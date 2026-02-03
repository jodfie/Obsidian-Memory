"""Graph engine for computing knowledge graph from markdown notes."""

import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Callable

from app.models.graph import (
    Edge,
    EdgeSource,
    EdgeType,
    Graph,
    GraphPath,
    Node,
    PathStep,
    TraversalQuery,
    TraversalResult,
)
from app.models.note import ParsedNote, Relation, RelationType, Wikilink
from app.models.search import IndexedNote


class GraphEngine:
    """Computes and maintains knowledge graph from markdown notes."""

    def __init__(self) -> None:
        """Initialize graph engine."""
        self.graph = Graph()

    def add_note(
        self, note_id: int, indexed_note: IndexedNote, parsed_note: ParsedNote
    ) -> None:
        """
        Add a note to the graph, creating nodes and edges.

        Args:
            note_id: Note ID from search index
            indexed_note: Indexed note with metadata
            parsed_note: Parsed note with relations and wikilinks
        """

        # Create or update node
        node = Node(
            id=note_id,
            title=parsed_note.frontmatter.title,
            permalink=parsed_note.frontmatter.permalink,
            vault_name=indexed_note.vault_name,
            relative_path=indexed_note.relative_path,
            note_type=parsed_note.frontmatter.type.value,
            project=parsed_note.frontmatter.project,
            tags=parsed_note.frontmatter.tags,
            created_at=indexed_note.created_at,
            updated_at=indexed_note.updated_at,
        )

        self.graph.nodes[note_id] = node

        # Update mappings
        if parsed_note.frontmatter.title:
            self.graph.title_to_id[parsed_note.frontmatter.title] = note_id
        if parsed_note.frontmatter.permalink:
            self.graph.permalink_to_id[
                parsed_note.frontmatter.permalink
            ] = note_id

        # Create edges from relations
        for relation in parsed_note.relations:
            edge = Edge(
                edge_id=str(uuid.uuid4()),
                source_id=note_id,
                target_id=None,  # Will be resolved later
                target_title=relation.target,
                edge_type=EdgeType(relation.relation_type.value),
                context=relation.context,
                weight=1.0,
                source_type=EdgeSource.EXPLICIT,
                confidence=1.0,
            )
            self.graph.edges.append(edge)

        # Create edges from wikilinks
        for wikilink in parsed_note.wikilinks:
            edge = Edge(
                edge_id=str(uuid.uuid4()),
                source_id=note_id,
                target_id=None,  # Will be resolved later
                target_title=wikilink.target,
                edge_type=EdgeType.LINKS_TO,
                context=None,
                weight=0.5,  # Wikilinks are weaker than explicit relations
                source_type=EdgeSource.WIKILINK,
                confidence=1.0,
            )
            self.graph.edges.append(edge)

    def add_inferred_edges_from_records(
        self, records: list[dict], node_ids: set[int] | None = None
    ) -> int:
        """Add edges from stored inferred-relation records.

        Use this to merge DB-backed inferred relations into the in-memory graph.
        Only adds edges whose source_id and target_id exist in the graph (or in
        node_ids if provided).

        Args:
            records: List of dicts from get_inferred_relations (edge_id,
                source_note_id, target_note_id, relation_type, confidence,
                reasoning, inferred_at, etc.)
            node_ids: Optional set of note IDs to allow; if None, only notes
                already in self.graph.nodes are allowed.

        Returns:
            Number of edges added.
        """
        from datetime import datetime

        allowed = node_ids if node_ids is not None else set(self.graph.nodes)
        added = 0
        for rec in records:
            sid = rec.get("source_note_id")
            tid = rec.get("target_note_id")
            if sid is None or tid is None or sid not in allowed or tid not in allowed:
                continue
            relation_type = rec.get("relation_type", "related_to")
            try:
                edge_type = EdgeType(relation_type)
            except ValueError:
                edge_type = EdgeType.RELATED_TO
            target_title = rec.get("target_title") or ""
            inferred_at = rec.get("inferred_at")
            if isinstance(inferred_at, str):
                try:
                    inferred_at = datetime.fromisoformat(
                        inferred_at.replace("Z", "+00:00")
                    )
                except ValueError:
                    inferred_at = None
            edge = Edge(
                edge_id=rec.get("edge_id"),
                source_id=sid,
                target_id=tid,
                target_title=target_title,
                edge_type=edge_type,
                context=rec.get("reasoning") or rec.get("context"),
                weight=float(rec.get("confidence", 1.0)),
                source_type=EdgeSource.INFERRED,
                confidence=float(rec.get("confidence", 1.0)),
                reasoning=rec.get("reasoning"),
                inferred_at=inferred_at,
            )
            self.graph.edges.append(edge)
            added += 1
        return added

    def resolve_edges(self) -> None:
        """Resolve target IDs for all edges using title and permalink mappings."""
        for edge in self.graph.edges:
            if edge.target_id is not None:
                continue  # Already resolved

            # Try to resolve by title
            if edge.target_title in self.graph.title_to_id:
                edge.target_id = self.graph.title_to_id[edge.target_title]
                continue

            # Try to resolve by permalink (if target_title looks like a permalink)
            if edge.target_title in self.graph.permalink_to_id:
                edge.target_id = self.graph.permalink_to_id[edge.target_title]

    def remove_note(self, note_id: int) -> None:
        """Remove a note and all its edges from the graph."""
        if note_id not in self.graph.nodes:
            return

        # Remove node
        node = self.graph.nodes[note_id]
        del self.graph.nodes[note_id]

        # Remove from mappings
        if node.title in self.graph.title_to_id:
            if self.graph.title_to_id[node.title] == note_id:
                del self.graph.title_to_id[node.title]

        if node.permalink and node.permalink in self.graph.permalink_to_id:
            if self.graph.permalink_to_id[node.permalink] == note_id:
                del self.graph.permalink_to_id[node.permalink]

        # Remove edges
        self.graph.edges = [
            e for e in self.graph.edges if e.source_id != note_id and e.target_id != note_id
        ]

    def get_node(self, note_id: int) -> Node | None:
        """Get a node by ID."""
        return self.graph.nodes.get(note_id)

    def get_outgoing_edges(self, note_id: int) -> list[Edge]:
        """Get all outgoing edges from a node."""
        return [e for e in self.graph.edges if e.source_id == note_id]

    def get_incoming_edges(self, note_id: int) -> list[Edge]:
        """Get all incoming edges to a node."""
        return [e for e in self.graph.edges if e.target_id == note_id]

    def get_neighbors(self, note_id: int) -> list[int]:
        """Get all neighbor node IDs (both incoming and outgoing)."""
        neighbors: set[int] = set()

        for edge in self.graph.edges:
            if edge.source_id == note_id and edge.target_id is not None:
                neighbors.add(edge.target_id)
            elif edge.target_id == note_id:
                neighbors.add(edge.source_id)

        return list(neighbors)

    def get_graph(self) -> Graph:
        """Get the current graph."""
        return self.graph

    def clear(self) -> None:
        """Clear the entire graph."""
        self.graph = Graph()

    # Graph Traversal Methods

    def _get_edges_for_traversal(
        self, node_id: int, direction: str, edge_types: list[EdgeType] | None
    ) -> list[Edge]:
        """Get edges for traversal based on direction and type filters."""
        if direction == "outgoing":
            edges = self.get_outgoing_edges(node_id)
        elif direction == "incoming":
            edges = self.get_incoming_edges(node_id)
        else:  # both
            edges = self.get_outgoing_edges(node_id) + self.get_incoming_edges(
                node_id
            )

        # Filter by edge types
        if edge_types:
            edges = [e for e in edges if e.edge_type in edge_types]

        # Only include resolved edges
        return [e for e in edges if e.target_id is not None]

    def traverse_bfs(
        self, query: TraversalQuery
    ) -> TraversalResult:
        """
        Breadth-first search traversal of the graph.

        Args:
            query: Traversal query parameters

        Returns:
            TraversalResult with visited nodes
        """
        visited: list[int] = []
        queue: deque[tuple[int, int]] = deque(
            [(query.start_node_id, 0)]
        )  # (node_id, depth)
        seen: set[int] = {query.start_node_id}
        exclude = set(query.exclude_nodes)

        while queue:
            node_id, depth = queue.popleft()

            if depth > query.max_depth:
                continue

            if node_id not in exclude:
                visited.append(node_id)

            # If we found the target, we can stop (optional)
            if query.target_node_id and node_id == query.target_node_id:
                break

            # Get neighbors
            edges = self._get_edges_for_traversal(
                node_id, query.direction, query.edge_types
            )

            for edge in edges:
                # Determine next node based on edge direction
                if query.direction == "outgoing":
                    # Follow edge forward: source -> target
                    if edge.source_id == node_id and edge.target_id is not None:
                        next_id = edge.target_id
                    else:
                        continue
                elif query.direction == "incoming":
                    # Follow edge backward: target -> source
                    if edge.target_id == node_id:
                        next_id = edge.source_id
                    else:
                        continue
                else:  # both
                    # Can go either direction
                    if edge.source_id == node_id and edge.target_id is not None:
                        next_id = edge.target_id
                    elif edge.target_id == node_id:
                        next_id = edge.source_id
                    else:
                        continue

                if next_id not in seen and next_id not in exclude:
                    seen.add(next_id)
                    queue.append((next_id, depth + 1))

        return TraversalResult(
            visited_nodes=visited,
            paths=[],
            depth_reached=query.max_depth,
        )

    def traverse_dfs(
        self, query: TraversalQuery
    ) -> TraversalResult:
        """
        Depth-first search traversal of the graph.

        Args:
            query: Traversal query parameters

        Returns:
            TraversalResult with visited nodes
        """
        visited: list[int] = []
        stack: list[tuple[int, int]] = [
            (query.start_node_id, 0)
        ]  # (node_id, depth)
        seen: set[int] = {query.start_node_id}
        exclude = set(query.exclude_nodes)

        while stack:
            node_id, depth = stack.pop()

            if depth > query.max_depth:
                continue

            if node_id not in exclude:
                visited.append(node_id)

            # If we found the target, we can stop (optional)
            if query.target_node_id and node_id == query.target_node_id:
                break

            # Get neighbors (reverse order for DFS stack behavior)
            edges = self._get_edges_for_traversal(
                node_id, query.direction, query.edge_types
            )

            for edge in reversed(edges):
                # Determine next node based on edge direction
                if query.direction == "outgoing":
                    # Follow edge forward: source -> target
                    if edge.source_id == node_id and edge.target_id is not None:
                        next_id = edge.target_id
                    else:
                        continue
                elif query.direction == "incoming":
                    # Follow edge backward: target -> source
                    if edge.target_id == node_id:
                        next_id = edge.source_id
                    else:
                        continue
                else:  # both
                    # Can go either direction
                    if edge.source_id == node_id and edge.target_id is not None:
                        next_id = edge.target_id
                    elif edge.target_id == node_id:
                        next_id = edge.source_id
                    else:
                        continue

                if next_id not in seen and next_id not in exclude:
                    seen.add(next_id)
                    stack.append((next_id, depth + 1))

        return TraversalResult(
            visited_nodes=visited,
            paths=[],
            depth_reached=query.max_depth,
        )

    def find_shortest_path(
        self,
        start_id: int,
        target_id: int,
        max_depth: int = 10,
        edge_types: list[EdgeType] | None = None,
        direction: str = "outgoing",
    ) -> GraphPath | None:
        """
        Find shortest path between two nodes using BFS.

        Args:
            start_id: Starting node ID
            target_id: Target node ID
            max_depth: Maximum path length
            edge_types: Filter by edge types
            direction: Traversal direction

        Returns:
            GraphPath if found, None otherwise
        """
        if start_id == target_id:
            return GraphPath(steps=[], total_weight=0.0, length=0)

        # BFS with path tracking
        queue: deque[tuple[int, list[PathStep], float]] = deque(
            [(start_id, [], 0.0)]
        )
        seen: set[int] = {start_id}

        while queue:
            node_id, path, total_weight = queue.popleft()

            if len(path) >= max_depth:
                continue

            edges = self._get_edges_for_traversal(node_id, direction, edge_types)

            for edge in edges:
                # Determine next node based on edge direction
                if direction == "outgoing":
                    if edge.source_id == node_id and edge.target_id is not None:
                        next_id = edge.target_id
                    else:
                        continue
                elif direction == "incoming":
                    if edge.target_id == node_id:
                        next_id = edge.source_id
                    else:
                        continue
                else:  # both
                    if edge.source_id == node_id and edge.target_id is not None:
                        next_id = edge.target_id
                    elif edge.target_id == node_id:
                        next_id = edge.source_id
                    else:
                        continue

                if next_id in seen:
                    continue

                seen.add(next_id)

                # Create new path step
                step = PathStep(
                    from_node_id=node_id,
                    to_node_id=next_id,
                    edge=edge,
                    depth=len(path),
                )

                new_path = path + [step]
                new_weight = total_weight + edge.weight

                if next_id == target_id:
                    return GraphPath(
                        steps=new_path, total_weight=new_weight, length=len(new_path)
                    )

                queue.append((next_id, new_path, new_weight))

        return None

    def find_all_paths(
        self,
        start_id: int,
        target_id: int,
        max_depth: int = 10,
        max_paths: int = 100,
        edge_types: list[EdgeType] | None = None,
        direction: str = "outgoing",
    ) -> list[GraphPath]:
        """
        Find all paths between two nodes (up to max_paths).

        Args:
            start_id: Starting node ID
            target_id: Target node ID
            max_depth: Maximum path length
            max_paths: Maximum number of paths to return
            edge_types: Filter by edge types
            direction: Traversal direction

        Returns:
            List of paths found
        """
        if start_id == target_id:
            return [GraphPath(steps=[], total_weight=0.0, length=0)]

        paths: list[GraphPath] = []
        stack: list[tuple[int, list[PathStep], float, set[int]]] = [
            (start_id, [], 0.0, {start_id})
        ]

        while stack and len(paths) < max_paths:
            node_id, path, total_weight, visited = stack.pop()

            if len(path) >= max_depth:
                continue

            edges = self._get_edges_for_traversal(node_id, direction, edge_types)

            for edge in edges:
                # Determine next node based on edge direction
                if direction == "outgoing":
                    if edge.source_id == node_id and edge.target_id is not None:
                        next_id = edge.target_id
                    else:
                        continue
                elif direction == "incoming":
                    if edge.target_id == node_id:
                        next_id = edge.source_id
                    else:
                        continue
                else:  # both
                    if edge.source_id == node_id and edge.target_id is not None:
                        next_id = edge.target_id
                    elif edge.target_id == node_id:
                        next_id = edge.source_id
                    else:
                        continue

                if next_id in visited:
                    continue

                # Create new path step
                step = PathStep(
                    from_node_id=node_id,
                    to_node_id=next_id,
                    edge=edge,
                    depth=len(path),
                )

                new_path = path + [step]
                new_weight = total_weight + edge.weight
                new_visited = visited | {next_id}

                if next_id == target_id:
                    paths.append(
                        GraphPath(
                            steps=new_path,
                            total_weight=new_weight,
                            length=len(new_path),
                        )
                    )
                else:
                    stack.append((next_id, new_path, new_weight, new_visited))

        # Sort by weight (shortest first)
        paths.sort(key=lambda p: p.total_weight)
        return paths[:max_paths]

    def get_reachable_nodes(
        self,
        start_id: int,
        max_depth: int = 10,
        edge_types: list[EdgeType] | None = None,
        direction: str = "outgoing",
    ) -> list[int]:
        """
        Get all nodes reachable from a starting node.

        Args:
            start_id: Starting node ID
            max_depth: Maximum traversal depth
            edge_types: Filter by edge types
            direction: Traversal direction

        Returns:
            List of reachable node IDs
        """
        query = TraversalQuery(
            start_node_id=start_id,
            max_depth=max_depth,
            edge_types=edge_types,
            direction=direction,
        )
        result = self.traverse_bfs(query)
        # Remove start node from results
        return [nid for nid in result.visited_nodes if nid != start_id]

    # Graph Analysis Methods

    def get_node_centrality(self, node_id: int) -> dict:
        """
        Calculate centrality metrics for a node.

        Returns degree centrality (incoming + outgoing edges),
        plus breakdown by edge types.

        Args:
            node_id: Node ID to analyze

        Returns:
            Dictionary with centrality metrics
        """
        outgoing = self.get_outgoing_edges(node_id)
        incoming = self.get_incoming_edges(node_id)

        # Count by edge type
        outgoing_by_type: dict[str, int] = {}
        for edge in outgoing:
            edge_type_name = edge.edge_type.value
            outgoing_by_type[edge_type_name] = outgoing_by_type.get(edge_type_name, 0) + 1

        incoming_by_type: dict[str, int] = {}
        for edge in incoming:
            edge_type_name = edge.edge_type.value
            incoming_by_type[edge_type_name] = incoming_by_type.get(edge_type_name, 0) + 1

        return {
            "node_id": node_id,
            "degree_centrality": len(outgoing) + len(incoming),
            "in_degree": len(incoming),
            "out_degree": len(outgoing),
            "outgoing_by_type": outgoing_by_type,
            "incoming_by_type": incoming_by_type,
            "normalized_centrality": (len(outgoing) + len(incoming)) / max(len(self.graph.nodes) - 1, 1)
        }

    def get_graph_stats(self) -> dict:
        """
        Get comprehensive graph statistics.

        Returns:
            Dictionary with graph metrics including:
            - Total nodes and edges
            - Edge type distribution
            - Orphan nodes (no connections)
            - Average degree
            - Most connected nodes
        """
        total_nodes = len(self.graph.nodes)
        total_edges = len(self.graph.edges)

        # Edge type distribution
        edge_type_counts: dict[str, int] = {}
        for edge in self.graph.edges:
            edge_type_name = edge.edge_type.value
            edge_type_counts[edge_type_name] = edge_type_counts.get(edge_type_name, 0) + 1

        # Find orphan nodes (no incoming or outgoing edges)
        orphan_nodes = []
        node_degrees = {}

        for node_id in self.graph.nodes:
            outgoing = len(self.get_outgoing_edges(node_id))
            incoming = len(self.get_incoming_edges(node_id))
            degree = outgoing + incoming
            node_degrees[node_id] = degree

            if degree == 0:
                orphan_nodes.append(node_id)

        # Calculate average degree
        avg_degree = sum(node_degrees.values()) / max(total_nodes, 1)

        # Find most connected nodes
        sorted_nodes = sorted(node_degrees.items(), key=lambda x: x[1], reverse=True)
        top_hubs = sorted_nodes[:10]  # Top 10 most connected

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "edge_type_distribution": edge_type_counts,
            "orphan_nodes": orphan_nodes,
            "orphan_count": len(orphan_nodes),
            "average_degree": avg_degree,
            "top_hubs": [{"node_id": nid, "degree": deg} for nid, deg in top_hubs],
            "graph_density": (2 * total_edges) / (total_nodes * (total_nodes - 1)) if total_nodes > 1 else 0
        }

    def find_hubs(self, limit: int = 10) -> list[dict]:
        """
        Find hub nodes with highest connectivity.

        Args:
            limit: Maximum number of hubs to return

        Returns:
            List of hub nodes with their centrality metrics
        """
        node_centralities = []

        for node_id in self.graph.nodes:
            centrality = self.get_node_centrality(node_id)
            node = self.get_node(node_id)
            if node:
                node_centralities.append({
                    "node_id": node_id,
                    "title": node.title,
                    "permalink": node.permalink,
                    "degree_centrality": centrality["degree_centrality"],
                    "in_degree": centrality["in_degree"],
                    "out_degree": centrality["out_degree"],
                    "normalized_centrality": centrality["normalized_centrality"]
                })

        # Sort by degree centrality
        node_centralities.sort(key=lambda x: x["degree_centrality"], reverse=True)

        return node_centralities[:limit]

    # -------------------------------------------------------------------------
    # Inferred Relations Management
    # -------------------------------------------------------------------------

    def add_inferred_edge(
        self,
        source_id: int,
        target_id: int,
        edge_type: EdgeType,
        confidence: float,
        reasoning: str | None = None,
        context: str | None = None,
    ) -> Edge:
        """
        Add an AI-inferred edge to the graph.

        Args:
            source_id: Source note ID
            target_id: Target note ID
            edge_type: Type of relation
            confidence: Confidence score (0-1)
            reasoning: AI reasoning for the inference
            context: Additional context

        Returns:
            The created Edge
        """
        # Get target title for the edge
        target_node = self.get_node(target_id)
        target_title = target_node.title if target_node else f"Note #{target_id}"

        edge = Edge(
            edge_id=str(uuid.uuid4()),
            source_id=source_id,
            target_id=target_id,
            target_title=target_title,
            edge_type=edge_type,
            context=context,
            weight=confidence,  # Use confidence as weight for ranking
            source_type=EdgeSource.INFERRED,
            confidence=confidence,
            reasoning=reasoning,
            inferred_at=datetime.now(timezone.utc),
        )

        self.graph.edges.append(edge)
        return edge

    def get_inferred_edges(
        self,
        min_confidence: float = 0.0,
        edge_type: EdgeType | None = None,
    ) -> list[Edge]:
        """
        Get all inferred edges, optionally filtered.

        Args:
            min_confidence: Minimum confidence threshold
            edge_type: Optional filter by edge type

        Returns:
            List of inferred edges
        """
        edges = [
            e for e in self.graph.edges
            if e.source_type == EdgeSource.INFERRED
            and e.confidence >= min_confidence
        ]

        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]

        return sorted(edges, key=lambda e: e.confidence, reverse=True)

    def get_edge_by_id(self, edge_id: str) -> Edge | None:
        """
        Get an edge by its ID.

        Args:
            edge_id: Edge identifier

        Returns:
            Edge if found, None otherwise
        """
        for edge in self.graph.edges:
            if edge.edge_id == edge_id:
                return edge
        return None

    def promote_inferred_edge(self, edge_id: str) -> Edge | None:
        """
        Promote an inferred edge to explicit.

        This changes the edge's source_type from INFERRED to EXPLICIT,
        effectively making it a permanent relationship.

        Args:
            edge_id: Edge identifier to promote

        Returns:
            The promoted edge, or None if not found
        """
        edge = self.get_edge_by_id(edge_id)
        if edge and edge.source_type == EdgeSource.INFERRED:
            edge.source_type = EdgeSource.EXPLICIT
            edge.confidence = 1.0  # Promoted edges have full confidence
            return edge
        return None

    def remove_edge(self, edge_id: str) -> bool:
        """
        Remove an edge by ID.

        Args:
            edge_id: Edge identifier to remove

        Returns:
            True if edge was removed, False if not found
        """
        for i, edge in enumerate(self.graph.edges):
            if edge.edge_id == edge_id:
                del self.graph.edges[i]
                return True
        return False

    def remove_inferred_edges_for_note(self, note_id: int) -> int:
        """
        Remove all inferred edges involving a specific note.

        Useful when re-running inference for a note.

        Args:
            note_id: Note ID to clear inferred edges for

        Returns:
            Number of edges removed
        """
        original_count = len(self.graph.edges)
        self.graph.edges = [
            e for e in self.graph.edges
            if not (
                e.source_type == EdgeSource.INFERRED
                and (e.source_id == note_id or e.target_id == note_id)
            )
        ]
        return original_count - len(self.graph.edges)

    def get_edges_between(
        self,
        source_id: int,
        target_id: int,
        include_reverse: bool = True,
    ) -> list[Edge]:
        """
        Get all edges between two notes.

        Args:
            source_id: Source note ID
            target_id: Target note ID
            include_reverse: Also include edges in reverse direction

        Returns:
            List of edges between the notes
        """
        edges = [
            e for e in self.graph.edges
            if e.source_id == source_id and e.target_id == target_id
        ]

        if include_reverse:
            edges.extend([
                e for e in self.graph.edges
                if e.source_id == target_id and e.target_id == source_id
            ])

        return edges

    def has_edge_between(
        self,
        source_id: int,
        target_id: int,
        edge_type: EdgeType | None = None,
    ) -> bool:
        """
        Check if an edge exists between two notes.

        Args:
            source_id: Source note ID
            target_id: Target note ID
            edge_type: Optional edge type to check for

        Returns:
            True if edge exists
        """
        for edge in self.graph.edges:
            if edge.source_id == source_id and edge.target_id == target_id:
                if edge_type is None or edge.edge_type == edge_type:
                    return True
        return False
