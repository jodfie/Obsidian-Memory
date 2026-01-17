/**
 * Tests for graph traversal tools.
 */

import { describe, expect, test } from 'bun:test';
import {
  graphTools,
  handleGraphSimilar,
  handleGraphTraverse,
} from '../src/tools/graph.js';

describe('Graph Tools', () => {
  test('graph tools are defined', () => {
    expect(graphTools).toBeDefined();
    expect(graphTools.length).toBe(2);
    expect(graphTools.map((t) => t.name)).toEqual([
      'graph_traverse',
      'graph_similar',
    ]);
  });

  test('graph_traverse tool schema is valid', () => {
    const tool = graphTools.find((t) => t.name === 'graph_traverse');
    expect(tool).toBeDefined();
    expect(tool?.inputSchema).toBeDefined();
    expect(tool?.inputSchema.type).toBe('object');
    expect(tool?.inputSchema.properties).toBeDefined();
    expect(tool?.inputSchema.properties?.start_node_id).toBeDefined();
    expect(tool?.inputSchema.properties?.method).toBeDefined();
    expect(tool?.inputSchema.required).toContain('start_node_id');
  });

  test('graph_similar tool schema is valid', () => {
    const tool = graphTools.find((t) => t.name === 'graph_similar');
    expect(tool).toBeDefined();
    expect(tool?.inputSchema).toBeDefined();
    expect(tool?.inputSchema.type).toBe('object');
    expect(tool?.inputSchema.properties).toBeDefined();
    expect(tool?.inputSchema.properties?.note_id).toBeDefined();
    expect(tool?.inputSchema.required).toContain('note_id');
  });

  // Note: Integration tests would require a running backend with graph API
  test.skip('handleGraphTraverse with BFS', async () => {
    // Requires running backend with graph API
    const result = await handleGraphTraverse({
      start_node_id: 1,
      method: 'bfs',
      max_depth: 3,
    });
    expect(result).toBeDefined();
    expect(result.visited_nodes).toBeDefined();
  });

  test.skip('handleGraphSimilar finds similar notes', async () => {
    // Requires running backend with graph API
    const result = await handleGraphSimilar({
      note_id: 1,
      limit: 5,
    });
    expect(result).toBeDefined();
    expect(result.similar_notes).toBeDefined();
    expect(Array.isArray(result.similar_notes)).toBe(true);
  });
});
