/**
 * Graph traversal tools for Obsidian-Memory MCP server.
 */

import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { ApiClient } from '../client.js';

const API_BASE_URL = process.env.OBSIDIAN_MEMORY_API_URL || 'http://localhost:8000';
const client = new ApiClient(API_BASE_URL);

/**
 * Tool definitions for graph operations.
 */
export const graphTools: Tool[] = [
  {
    name: 'graph_traverse',
    description:
      'Traverse the knowledge graph from a starting note using BFS or DFS. Returns visited nodes and optional paths.',
    inputSchema: {
      type: 'object',
      properties: {
        start_node_id: {
          type: 'number',
          description: 'Starting node ID',
        },
        target_node_id: {
          type: 'number',
          description: 'Optional target node ID (stops when found)',
        },
        method: {
          type: 'string',
          enum: ['bfs', 'dfs'],
          description: 'Traversal method: breadth-first (bfs) or depth-first (dfs)',
        },
        max_depth: {
          type: 'number',
          description: 'Maximum traversal depth (default: 10)',
        },
        direction: {
          type: 'string',
          enum: ['outgoing', 'incoming', 'both'],
          description: 'Edge direction to traverse',
        },
        edge_types: {
          type: 'array',
          items: { type: 'string' },
          description: 'Filter by edge types (e.g., ["depends_on", "enables"])',
        },
        exclude_nodes: {
          type: 'array',
          items: { type: 'number' },
          description: 'Node IDs to exclude from traversal',
        },
      },
      required: ['start_node_id'],
    },
  },
  {
    name: 'graph_similar',
    description:
      'Find notes similar to a given note using graph structure and content similarity.',
    inputSchema: {
      type: 'object',
      properties: {
        note_id: {
          type: 'number',
          description: 'Source note ID',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of similar notes to return (default: 10)',
        },
        method: {
          type: 'string',
          enum: ['graph', 'content', 'hybrid'],
          description:
            'Similarity method: graph structure, content similarity, or both',
        },
      },
      required: ['note_id'],
    },
  },
];

/**
 * Handle graph_traverse tool call.
 */
export async function handleGraphTraverse(args: {
  start_node_id: number;
  target_node_id?: number;
  method?: string;
  max_depth?: number;
  direction?: string;
  edge_types?: string[];
  exclude_nodes?: number[];
}): Promise<{
  visited_nodes: unknown[];
  paths: unknown[];
  depth_reached: number;
}> {
  // Note: This would require graph API endpoints
  // For now, use search-based approximation
  // TODO: Implement when graph API is available

  const startNote = await client.getNoteById(args.start_node_id);
  if (!startNote) {
    throw new Error(`Note with ID ${args.start_node_id} not found`);
  }

  // Use search to find similar/related notes
  const results = await client.searchNotes({
    query: startNote.title,
    limit: args.max_depth || 10,
  });

  return {
    visited_nodes: results.notes.map((n) => n.note_id),
    paths: [],
    depth_reached: 1,
  };
}

/**
 * Handle graph_similar tool call.
 */
export async function handleGraphSimilar(args: {
  note_id: number;
  limit?: number;
  method?: string;
}): Promise<{
  similar_notes: unknown[];
  scores: unknown[];
}> {
  const sourceNote = await client.getNoteById(args.note_id);
  if (!sourceNote) {
    throw new Error(`Note with ID ${args.note_id} not found`);
  }

  // Use search to find similar notes
  const results = await client.searchNotes({
    query: sourceNote.title,
    limit: args.limit || 10,
  });

  // Filter out the source note
  const similar = results.notes.filter((n) => n.note_id !== args.note_id);

  return {
    similar_notes: similar,
    scores: similar.map((n) => ({ note_id: n.note_id, score: n.score })),
  };
}
