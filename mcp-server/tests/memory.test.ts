/**
 * Tests for memory management tools.
 */

import { describe, expect, test } from 'bun:test';
import {
  handleMemRead,
  handleMemSearch,
  handleMemWrite,
  memoryTools,
} from '../src/tools/memory.js';

describe('Memory Tools', () => {
  test('memory tools are defined', () => {
    expect(memoryTools).toBeDefined();
    expect(memoryTools.length).toBe(3);
    expect(memoryTools.map((t) => t.name)).toEqual(['mem_read', 'mem_write', 'mem_search']);
  });

  test('mem_read tool schema is valid', () => {
    const tool = memoryTools.find((t) => t.name === 'mem_read');
    expect(tool).toBeDefined();
    expect(tool?.inputSchema).toBeDefined();
    expect(tool?.inputSchema.type).toBe('object');
    expect(tool?.inputSchema.properties).toBeDefined();
    expect(tool?.inputSchema.properties?.id).toBeDefined();
    expect(tool?.inputSchema.properties?.permalink).toBeDefined();
    expect(tool?.inputSchema.properties?.query).toBeDefined();
  });

  test('mem_write tool schema is valid', () => {
    const tool = memoryTools.find((t) => t.name === 'mem_write');
    expect(tool).toBeDefined();
    expect(tool?.inputSchema).toBeDefined();
    expect(tool?.inputSchema.type).toBe('object');
    expect(tool?.inputSchema.properties).toBeDefined();
    expect(tool?.inputSchema.properties?.relative_path).toBeDefined();
    expect(tool?.inputSchema.properties?.title).toBeDefined();
    expect(tool?.inputSchema.properties?.content).toBeDefined();
    expect(tool?.inputSchema.required).toContain('relative_path');
    expect(tool?.inputSchema.required).toContain('title');
    expect(tool?.inputSchema.required).toContain('content');
  });

  test('mem_search tool schema is valid', () => {
    const tool = memoryTools.find((t) => t.name === 'mem_search');
    expect(tool).toBeDefined();
    expect(tool?.inputSchema).toBeDefined();
    expect(tool?.inputSchema.type).toBe('object');
    expect(tool?.inputSchema.properties).toBeDefined();
    expect(tool?.inputSchema.properties?.query).toBeDefined();
    expect(tool?.inputSchema.required).toContain('query');
  });

  // Note: Integration tests would require a running backend API
  // These are skipped for now but can be enabled when backend is available
  test.skip('handleMemRead with ID', async () => {
    // Requires running backend
    const result = await handleMemRead({ id: 1 });
    expect(result).toBeDefined();
    expect(result.content).toBeDefined();
    expect(result.note).toBeDefined();
  });

  test.skip('handleMemWrite creates note', async () => {
    // Requires running backend
    const result = await handleMemWrite({
      relative_path: 'test.md',
      title: 'Test Note',
      content: '# Test\n\nContent',
    });
    expect(result).toBeDefined();
    expect(result.note).toBeDefined();
    expect(result.message).toContain('created');
  });

  test.skip('handleMemSearch finds notes', async () => {
    // Requires running backend
    const result = await handleMemSearch({ query: 'test' });
    expect(result).toBeDefined();
    expect(result.results).toBeDefined();
    expect(Array.isArray(result.results)).toBe(true);
    expect(result.total).toBeGreaterThanOrEqual(0);
  });
});
