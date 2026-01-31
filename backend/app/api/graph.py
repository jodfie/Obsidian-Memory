"""Graph query API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_markdown_parser, get_search_index, get_vault_manager
from app.models.graph import (
    Graph,
    Node,
    Edge,
    TraversalQuery,
    BacklinkItem,
    BacklinkResponse,
    NodeCentrality,
    GraphStats,
    HubNode,
)
from app.services.graph_engine import GraphEngine
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex
from app.services.vault_manager import VaultManager
from app.utils.cache import get_cache

router = APIRouter(prefix="/api/graph", tags=["graph"])
cache = get_cache()


@router.get("")
async def get_graph(
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
) -> dict[str, Any]:
    """Get the full knowledge graph.

    Returns:
        Graph structure with nodes and edges
    """
    # Check cache first
    cache_key = "graph:full"
    cached_graph = cache.get(cache_key)
    if cached_graph:
        return cached_graph
    
    await search_index.initialize()
    
    # Build graph from indexed notes
    engine = GraphEngine()
    
    # Get all notes from index (limit to prevent memory issues)
    from app.models.search import SearchQuery, SortOrder
    
    query = SearchQuery(query="", limit=1000, sort=SortOrder.UPDATED_DESC)
    results = await search_index.search(query)
    
    for result in results.results:
        try:
            # Get note content from vault
            note_content = await vault_manager.read_file(
                result.vault_name, result.relative_path
            )
            
            # Parse note
            parsed = markdown_parser.parse(note_content)
            
            # Create indexed note structure
            from app.models.search import IndexedNote
            indexed = IndexedNote(
                vault_name=result.vault_name,
                relative_path=result.relative_path,
                title=result.title,
                note_type=result.note_type,
                project=result.project,
                content=note_content,
                tags=result.tags,
                file_hash="",  # Simplified - would compute hash in production
            )
            
            # Add to graph
            engine.add_note(result.note_id, indexed, parsed)
        except Exception:
            # Skip notes that can't be loaded/parsed
            continue
    
    # Resolve edges
    engine.resolve_edges()
    
    # Convert to API response format
    graph = engine.get_graph()
    nodes = [
        {
            "id": node.id,
            "title": node.title,
            "permalink": node.permalink,
            "vault_name": node.vault_name,
            "note_type": node.note_type,
            "project": node.project,
            "tags": node.tags,
        }
        for node in graph.nodes.values()
    ]
    
    edges = [
        {
            "source": edge.source_id,
            "target": edge.target_id,
            "target_title": edge.target_title,
            "type": edge.edge_type.value,
            "context": edge.context,
            "weight": edge.weight,
        }
        for edge in graph.edges
        if edge.target_id is not None  # Only include resolved edges
    ]
    
    graph_data = {
        "nodes": nodes,
        "edges": edges,
    }
    
    # Cache for 5 minutes
    cache.set(cache_key, graph_data, ttl=300)
    
    return graph_data


@router.get("/nodes")
async def list_nodes(
    limit: int = 100,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """List all nodes in the graph.

    Args:
        limit: Maximum number of nodes to return

    Returns:
        List of nodes
    """
    # Enforce maximum limit
    limit = min(limit, 500)
    
    await search_index.initialize()
    
    # Get recent notes as nodes
    recent_notes = await search_index.get_recent_notes(limit=limit)
    
    nodes = [
        {
            "id": note.note_id,
            "title": note.title,
            "permalink": note.permalink,
            "vault_name": note.vault_name,
            "note_type": note.note_type,
            "project": note.project,
            "tags": note.tags,
        }
        for note in recent_notes
    ]
    
    return {"nodes": nodes}


@router.get("/edges")
async def list_edges(
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
) -> dict[str, Any]:
    """List all edges in the graph.

    Returns:
        List of edges
    """
    # Use the same graph building logic as get_graph
    graph_response = await get_graph(search_index, vault_manager, markdown_parser)
    return {"edges": graph_response["edges"]}


@router.get("/nodes/{node_id}/neighbors")
async def get_neighbors(
    node_id: int,
    direction: str = "both",
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """Get neighbors of a node.

    Args:
        node_id: Node ID
        direction: Edge direction (outgoing, incoming, both)

    Returns:
        List of neighbor nodes
    """
    await search_index.initialize()

    # Get the note
    note = await search_index.get_note_by_id(node_id)
    if not note:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    # For now, return empty neighbors
    # Full implementation would build graph and use GraphEngine.get_neighbors
    # This is expensive to compute on-demand, so should be cached
    return {
        "node_id": node_id,
        "neighbors": [],
        "direction": direction,
        "message": "Graph neighbor lookup - full implementation requires graph caching",
    }


@router.post("/traverse")
async def traverse_graph(
    request: TraversalQuery,
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
) -> dict[str, Any]:
    """Traverse the graph using BFS or DFS.

    Args:
        request: Traversal parameters

    Returns:
        Traversal results with visited nodes and paths
    """
    await search_index.initialize()

    # Verify start node exists
    start_note = await search_index.get_note_by_id(request.start_node_id)
    if not start_note:
        raise HTTPException(status_code=404, detail=f"Start node {request.start_node_id} not found")

    # Build graph from indexed notes
    engine = GraphEngine()

    from app.models.search import SearchQuery, SortOrder, IndexedNote

    query = SearchQuery(query="", limit=500, sort=SortOrder.UPDATED_DESC)
    results = await search_index.search(query)

    for result in results.results:
        try:
            note_content = await vault_manager.read_file(
                result.relative_path, vault=result.vault_name
            )
            parsed = markdown_parser.parse(note_content)

            indexed = IndexedNote(
                vault_name=result.vault_name,
                relative_path=result.relative_path,
                title=result.title,
                note_type=result.note_type,
                project=result.project,
                content=note_content,
                tags=result.tags,
                file_hash="",
            )
            engine.add_note(result.note_id, indexed, parsed)
        except Exception:
            continue

    engine.resolve_edges()

    # Perform traversal using GraphEngine methods
    if request.method == "bfs":
        result = engine.traverse_bfs(request)
    else:
        result = engine.traverse_dfs(request)

    return {
        "start_node_id": request.start_node_id,
        "target_node_id": request.target_node_id,
        "method": request.method,
        "visited_nodes": result.visited_nodes,
        "paths": [[step.to_node_id for step in path.steps] for path in result.paths],
        "depth_reached": result.depth_reached,
    }


@router.get("/nodes/{node_id}/similar")
async def get_similar_notes(
    node_id: int,
    limit: int = 10,
    method: str = "hybrid",
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """Find notes similar to the given node using enhanced similarity methods.

    Args:
        node_id: Source node ID
        limit: Maximum number of similar notes
        method: Similarity method:
            - 'content': FTS-based content similarity only
            - 'graph': Tag and relation-based similarity only
            - 'hybrid': Combined weighted similarity (default)

    Returns:
        List of similar notes with scores
    """
    await search_index.initialize()

    # Validate method parameter
    if method not in ["content", "graph", "hybrid"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid method '{method}'. Must be 'content', 'graph', or 'hybrid'"
        )

    # Use the enhanced similarity search method
    similar_notes = await search_index.search_similar_enhanced(
        note_id=node_id,
        limit=limit,
        method=method
    )

    return {
        "source_node_id": node_id,
        "method": method,
        "similar_notes": similar_notes,
        "count": len(similar_notes),
    }


@router.get("/nodes/{node_id}/backlinks")
async def get_backlinks(
    node_id: int,
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
) -> BacklinkResponse:
    """Get backlinks (notes that link TO the given note) with context.

    Args:
        node_id: Target node ID to get backlinks for

    Returns:
        BacklinkResponse with source note details and edge context
    """
    await search_index.initialize()

    # Verify target node exists
    target_note = await search_index.get_note_by_id(node_id)
    if not target_note:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    # Check cache first
    cache_key = f"graph:backlinks:{node_id}"
    cached_response = cache.get(cache_key)
    if cached_response:
        return BacklinkResponse(**cached_response)

    # Build graph to compute backlinks
    engine = GraphEngine()

    # Get notes from index (use reasonable limit for performance)
    from app.models.search import SearchQuery, SortOrder, IndexedNote

    query = SearchQuery(query="", limit=500, sort=SortOrder.UPDATED_DESC)
    results = await search_index.search(query)

    for result in results.results:
        try:
            # Get note content from vault
            vault_file = await vault_manager.read_file(
                result.relative_path, vault=result.vault_name
            )

            # Parse note
            parsed = markdown_parser.parse(vault_file.content)

            # Create indexed note structure
            indexed = IndexedNote(
                vault_name=result.vault_name,
                relative_path=result.relative_path,
                title=result.title,
                note_type=result.note_type,
                project=result.project,
                content=vault_file.content,
                tags=result.tags,
                file_hash="",  # Simplified for now
            )

            # Add to graph
            engine.add_note(result.note_id, indexed, parsed)
        except Exception:
            # Skip notes that can't be loaded/parsed
            continue

    # Resolve edges
    engine.resolve_edges()

    # Get incoming edges using GraphEngine method
    incoming_edges = engine.get_incoming_edges(node_id)

    # Build backlink items with source node details
    backlink_items = []
    for edge in incoming_edges:
        source_node = engine.graph.nodes.get(edge.source_id)
        if source_node:
            backlink_item = BacklinkItem(
                source_node=source_node,
                edge_type=edge.edge_type,
                context=edge.context,
                weight=edge.weight,
            )
            backlink_items.append(backlink_item)

    # Sort by weight (descending) for relevance
    backlink_items.sort(key=lambda x: x.weight, reverse=True)

    # Create response
    response = BacklinkResponse(
        target_node_id=node_id,
        target_title=target_note.title,
        backlinks=backlink_items,
        total_count=len(backlink_items),
    )

    # Cache for 5 minutes
    cache.set(cache_key, response.model_dump(), ttl=300)

    return response


@router.get("/stats")
async def get_graph_stats(
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
) -> GraphStats:
    """Get comprehensive graph statistics.

    Returns statistics including:
    - Total nodes and edges
    - Edge type distribution
    - Orphan nodes (no connections)
    - Average degree
    - Most connected nodes (hubs)
    """
    # Check cache first
    cache_key = "graph:stats"
    cached_stats = cache.get(cache_key)
    if cached_stats:
        return GraphStats(**cached_stats)

    await search_index.initialize()

    # Build graph
    engine = GraphEngine()

    # Load up to 500 notes for stats
    from app.models.search import SearchQuery, SortOrder

    query = SearchQuery(query="", limit=500, sort=SortOrder.UPDATED_DESC)
    results = await search_index.search(query)

    for result in results.results:
        try:
            # Get note content
            note_content = await vault_manager.read_file(
                result.vault_name, result.relative_path
            )

            # Parse note
            parsed = markdown_parser.parse(note_content)

            # Create indexed note
            from app.models.search import IndexedNote
            indexed = IndexedNote(
                vault_name=result.vault_name,
                relative_path=result.relative_path,
                title=result.title,
                note_type=result.note_type,
                project=result.project,
                content=note_content,
                tags=result.tags,
                file_hash="",
            )

            # Add to graph
            engine.add_note(result.note_id, indexed, parsed)
        except Exception:
            continue

    # Resolve edges
    engine.resolve_edges()

    # Get stats
    stats_dict = engine.get_graph_stats()

    # Convert to response model
    stats = GraphStats(
        total_nodes=stats_dict["total_nodes"],
        total_edges=stats_dict["total_edges"],
        edge_type_distribution=stats_dict["edge_type_distribution"],
        orphan_nodes=stats_dict["orphan_nodes"],
        orphan_count=stats_dict["orphan_count"],
        average_degree=stats_dict["average_degree"],
        graph_density=stats_dict["graph_density"],
        top_hubs=stats_dict["top_hubs"],
    )

    # Cache for 5 minutes
    cache.set(cache_key, stats.model_dump(), ttl=300)

    return stats


@router.get("/nodes/{node_id}/centrality")
async def get_node_centrality(
    node_id: int,
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
) -> NodeCentrality:
    """Get centrality metrics for a specific node.

    Calculates degree centrality (incoming + outgoing edges),
    plus breakdown by edge types.

    Args:
        node_id: ID of node to analyze

    Returns:
        NodeCentrality with metrics

    Raises:
        HTTPException: If node not found
    """
    # Check cache first
    cache_key = f"graph:centrality:{node_id}"
    cached_centrality = cache.get(cache_key)
    if cached_centrality:
        return NodeCentrality(**cached_centrality)

    await search_index.initialize()

    # Verify node exists
    target_note = await search_index.get_note_by_id(node_id)
    if not target_note:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    # Build graph
    engine = GraphEngine()

    # Load up to 500 notes
    from app.models.search import SearchQuery, SortOrder

    query = SearchQuery(query="", limit=500, sort=SortOrder.UPDATED_DESC)
    results = await search_index.search(query)

    for result in results.results:
        try:
            # Get note content
            note_content = await vault_manager.read_file(
                result.vault_name, result.relative_path
            )

            # Parse note
            parsed = markdown_parser.parse(note_content)

            # Create indexed note
            from app.models.search import IndexedNote
            indexed = IndexedNote(
                vault_name=result.vault_name,
                relative_path=result.relative_path,
                title=result.title,
                note_type=result.note_type,
                project=result.project,
                content=note_content,
                tags=result.tags,
                file_hash="",
            )

            # Add to graph
            engine.add_note(result.note_id, indexed, parsed)
        except Exception:
            continue

    # Resolve edges
    engine.resolve_edges()

    # Get centrality metrics
    centrality_dict = engine.get_node_centrality(node_id)

    # Get node for title/permalink
    node = engine.get_node(node_id)

    # Convert to response model
    centrality = NodeCentrality(
        node_id=centrality_dict["node_id"],
        title=node.title if node else None,
        permalink=node.permalink if node else None,
        degree_centrality=centrality_dict["degree_centrality"],
        in_degree=centrality_dict["in_degree"],
        out_degree=centrality_dict["out_degree"],
        normalized_centrality=centrality_dict["normalized_centrality"],
        outgoing_by_type=centrality_dict["outgoing_by_type"],
        incoming_by_type=centrality_dict["incoming_by_type"],
    )

    # Cache for 5 minutes
    cache.set(cache_key, centrality.model_dump(), ttl=300)

    return centrality
