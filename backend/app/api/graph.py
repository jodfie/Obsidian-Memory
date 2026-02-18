"""Graph query API endpoints."""

import asyncio
import logging
import uuid
from typing import Any

# Chunk size for relation inference to avoid oversized AI payloads; delay between chunks for rate limiting
INFER_RELATIONS_BATCH_SIZE = 20
INFER_RELATIONS_DELAY_SECONDS = 1.0

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import (
    get_ai_processor,
    get_markdown_parser,
    get_search_index,
    get_vault_manager,
)
from app.models.graph import (
    Graph,
    Node,
    Edge,
    EdgeSource,
    EdgeType,
    TraversalQuery,
    BacklinkItem,
    BacklinkResponse,
    NodeCentrality,
    GraphStats,
    HubNode,
)
from app.services.ai_processor import AIProcessor
from app.services.graph_engine import GraphEngine
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex
from app.services.vault_manager import VaultManager
from app.utils.cache import get_cache

logger = logging.getLogger(__name__)

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
    
    query = SearchQuery(query="*", limit=1000, sort=SortOrder.UPDATED_DESC)
    results = await search_index.search(query)

    for result in results.results:
        try:
            # Get note content from vault (path first, vault= second)
            vault_file = await vault_manager.read_file(
                result.relative_path, vault=result.vault_name
            )
            note_content = vault_file.content

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

    # Merge inferred relations from DB into the graph
    inferred = await search_index.get_inferred_relations(
        include_promoted=True, limit=500
    )
    if inferred:
        node_ids = set(engine.get_graph().nodes)
        engine.add_inferred_edges_from_records(inferred, node_ids=node_ids)

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
            "source_type": edge.source_type.value,
            "confidence": edge.confidence,
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

    query = SearchQuery(query="*", limit=500, sort=SortOrder.UPDATED_DESC)
    results = await search_index.search(query)

    for result in results.results:
        try:
            vault_file = await vault_manager.read_file(
                result.relative_path, vault=result.vault_name
            )
            note_content = vault_file.content
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

    query = SearchQuery(query="*", limit=500, sort=SortOrder.UPDATED_DESC)
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

    query = SearchQuery(query="*", limit=500, sort=SortOrder.UPDATED_DESC)
    results = await search_index.search(query)

    for result in results.results:
        try:
            # Get note content from vault (path first, vault= second)
            vault_file = await vault_manager.read_file(
                result.relative_path, vault=result.vault_name
            )
            note_content = vault_file.content

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

    query = SearchQuery(query="*", limit=500, sort=SortOrder.UPDATED_DESC)
    results = await search_index.search(query)

    for result in results.results:
        try:
            # Get note content from vault (path first, vault= second)
            vault_file = await vault_manager.read_file(
                result.relative_path, vault=result.vault_name
            )
            note_content = vault_file.content

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


# -----------------------------------------------------------------------------
# Relation Inference Endpoints
# -----------------------------------------------------------------------------


class InferRelationsRequest(BaseModel):
    """Request model for triggering relation inference."""

    note_ids: list[int] | None = Field(
        default=None,
        description="Specific note IDs to analyze. If None, uses candidate pairs based on shared tags.",
    )
    max_pairs: int = Field(
        default=50, ge=1, le=200, description="Maximum number of pairs to analyze"
    )
    min_confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum confidence to store"
    )


class InferredRelationResponse(BaseModel):
    """Response model for an inferred relation."""

    edge_id: str
    source_note_id: int
    target_note_id: int
    source_title: str
    target_title: str
    relation_type: str
    confidence: float
    reasoning: str | None
    is_promoted: bool
    inferred_at: str


class InferRelationsResponse(BaseModel):
    """Response model for relation inference."""

    inferred_count: int
    relations: list[InferredRelationResponse]
    pairs_analyzed: int


@router.post("/infer-relations", response_model=InferRelationsResponse)
async def infer_relations(
    request: InferRelationsRequest,
    search_index: SearchIndex = Depends(get_search_index),
    vault_manager: VaultManager = Depends(get_vault_manager),
    markdown_parser: MarkdownParser = Depends(get_markdown_parser),
    ai_processor: AIProcessor = Depends(get_ai_processor),
) -> InferRelationsResponse:
    """Trigger AI-powered relation inference for notes.

    Analyzes note pairs to discover semantic relationships based on content
    similarity. Inferred relations are stored separately from explicit relations
    and can be promoted to explicit status.

    Args:
        request: Inference parameters including note IDs and thresholds

    Returns:
        InferRelationsResponse with inferred relations
    """
    await search_index.initialize()

    # Get candidate pairs for inference
    pairs = await search_index.get_candidate_pairs_for_inference(
        note_ids=request.note_ids, limit=request.max_pairs
    )

    if not pairs:
        return InferRelationsResponse(
            inferred_count=0, relations=[], pairs_analyzed=0
        )

    # Build note content pairs for AI analysis.
    # Each tuple is (parsed_source, indexed_source, parsed_target, indexed_target)
    # so AIProcessor.infer_relations() receives the expected 4-tuple shape.
    note_pairs: list[tuple] = []
    for source_id, target_id in pairs:
        try:
            source_note = await search_index.get_note_by_id(source_id)
            target_note = await search_index.get_note_by_id(target_id)

            if not source_note or not target_note:
                continue

            # Get parsed notes for content
            source_content = await vault_manager.read_file(
                source_note.relative_path, vault=source_note.vault_name
            )
            target_content = await vault_manager.read_file(
                target_note.relative_path, vault=target_note.vault_name
            )

            source_parsed = markdown_parser.parse(source_content.content)
            target_parsed = markdown_parser.parse(target_content.content)

            note_pairs.append(
                (source_parsed, source_note, target_parsed, target_note)
            )
        except Exception as e:
            logger.warning(f"Failed to load note pair ({source_id}, {target_id}): {e}")
            continue

    if not note_pairs:
        return InferRelationsResponse(
            inferred_count=0, relations=[], pairs_analyzed=0
        )

    # Map AI flat indices (0,1 = pair 0; 2,3 = pair 1; ...) to actual note IDs.
    def flat_idx_to_note_id(flat_idx: int, pairs: list) -> int | None:
        if flat_idx < 0:
            return None
        pair_idx = flat_idx // 2
        pos = flat_idx % 2
        if pair_idx >= len(pairs):
            return None
        indexed = pairs[pair_idx][1] if pos == 0 else pairs[pair_idx][3]
        return indexed.note_id

    def resolve_titles(
        sid: int, tid: int, pairs: list
    ) -> tuple[str, str]:
        src = next(
            (p[1] if p[1].note_id == sid else p[3] for p in pairs if p[1].note_id == sid or p[3].note_id == sid),
            None,
        )
        tgt = next(
            (p[1] if p[1].note_id == tid else p[3] for p in pairs if p[1].note_id == tid or p[3].note_id == tid),
            None,
        )
        return (src.title if src else "", tgt.title if tgt else "")

    stored_relations: list[InferredRelationResponse] = []
    pairs_analyzed = 0

    # Process in batches to limit payload size and rate-limit AI calls
    for offset in range(0, len(note_pairs), INFER_RELATIONS_BATCH_SIZE):
        chunk = note_pairs[offset : offset + INFER_RELATIONS_BATCH_SIZE]
        if offset > 0:
            await asyncio.sleep(INFER_RELATIONS_DELAY_SECONDS)

        try:
            inferred = await ai_processor.infer_relations(chunk)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"AI inference failed: {e}"
            ) from e

        pairs_analyzed += len(chunk)

        for relation in inferred.relations:
            if relation.confidence < request.min_confidence:
                continue

            source_id = flat_idx_to_note_id(relation.source_note_id, chunk)
            target_id = flat_idx_to_note_id(relation.target_note_id, chunk)
            if source_id is None or target_id is None:
                continue

            edge_id = str(uuid.uuid4())
            _, inferred_at = await search_index.store_inferred_relation(
                edge_id=edge_id,
                source_note_id=source_id,
                target_note_id=target_id,
                relation_type=relation.relation_type,
                confidence=relation.confidence,
                reasoning=relation.reasoning,
            )

            source_title, target_title = resolve_titles(source_id, target_id, chunk)

            stored_relations.append(
                InferredRelationResponse(
                    edge_id=edge_id,
                    source_note_id=source_id,
                    target_note_id=target_id,
                    source_title=source_title,
                    target_title=target_title,
                    relation_type=relation.relation_type,
                    confidence=relation.confidence,
                    reasoning=relation.reasoning,
                    is_promoted=False,
                    inferred_at=inferred_at,
                )
            )

    return InferRelationsResponse(
        inferred_count=len(stored_relations),
        relations=stored_relations,
        pairs_analyzed=pairs_analyzed,
    )


@router.get("/inferred-relations")
async def get_inferred_relations(
    note_id: int | None = None,
    relation_type: str | None = None,
    min_confidence: float = 0.0,
    include_promoted: bool = False,
    limit: int = 100,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """Get inferred relations with optional filtering.

    Args:
        note_id: Optional note ID to filter by (as source or target)
        relation_type: Optional relation type filter
        min_confidence: Minimum confidence threshold
        include_promoted: Whether to include promoted relations
        limit: Maximum results

    Returns:
        List of inferred relations
    """
    await search_index.initialize()

    relations = await search_index.get_inferred_relations(
        note_id=note_id,
        relation_type=relation_type,
        min_confidence=min_confidence,
        include_promoted=include_promoted,
        limit=limit,
    )

    return {"relations": relations, "total": len(relations)}


@router.put("/relations/{edge_id}/promote")
async def promote_relation(
    edge_id: str,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """Promote an inferred relation to explicit.

    This marks the relation as user-approved and sets confidence to 1.0.

    Args:
        edge_id: Edge identifier to promote

    Returns:
        Promoted relation details
    """
    await search_index.initialize()

    # Get the relation first
    relation = await search_index.get_inferred_relation_by_edge_id(edge_id)
    if not relation:
        raise HTTPException(status_code=404, detail="Relation not found")

    if relation["is_promoted"]:
        raise HTTPException(status_code=400, detail="Relation already promoted")

    # Promote it
    success = await search_index.promote_inferred_relation(edge_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to promote relation")

    # Get updated relation
    updated = await search_index.get_inferred_relation_by_edge_id(edge_id)

    return {
        "message": "Relation promoted successfully",
        "relation": updated,
    }


@router.delete("/relations/{edge_id}")
async def delete_relation(
    edge_id: str,
    search_index: SearchIndex = Depends(get_search_index),
) -> dict[str, Any]:
    """Delete an inferred relation.

    Args:
        edge_id: Edge identifier to delete

    Returns:
        Deletion confirmation
    """
    await search_index.initialize()

    success = await search_index.delete_inferred_relation(edge_id)
    if not success:
        raise HTTPException(status_code=404, detail="Relation not found")

    return {"message": "Relation deleted successfully", "edge_id": edge_id}
