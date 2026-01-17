"""Graph engine for computing knowledge graph from markdown notes."""

from collections import deque
from typing import Callable

from app.models.graph import (
    Edge,
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
                source_id=note_id,
                target_id=None,  # Will be resolved later
                target_title=relation.target,
                edge_type=EdgeType(relation.relation_type.value),
                context=relation.context,
                weight=1.0,
            )
            self.graph.edges.append(edge)

        # Create edges from wikilinks
        for wikilink in parsed_note.wikilinks:
            edge = Edge(
                source_id=note_id,
                target_id=None,  # Will be resolved later
                target_title=wikilink.target,
                edge_type=EdgeType.LINKS_TO,
                context=None,
                weight=0.5,  # Wikilinks are weaker than explicit relations
            )
            self.graph.edges.append(edge)

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
