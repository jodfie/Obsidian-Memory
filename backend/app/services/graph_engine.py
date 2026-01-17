"""Graph engine for computing knowledge graph from markdown notes."""

from app.models.graph import Edge, EdgeType, Graph, Node
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
