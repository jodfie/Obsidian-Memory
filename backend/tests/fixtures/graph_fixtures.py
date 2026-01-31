"""Reusable graph fixtures for testing graph functionality."""

import pytest
from typing import Dict, List, Tuple
from app.services.graph_engine import GraphEngine
from app.models.graph import Node, Edge, EdgeType
from app.models.note import ParsedNote, Frontmatter, NoteType, Relation, RelationType, Wikilink
from app.models.search import IndexedNote
from datetime import datetime


@pytest.fixture
def empty_graph() -> GraphEngine:
    """Create an empty graph engine."""
    return GraphEngine()


@pytest.fixture
def single_node_graph() -> GraphEngine:
    """Create a graph with a single isolated node."""
    engine = GraphEngine()

    node = Node(
        id=1,
        title="Single Node",
        permalink="single-node",
        vault_name="test",
        relative_path="single.md",
        note_type="note",
        tags=["single"],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    engine.graph.nodes[1] = node
    engine.graph.title_to_id["Single Node"] = 1
    engine.graph.permalink_to_id["single-node"] = 1

    return engine


@pytest.fixture
def chain_graph() -> GraphEngine:
    """
    Create a linear chain graph: 1 -> 2 -> 3 -> 4 -> 5

    Useful for testing simple traversals and path finding.
    """
    engine = GraphEngine()

    # Add nodes
    for i in range(1, 6):
        node = Node(
            id=i,
            title=f"Node {i}",
            permalink=f"node-{i}",
            vault_name="test",
            relative_path=f"node_{i}.md",
            note_type="note",
            tags=[f"chain"],
        )
        engine.graph.nodes[i] = node
        engine.graph.title_to_id[f"Node {i}"] = i
        engine.graph.permalink_to_id[f"node-{i}"] = i

    # Add edges to form chain
    for i in range(1, 5):
        edge = Edge(
            source_id=i,
            target_id=i + 1,
            target_title=f"Node {i + 1}",
            edge_type=EdgeType.LINKS_TO,
            weight=1.0,
        )
        engine.graph.edges.append(edge)

    return engine


@pytest.fixture
def tree_graph() -> GraphEngine:
    """
    Create a tree structure:
           1
          / \\
         2   3
        / \\   \\
       4   5   6

    Useful for testing hierarchical traversals.
    """
    engine = GraphEngine()

    # Add nodes
    for i in range(1, 7):
        node = Node(
            id=i,
            title=f"Node {i}",
            permalink=f"node-{i}",
            vault_name="test",
            relative_path=f"node_{i}.md",
            note_type="note",
            tags=["tree"],
        )
        engine.graph.nodes[i] = node
        engine.graph.title_to_id[f"Node {i}"] = i
        engine.graph.permalink_to_id[f"node-{i}"] = i

    # Add edges to form tree
    edges_data = [
        (1, 2, EdgeType.PART_OF),
        (1, 3, EdgeType.PART_OF),
        (2, 4, EdgeType.PART_OF),
        (2, 5, EdgeType.PART_OF),
        (3, 6, EdgeType.PART_OF),
    ]

    for source, target, edge_type in edges_data:
        edge = Edge(
            source_id=source,
            target_id=target,
            target_title=f"Node {target}",
            edge_type=edge_type,
            weight=1.0,
        )
        engine.graph.edges.append(edge)

    return engine


@pytest.fixture
def cyclic_graph() -> GraphEngine:
    """
    Create a graph with cycles:
    1 -> 2 -> 3
    ^         |
    |         v
    5 <- 4 <-

    Useful for testing cycle detection and path algorithms.
    """
    engine = GraphEngine()

    # Add nodes
    for i in range(1, 6):
        node = Node(
            id=i,
            title=f"Node {i}",
            permalink=f"node-{i}",
            vault_name="test",
            relative_path=f"node_{i}.md",
            note_type="note",
            tags=["cyclic"],
        )
        engine.graph.nodes[i] = node
        engine.graph.title_to_id[f"Node {i}"] = i
        engine.graph.permalink_to_id[f"node-{i}"] = i

    # Add edges to form cycle
    edges_data = [
        (1, 2, EdgeType.LINKS_TO),
        (2, 3, EdgeType.LINKS_TO),
        (3, 4, EdgeType.LINKS_TO),
        (4, 5, EdgeType.LINKS_TO),
        (5, 1, EdgeType.LINKS_TO),  # Creates the cycle
    ]

    for source, target, edge_type in edges_data:
        edge = Edge(
            source_id=source,
            target_id=target,
            target_title=f"Node {target}",
            edge_type=edge_type,
            weight=1.0,
        )
        engine.graph.edges.append(edge)

    return engine


@pytest.fixture
def disconnected_graph() -> GraphEngine:
    """
    Create a graph with multiple disconnected components:
    Component 1: 1 <-> 2 <-> 3
    Component 2: 4 <-> 5
    Isolated: 6, 7

    Useful for testing connectivity and component detection.
    """
    engine = GraphEngine()

    # Add nodes
    for i in range(1, 8):
        node = Node(
            id=i,
            title=f"Node {i}",
            permalink=f"node-{i}",
            vault_name="test",
            relative_path=f"node_{i}.md",
            note_type="note",
            tags=["disconnected"],
        )
        engine.graph.nodes[i] = node
        engine.graph.title_to_id[f"Node {i}"] = i
        engine.graph.permalink_to_id[f"node-{i}"] = i

    # Add edges for component 1 (bidirectional)
    component1_edges = [
        (1, 2), (2, 1),  # 1 <-> 2
        (2, 3), (3, 2),  # 2 <-> 3
    ]

    # Add edges for component 2 (bidirectional)
    component2_edges = [
        (4, 5), (5, 4),  # 4 <-> 5
    ]

    for source, target in component1_edges + component2_edges:
        edge = Edge(
            source_id=source,
            target_id=target,
            target_title=f"Node {target}",
            edge_type=EdgeType.RELATED_TO,
            weight=1.0,
        )
        engine.graph.edges.append(edge)

    # Nodes 6 and 7 remain isolated (no edges)

    return engine


@pytest.fixture
def hub_spoke_graph() -> GraphEngine:
    """
    Create a hub-and-spoke graph:
    All nodes 2-8 connect to central hub node 1.

    Useful for testing centrality and hub detection.
    """
    engine = GraphEngine()

    # Add hub node
    hub = Node(
        id=1,
        title="Central Hub",
        permalink="central-hub",
        vault_name="test",
        relative_path="hub.md",
        note_type="note",
        tags=["hub"],
    )
    engine.graph.nodes[1] = hub
    engine.graph.title_to_id["Central Hub"] = 1
    engine.graph.permalink_to_id["central-hub"] = 1

    # Add spoke nodes and edges
    for i in range(2, 9):
        node = Node(
            id=i,
            title=f"Spoke {i}",
            permalink=f"spoke-{i}",
            vault_name="test",
            relative_path=f"spoke_{i}.md",
            note_type="note",
            tags=["spoke"],
        )
        engine.graph.nodes[i] = node
        engine.graph.title_to_id[f"Spoke {i}"] = i
        engine.graph.permalink_to_id[f"spoke-{i}"] = i

        # Add bidirectional edges between hub and spoke
        edge_out = Edge(
            source_id=1,
            target_id=i,
            target_title=f"Spoke {i}",
            edge_type=EdgeType.ENABLES,
            weight=1.0,
        )
        edge_in = Edge(
            source_id=i,
            target_id=1,
            target_title="Central Hub",
            edge_type=EdgeType.DEPENDS_ON,
            weight=1.0,
        )
        engine.graph.edges.extend([edge_out, edge_in])

    return engine


@pytest.fixture
def complex_graph() -> GraphEngine:
    """
    Create a complex graph with various edge types and weights:
    - Multiple paths between nodes
    - Different edge types
    - Varying edge weights

    Structure:
    1 --depends_on--> 2 --enables--> 4
    |                 |               ^
    links_to      related_to          |
    |                 |           part_of
    v                 v               |
    3 <--solved_by--- 5 --------------+

    Useful for testing advanced traversal and similarity algorithms.
    """
    engine = GraphEngine()

    # Add nodes with different attributes
    nodes_data = [
        (1, "Project Root", ["project", "root"]),
        (2, "Core Module", ["module", "core"]),
        (3, "Feature A", ["feature"]),
        (4, "Implementation", ["implementation"]),
        (5, "Solution", ["solution"]),
    ]

    for node_id, title, tags in nodes_data:
        node = Node(
            id=node_id,
            title=title,
            permalink=title.lower().replace(" ", "-"),
            vault_name="test",
            relative_path=f"{title.lower().replace(' ', '_')}.md",
            note_type="note",
            tags=tags,
        )
        engine.graph.nodes[node_id] = node
        engine.graph.title_to_id[title] = node_id
        engine.graph.permalink_to_id[node.permalink] = node_id

    # Add edges with various types and weights
    edges_data = [
        (1, 2, EdgeType.DEPENDS_ON, 1.0),
        (1, 3, EdgeType.LINKS_TO, 0.5),
        (2, 4, EdgeType.ENABLES, 1.0),
        (2, 5, EdgeType.RELATED_TO, 0.7),
        (5, 3, EdgeType.SOLVED_BY, 1.5),
        (5, 4, EdgeType.PART_OF, 0.8),
    ]

    for source, target, edge_type, weight in edges_data:
        edge = Edge(
            source_id=source,
            target_id=target,
            target_title=engine.graph.nodes[target].title,
            edge_type=edge_type,
            weight=weight,
        )
        engine.graph.edges.append(edge)

    return engine


@pytest.fixture
def bidirectional_graph() -> GraphEngine:
    """
    Create a fully bidirectional graph where every edge has a reverse:
    1 <-> 2 <-> 3
      ^   ^   ^
      |   |   |
      v   v   v
      4 <-> 5

    Useful for testing undirected graph algorithms.
    """
    engine = GraphEngine()

    # Add nodes
    for i in range(1, 6):
        node = Node(
            id=i,
            title=f"Node {i}",
            permalink=f"node-{i}",
            vault_name="test",
            relative_path=f"node_{i}.md",
            note_type="note",
            tags=["bidirectional"],
        )
        engine.graph.nodes[i] = node
        engine.graph.title_to_id[f"Node {i}"] = i
        engine.graph.permalink_to_id[f"node-{i}"] = i

    # Add bidirectional edges
    bidirectional_pairs = [
        (1, 2), (2, 3),  # Horizontal connections
        (1, 4), (2, 4), (2, 5), (3, 5),  # Vertical connections
        (4, 5),  # Bottom connection
    ]

    for source, target in bidirectional_pairs:
        # Forward edge
        edge_forward = Edge(
            source_id=source,
            target_id=target,
            target_title=f"Node {target}",
            edge_type=EdgeType.RELATED_TO,
            weight=1.0,
        )
        # Reverse edge
        edge_reverse = Edge(
            source_id=target,
            target_id=source,
            target_title=f"Node {source}",
            edge_type=EdgeType.RELATED_TO,
            weight=1.0,
        )
        engine.graph.edges.extend([edge_forward, edge_reverse])

    return engine


# Helper function fixtures

@pytest.fixture
def create_test_note():
    """Factory fixture for creating test notes."""
    def _create_note(
        note_id: int,
        title: str,
        relations: List[Tuple[str, str]] = None,  # [(relation_type, target)]
        wikilinks: List[str] = None,
        tags: List[str] = None,
    ) -> Tuple[IndexedNote, ParsedNote]:
        """Create indexed and parsed note for testing."""

        indexed_note = IndexedNote(
            vault_name="test",
            relative_path=f"{title.lower().replace(' ', '_')}.md",
            title=title,
            note_type="note",
            project="test_project",
            content=f"# {title}\n\nTest content",
            tags=tags or [],
            file_hash="test_hash",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        parsed_relations = []
        if relations:
            for rel_type, target in relations:
                parsed_relations.append(
                    Relation(
                        relation_type=RelationType(rel_type),
                        target=target,
                        context=f"{rel_type} {target}",
                    )
                )

        parsed_wikilinks = []
        if wikilinks:
            for link in wikilinks:
                parsed_wikilinks.append(Wikilink(target=link))

        parsed_note = ParsedNote(
            frontmatter=Frontmatter(
                title=title,
                permalink=title.lower().replace(" ", "-"),
                type=NoteType.NOTE,
                tags=tags or [],
            ),
            relations=parsed_relations,
            wikilinks=parsed_wikilinks,
            content=f"# {title}\n\nTest content",
        )

        return indexed_note, parsed_note

    return _create_note


@pytest.fixture
def assert_graph_structure():
    """Factory fixture for asserting graph structure."""
    def _assert_structure(
        engine: GraphEngine,
        expected_nodes: int,
        expected_edges: int,
        expected_orphans: List[int] = None,
    ):
        """Assert basic graph structure properties."""
        assert len(engine.graph.nodes) == expected_nodes, f"Expected {expected_nodes} nodes, got {len(engine.graph.nodes)}"
        assert len(engine.graph.edges) == expected_edges, f"Expected {expected_edges} edges, got {len(engine.graph.edges)}"

        if expected_orphans is not None:
            stats = engine.get_graph_stats()
            assert set(stats["orphan_nodes"]) == set(expected_orphans), f"Expected orphans {expected_orphans}, got {stats['orphan_nodes']}"

    return _assert_structure