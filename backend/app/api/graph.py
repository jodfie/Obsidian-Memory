"""Graph query API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_markdown_parser, get_search_index, get_vault_manager
from app.models.graph import Graph, Node, Edge, TraversalQuery
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
