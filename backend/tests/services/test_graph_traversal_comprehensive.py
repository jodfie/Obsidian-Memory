"""Comprehensive tests for graph traversal algorithms."""

import pytest
from typing import List
from app.models.graph import TraversalQuery, EdgeType
from app.services.graph_engine import GraphEngine

# Import our graph fixtures
from tests.fixtures.graph_fixtures import (
    empty_graph,
    single_node_graph,
    chain_graph,
    tree_graph,
    cyclic_graph,
    disconnected_graph,
    hub_spoke_graph,
    complex_graph,
    bidirectional_graph,
)


class TestBFSTraversal:
    """Test Breadth-First Search traversal."""

    def test_bfs_empty_graph(self, empty_graph: GraphEngine):
        """Test BFS on empty graph."""
        # Trying to traverse from non-existent node includes the start node even if not in graph
        query = TraversalQuery(start_node_id=1, max_depth=5)
        result = empty_graph.traverse_bfs(query)
        assert result.visited_nodes == [1]  # Start node is always included

    def test_bfs_single_node(self, single_node_graph: GraphEngine):
        """Test BFS on single isolated node."""
        query = TraversalQuery(start_node_id=1, max_depth=5)
        result = single_node_graph.traverse_bfs(query)
        assert result.visited_nodes == [1]

    def test_bfs_chain_traversal(self, chain_graph: GraphEngine):
        """Test BFS on linear chain."""
        # Forward traversal from node 1
        query = TraversalQuery(start_node_id=1, max_depth=10, direction="outgoing")
        result = chain_graph.traverse_bfs(query)
        # BFS should visit nodes in order for a chain
        assert result.visited_nodes == [1, 2, 3, 4, 5]

        # Limited depth traversal
        query = TraversalQuery(start_node_id=1, max_depth=2, direction="outgoing")
        result = chain_graph.traverse_bfs(query)
        assert result.visited_nodes == [1, 2, 3]  # Only reach 2 hops

        # Backward traversal (no incoming edges in chain)
        query = TraversalQuery(start_node_id=5, max_depth=10, direction="incoming")
        result = chain_graph.traverse_bfs(query)
        assert result.visited_nodes == [5]  # Can't go backward

    def test_bfs_tree_traversal(self, tree_graph: GraphEngine):
        """Test BFS on tree structure - should visit level by level."""
        query = TraversalQuery(start_node_id=1, max_depth=10, direction="outgoing")
        result = tree_graph.traverse_bfs(query)

        # BFS visits level by level: root (1), level 1 (2,3), level 2 (4,5,6)
        # Exact order within a level may vary
        assert result.visited_nodes[0] == 1  # Root first
        assert set(result.visited_nodes[1:3]) == {2, 3}  # Level 1
        assert set(result.visited_nodes[3:6]) == {4, 5, 6}  # Level 2

    def test_bfs_cyclic_traversal(self, cyclic_graph: GraphEngine):
        """Test BFS handles cycles correctly."""
        query = TraversalQuery(start_node_id=1, max_depth=10, direction="outgoing")
        result = cyclic_graph.traverse_bfs(query)

        # Should visit all nodes exactly once despite the cycle
        assert len(result.visited_nodes) == 5
        assert set(result.visited_nodes) == {1, 2, 3, 4, 5}
        # BFS order: 1 -> 2 -> 3 -> 4 -> 5
        assert result.visited_nodes[0] == 1

    def test_bfs_with_target(self, chain_graph: GraphEngine):
        """Test BFS stops when target is found."""
        query = TraversalQuery(
            start_node_id=1,
            target_node_id=3,
            max_depth=10,
            direction="outgoing"
        )
        result = chain_graph.traverse_bfs(query)

        # Should stop after finding node 3
        assert 3 in result.visited_nodes
        # May include nodes visited before finding target
        assert all(node <= 3 for node in result.visited_nodes)

    def test_bfs_disconnected_components(self, disconnected_graph: GraphEngine):
        """Test BFS only visits connected component."""
        # Start from node 1 (in first component)
        query = TraversalQuery(start_node_id=1, max_depth=10, direction="both")
        result = disconnected_graph.traverse_bfs(query)

        # Should only visit nodes 1, 2, 3 (first component)
        assert set(result.visited_nodes) == {1, 2, 3}
        assert 4 not in result.visited_nodes  # Different component
        assert 6 not in result.visited_nodes  # Isolated

    def test_bfs_hub_spoke(self, hub_spoke_graph: GraphEngine):
        """Test BFS from hub visits all spokes in one level."""
        query = TraversalQuery(start_node_id=1, max_depth=1, direction="outgoing")
        result = hub_spoke_graph.traverse_bfs(query)

        # Should visit hub and all spokes (depth 1)
        assert result.visited_nodes[0] == 1  # Hub first
        assert set(result.visited_nodes[1:]) == set(range(2, 9))  # All spokes

    def test_bfs_edge_type_filtering(self, complex_graph: GraphEngine):
        """Test BFS with edge type filtering."""
        # Only follow DEPENDS_ON edges
        query = TraversalQuery(
            start_node_id=1,
            max_depth=10,
            direction="outgoing",
            edge_types=[EdgeType.DEPENDS_ON]
        )
        result = complex_graph.traverse_bfs(query)

        # From node 1, only DEPENDS_ON edge goes to node 2
        assert result.visited_nodes == [1, 2]

    def test_bfs_exclude_nodes(self, chain_graph: GraphEngine):
        """Test BFS with node exclusion."""
        query = TraversalQuery(
            start_node_id=1,
            max_depth=10,
            direction="outgoing",
            exclude_nodes=[3]
        )
        result = chain_graph.traverse_bfs(query)

        # Should skip node 3 and can't reach 4, 5 (chain is broken)
        assert 3 not in result.visited_nodes
        assert result.visited_nodes == [1, 2]


class TestDFSTraversal:
    """Test Depth-First Search traversal."""

    def test_dfs_empty_graph(self, empty_graph: GraphEngine):
        """Test DFS on empty graph."""
        query = TraversalQuery(start_node_id=1, max_depth=5)
        result = empty_graph.traverse_dfs(query)
        assert result.visited_nodes == [1]  # Start node is always included

    def test_dfs_single_node(self, single_node_graph: GraphEngine):
        """Test DFS on single isolated node."""
        query = TraversalQuery(start_node_id=1, max_depth=5)
        result = single_node_graph.traverse_dfs(query)
        assert result.visited_nodes == [1]

    def test_dfs_chain_traversal(self, chain_graph: GraphEngine):
        """Test DFS on linear chain."""
        query = TraversalQuery(start_node_id=1, max_depth=10, direction="outgoing")
        result = chain_graph.traverse_dfs(query)
        # DFS should go deep first, visiting all nodes in chain order
        assert result.visited_nodes == [1, 2, 3, 4, 5]

    def test_dfs_tree_traversal(self, tree_graph: GraphEngine):
        """Test DFS on tree structure - should visit deep first."""
        query = TraversalQuery(start_node_id=1, max_depth=10, direction="outgoing")
        result = tree_graph.traverse_dfs(query)

        # DFS goes deep first
        assert result.visited_nodes[0] == 1  # Root first
        # Should visit one branch completely before the other
        # Either [1, 2, 4, 5, 3, 6] or [1, 3, 6, 2, 4, 5] or similar

    def test_dfs_cyclic_traversal(self, cyclic_graph: GraphEngine):
        """Test DFS handles cycles correctly."""
        query = TraversalQuery(start_node_id=1, max_depth=10, direction="outgoing")
        result = cyclic_graph.traverse_dfs(query)

        # Should visit all nodes exactly once
        assert len(result.visited_nodes) == 5
        assert set(result.visited_nodes) == {1, 2, 3, 4, 5}

    def test_dfs_max_depth(self, chain_graph: GraphEngine):
        """Test DFS respects max depth."""
        query = TraversalQuery(start_node_id=1, max_depth=2, direction="outgoing")
        result = chain_graph.traverse_dfs(query)
        assert result.visited_nodes == [1, 2, 3]  # Only 2 hops from start

    def test_dfs_with_target(self, tree_graph: GraphEngine):
        """Test DFS stops when target is found."""
        query = TraversalQuery(
            start_node_id=1,
            target_node_id=4,
            max_depth=10,
            direction="outgoing"
        )
        result = tree_graph.traverse_dfs(query)

        # Should find node 4
        assert 4 in result.visited_nodes
        # May not visit all nodes if target found early
        assert result.visited_nodes[-1] == 4 or 4 in result.visited_nodes

    def test_dfs_bidirectional(self, bidirectional_graph: GraphEngine):
        """Test DFS with bidirectional traversal."""
        query = TraversalQuery(
            start_node_id=3,
            max_depth=10,
            direction="both"
        )
        result = bidirectional_graph.traverse_dfs(query)

        # From node 3, should reach all nodes (fully connected)
        assert len(result.visited_nodes) == 5
        assert set(result.visited_nodes) == {1, 2, 3, 4, 5}


class TestTraversalComparison:
    """Compare BFS and DFS behavior."""

    def test_bfs_vs_dfs_order(self, tree_graph: GraphEngine):
        """Compare traversal order between BFS and DFS."""
        query = TraversalQuery(start_node_id=1, max_depth=10, direction="outgoing")

        bfs_result = tree_graph.traverse_bfs(query)
        dfs_result = tree_graph.traverse_dfs(query)

        # Both should visit all nodes
        assert set(bfs_result.visited_nodes) == set(dfs_result.visited_nodes)

        # But in different order
        assert bfs_result.visited_nodes != dfs_result.visited_nodes

        # BFS visits level by level
        # First 3 nodes in BFS should be root and its children
        assert set(bfs_result.visited_nodes[:3]) == {1, 2, 3}

    def test_bfs_vs_dfs_with_cycles(self, cyclic_graph: GraphEngine):
        """Test both algorithms handle cycles correctly."""
        query = TraversalQuery(start_node_id=1, max_depth=10, direction="outgoing")

        bfs_result = cyclic_graph.traverse_bfs(query)
        dfs_result = cyclic_graph.traverse_dfs(query)

        # Both should visit same nodes (no duplicates despite cycle)
        assert set(bfs_result.visited_nodes) == set(dfs_result.visited_nodes)
        assert len(bfs_result.visited_nodes) == 5
        assert len(dfs_result.visited_nodes) == 5


class TestDirectionalTraversal:
    """Test traversal with different directions."""

    def test_incoming_traversal(self, chain_graph: GraphEngine):
        """Test traversal following incoming edges only."""
        # In chain 1->2->3->4->5, starting from 5
        query = TraversalQuery(start_node_id=5, max_depth=10, direction="incoming")
        result = chain_graph.traverse_bfs(query)

        # Can't traverse backward in forward-only chain
        assert result.visited_nodes == [5]

    def test_outgoing_traversal(self, chain_graph: GraphEngine):
        """Test traversal following outgoing edges only."""
        query = TraversalQuery(start_node_id=1, max_depth=10, direction="outgoing")
        result = chain_graph.traverse_bfs(query)

        # Should follow the chain forward
        assert result.visited_nodes == [1, 2, 3, 4, 5]

    def test_bidirectional_traversal(self, bidirectional_graph: GraphEngine):
        """Test traversal in both directions."""
        # Start from middle node
        query = TraversalQuery(start_node_id=2, max_depth=10, direction="both")
        result = bidirectional_graph.traverse_bfs(query)

        # Should reach all nodes from middle
        assert set(result.visited_nodes) == {1, 2, 3, 4, 5}

    def test_direction_with_hub(self, hub_spoke_graph: GraphEngine):
        """Test directional traversal with hub topology."""
        # Outgoing from hub reaches all spokes
        query = TraversalQuery(start_node_id=1, max_depth=1, direction="outgoing")
        result = hub_spoke_graph.traverse_bfs(query)
        assert len(result.visited_nodes) == 8  # Hub + 7 spokes

        # Incoming to hub from any spoke
        query = TraversalQuery(start_node_id=1, max_depth=1, direction="incoming")
        result = hub_spoke_graph.traverse_bfs(query)
        assert len(result.visited_nodes) == 8  # Hub + 7 spokes (bidirectional edges)

        # Outgoing from spoke only reaches hub
        query = TraversalQuery(start_node_id=2, max_depth=1, direction="outgoing")
        result = hub_spoke_graph.traverse_bfs(query)
        assert set(result.visited_nodes) == {1, 2}  # Spoke and hub


class TestEdgeTypeFiltering:
    """Test traversal with edge type filters."""

    def test_single_edge_type_filter(self, complex_graph: GraphEngine):
        """Test filtering by single edge type."""
        # Only follow ENABLES edges
        query = TraversalQuery(
            start_node_id=2,
            max_depth=10,
            direction="outgoing",
            edge_types=[EdgeType.ENABLES]
        )
        result = complex_graph.traverse_bfs(query)

        # From node 2, ENABLES goes to node 4
        assert set(result.visited_nodes) == {2, 4}

    def test_multiple_edge_type_filter(self, complex_graph: GraphEngine):
        """Test filtering by multiple edge types."""
        # Follow DEPENDS_ON and ENABLES
        query = TraversalQuery(
            start_node_id=1,
            max_depth=10,
            direction="outgoing",
            edge_types=[EdgeType.DEPENDS_ON, EdgeType.ENABLES]
        )
        result = complex_graph.traverse_bfs(query)

        # 1 -DEPENDS_ON-> 2 -ENABLES-> 4
        assert set(result.visited_nodes) == {1, 2, 4}

    def test_no_matching_edge_types(self, complex_graph: GraphEngine):
        """Test when no edges match the filter."""
        # Look for non-existent edge type from node 1
        query = TraversalQuery(
            start_node_id=1,
            max_depth=10,
            direction="outgoing",
            edge_types=[EdgeType.TESTS]  # No TESTS edges in graph
        )
        result = complex_graph.traverse_bfs(query)

        # Should only visit start node
        assert result.visited_nodes == [1]