"""Comprehensive tests for path finding algorithms."""

import pytest
from app.models.graph import EdgeType
from app.services.graph_engine import GraphEngine

# Import our graph fixtures
from tests.fixtures.graph_fixtures import (
    empty_graph,
    single_node_graph,
    chain_graph,
    tree_graph,
    cyclic_graph,
    disconnected_graph,
    complex_graph,
    bidirectional_graph,
)


class TestShortestPath:
    """Test shortest path finding."""

    def test_shortest_path_empty_graph(self, empty_graph: GraphEngine):
        """Test path finding in empty graph."""
        path = empty_graph.find_shortest_path(1, 2)
        assert path is None

    def test_shortest_path_same_node(self, single_node_graph: GraphEngine):
        """Test path from node to itself."""
        path = single_node_graph.find_shortest_path(1, 1)
        assert path is not None
        assert path.length == 0
        assert path.steps == []
        assert path.total_weight == 0.0

    def test_shortest_path_chain(self, chain_graph: GraphEngine):
        """Test shortest path in linear chain."""
        # Path from 1 to 5
        path = chain_graph.find_shortest_path(1, 5)
        assert path is not None
        assert path.length == 4  # 4 edges: 1->2->3->4->5
        assert len(path.steps) == 4

        # Verify path is correct
        expected_path = [(1, 2), (2, 3), (3, 4), (4, 5)]
        for i, step in enumerate(path.steps):
            assert step.from_node_id == expected_path[i][0]
            assert step.to_node_id == expected_path[i][1]

        # No backward path in forward-only chain
        path = chain_graph.find_shortest_path(5, 1, direction="outgoing")
        assert path is None

    def test_shortest_path_tree(self, tree_graph: GraphEngine):
        """Test shortest path in tree structure."""
        # Path from root to leaf
        path = tree_graph.find_shortest_path(1, 4)
        assert path is not None
        assert path.length == 2  # 1->2->4

        # Path between leaves (requires going through parent)
        # Since tree edges are directed downward, can't traverse between leaves
        path = tree_graph.find_shortest_path(4, 6, direction="outgoing")
        assert path is None  # Can't go up the tree with outgoing edges

    def test_shortest_path_cyclic(self, cyclic_graph: GraphEngine):
        """Test shortest path in graph with cycles."""
        # Should find shortest path, not just any path
        path = cyclic_graph.find_shortest_path(1, 4)
        assert path is not None
        assert path.length == 3  # 1->2->3->4 (not going around the cycle)

        # Path that goes around cycle
        path = cyclic_graph.find_shortest_path(4, 1)
        assert path is not None
        assert path.length == 2  # 4->5->1 (shorter than 4->3->2->1)

    def test_shortest_path_disconnected(self, disconnected_graph: GraphEngine):
        """Test shortest path between disconnected components."""
        # Nodes 1 and 4 are in different components
        path = disconnected_graph.find_shortest_path(1, 4, direction="both")
        assert path is None  # No path exists

        # Within same component
        path = disconnected_graph.find_shortest_path(1, 3, direction="both")
        assert path is not None
        assert path.length == 2  # 1->2->3

    def test_shortest_path_max_depth(self, chain_graph: GraphEngine):
        """Test shortest path with max depth limit."""
        # Path exists but exceeds max depth
        path = chain_graph.find_shortest_path(1, 5, max_depth=2)
        assert path is None  # Can't reach in 2 steps

        # Path within max depth
        path = chain_graph.find_shortest_path(1, 3, max_depth=2)
        assert path is not None
        assert path.length == 2

    def test_shortest_path_edge_filtering(self, complex_graph: GraphEngine):
        """Test shortest path with edge type filtering."""
        # Only follow specific edge types
        path = complex_graph.find_shortest_path(
            1, 4,
            edge_types=[EdgeType.DEPENDS_ON, EdgeType.ENABLES]
        )
        assert path is not None
        # 1 -DEPENDS_ON-> 2 -ENABLES-> 4
        assert path.length == 2

        # With different edge filter, path might not exist
        path = complex_graph.find_shortest_path(
            1, 4,
            edge_types=[EdgeType.LINKS_TO]
        )
        assert path is None  # No path using only LINKS_TO edges

    def test_shortest_path_weights(self, complex_graph: GraphEngine):
        """Test that shortest path considers edge weights."""
        # Complex graph has varying weights
        path = complex_graph.find_shortest_path(1, 5)
        assert path is not None
        # Should find path with minimum total weight
        assert path.total_weight > 0


class TestAllPaths:
    """Test finding all paths between nodes."""

    def test_all_paths_empty_graph(self, empty_graph: GraphEngine):
        """Test finding all paths in empty graph."""
        paths = empty_graph.find_all_paths(1, 2)
        assert paths == []

    def test_all_paths_same_node(self, single_node_graph: GraphEngine):
        """Test all paths from node to itself."""
        paths = single_node_graph.find_all_paths(1, 1)
        assert len(paths) == 1
        assert paths[0].length == 0

    def test_all_paths_chain(self, chain_graph: GraphEngine):
        """Test all paths in linear chain (only one path)."""
        paths = chain_graph.find_all_paths(1, 3)
        assert len(paths) == 1
        assert paths[0].length == 2  # 1->2->3

    def test_all_paths_cyclic(self, cyclic_graph: GraphEngine):
        """Test all paths in graph with cycles."""
        # Multiple paths possible but cycle detection prevents infinite paths
        paths = cyclic_graph.find_all_paths(1, 3, max_depth=10)
        assert len(paths) >= 1  # At least one path exists

        # Direct path should be shortest
        assert paths[0].length == 2  # 1->2->3 (paths sorted by weight)

    def test_all_paths_max_paths_limit(self, bidirectional_graph: GraphEngine):
        """Test limiting number of paths returned."""
        paths = bidirectional_graph.find_all_paths(1, 5, max_paths=2)
        assert len(paths) <= 2

    def test_all_paths_max_depth(self, bidirectional_graph: GraphEngine):
        """Test all paths with depth limit."""
        # Short paths only
        paths = bidirectional_graph.find_all_paths(1, 5, max_depth=2)

        for path in paths:
            assert path.length <= 2

    def test_all_paths_disconnected(self, disconnected_graph: GraphEngine):
        """Test all paths between disconnected components."""
        paths = disconnected_graph.find_all_paths(1, 6, direction="both")
        assert paths == []  # No paths between disconnected nodes

    def test_all_paths_multiple_routes(self):
        """Test finding multiple paths in custom graph."""
        engine = GraphEngine()

        # Create diamond pattern: multiple paths from 1 to 4
        #     2
        #   /   \
        # 1       4
        #   \   /
        #     3
        from app.models.graph import Node, Edge

        for i in range(1, 5):
            node = Node(
                id=i,
                title=f"Node {i}",
                vault_name="test",
                relative_path=f"node_{i}.md",
                note_type="note",
            )
            engine.graph.nodes[i] = node

        edges = [
            Edge(source_id=1, target_id=2, target_title="Node 2", edge_type=EdgeType.LINKS_TO),
            Edge(source_id=1, target_id=3, target_title="Node 3", edge_type=EdgeType.LINKS_TO),
            Edge(source_id=2, target_id=4, target_title="Node 4", edge_type=EdgeType.LINKS_TO),
            Edge(source_id=3, target_id=4, target_title="Node 4", edge_type=EdgeType.LINKS_TO),
        ]
        engine.graph.edges = edges

        paths = engine.find_all_paths(1, 4)
        assert len(paths) == 2  # Two paths: 1->2->4 and 1->3->4
        assert all(p.length == 2 for p in paths)


class TestReachableNodes:
    """Test finding reachable nodes."""

    def test_reachable_empty_graph(self, empty_graph: GraphEngine):
        """Test reachable nodes in empty graph."""
        reachable = empty_graph.get_reachable_nodes(1)
        assert reachable == []

    def test_reachable_single_node(self, single_node_graph: GraphEngine):
        """Test reachable from isolated node."""
        reachable = single_node_graph.get_reachable_nodes(1)
        assert reachable == []  # No other nodes reachable

    def test_reachable_chain(self, chain_graph: GraphEngine):
        """Test reachable nodes in chain."""
        # From start of chain
        reachable = chain_graph.get_reachable_nodes(1)
        assert set(reachable) == {2, 3, 4, 5}  # All downstream nodes

        # From middle of chain
        reachable = chain_graph.get_reachable_nodes(3)
        assert set(reachable) == {4, 5}  # Only downstream

        # From end of chain
        reachable = chain_graph.get_reachable_nodes(5)
        assert reachable == []  # No outgoing edges

    def test_reachable_tree(self, tree_graph: GraphEngine):
        """Test reachable nodes in tree."""
        # From root
        reachable = tree_graph.get_reachable_nodes(1)
        assert set(reachable) == {2, 3, 4, 5, 6}  # All descendants

        # From internal node
        reachable = tree_graph.get_reachable_nodes(2)
        assert set(reachable) == {4, 5}  # Only children

        # From leaf
        reachable = tree_graph.get_reachable_nodes(4)
        assert reachable == []  # No children

    def test_reachable_cyclic(self, cyclic_graph: GraphEngine):
        """Test reachable nodes in cyclic graph."""
        # All nodes should be reachable from any node due to cycle
        for start in range(1, 6):
            reachable = cyclic_graph.get_reachable_nodes(start)
            assert len(reachable) == 4  # All other nodes
            assert start not in reachable  # Excludes start node

    def test_reachable_disconnected(self, disconnected_graph: GraphEngine):
        """Test reachable nodes in disconnected graph."""
        # From component 1
        reachable = disconnected_graph.get_reachable_nodes(1, direction="both")
        assert set(reachable) == {2, 3}  # Only same component

        # From component 2
        reachable = disconnected_graph.get_reachable_nodes(4, direction="both")
        assert set(reachable) == {5}  # Only node 5

        # From isolated node
        reachable = disconnected_graph.get_reachable_nodes(6, direction="both")
        assert reachable == []  # No connections

    def test_reachable_max_depth(self, chain_graph: GraphEngine):
        """Test reachable nodes with depth limit."""
        # Limited depth
        reachable = chain_graph.get_reachable_nodes(1, max_depth=2)
        assert set(reachable) == {2, 3}  # Only 2 hops

        # Unlimited depth
        reachable = chain_graph.get_reachable_nodes(1, max_depth=100)
        assert set(reachable) == {2, 3, 4, 5}  # All downstream

    def test_reachable_directional(self, bidirectional_graph: GraphEngine):
        """Test reachable with different directions."""
        # Outgoing only
        reachable = bidirectional_graph.get_reachable_nodes(1, direction="outgoing")
        assert 2 in reachable  # Can reach via outgoing

        # Incoming only
        reachable = bidirectional_graph.get_reachable_nodes(5, direction="incoming")
        # Can reach nodes that have edges TO node 5

        # Both directions
        reachable = bidirectional_graph.get_reachable_nodes(3, direction="both")
        assert len(reachable) == 4  # All other nodes in connected graph

    def test_reachable_edge_filtering(self, complex_graph: GraphEngine):
        """Test reachable with edge type filtering."""
        # Only follow DEPENDS_ON edges
        reachable = complex_graph.get_reachable_nodes(
            1,
            edge_types=[EdgeType.DEPENDS_ON]
        )
        assert set(reachable) == {2}  # Only node 2 via DEPENDS_ON

        # Multiple edge types
        reachable = complex_graph.get_reachable_nodes(
            1,
            edge_types=[EdgeType.DEPENDS_ON, EdgeType.ENABLES]
        )
        # 1->2 via DEPENDS_ON, 2->4 via ENABLES
        assert set(reachable) == {2, 4}


class TestPathValidation:
    """Test path validity and properties."""

    def test_path_continuity(self, chain_graph: GraphEngine):
        """Test that path steps are continuous."""
        path = chain_graph.find_shortest_path(1, 5)
        assert path is not None

        # Each step should connect to the next
        for i in range(len(path.steps) - 1):
            current_step = path.steps[i]
            next_step = path.steps[i + 1]
            assert current_step.to_node_id == next_step.from_node_id

    def test_path_weight_calculation(self, complex_graph: GraphEngine):
        """Test that path weights are calculated correctly."""
        path = complex_graph.find_shortest_path(1, 4)
        assert path is not None

        # Total weight should be sum of edge weights
        total_weight = sum(step.edge.weight for step in path.steps)
        assert abs(path.total_weight - total_weight) < 0.001  # Floating point comparison

    def test_path_depth_tracking(self, tree_graph: GraphEngine):
        """Test that path depth is tracked correctly."""
        path = tree_graph.find_shortest_path(1, 4)
        assert path is not None

        # Each step should have correct depth
        for i, step in enumerate(path.steps):
            assert step.depth == i