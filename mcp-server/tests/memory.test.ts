/**
 * Tests for memory management tools.
 */

import { describe, expect, test } from 'bun:test';
import { tools } from '../src/tools.js';
import {
  handleMemRead,
  handleMemSearch,
  handleMemSupersede,
  handleMemWrite,
} from '../src/handlers.js';

// Get memory tools from the tools array
const memoryTools = tools.filter((t) =>
  ['mem_read', 'mem_write', 'mem_search', 'mem_supersede'].includes(t.name)
);

describe('Memory Tools', () => {
  test('memory tools are defined', () => {
    expect(memoryTools).toBeDefined();
    expect(memoryTools.length).toBe(4);
    expect(memoryTools.map((t) => t.name)).toEqual(['mem_read', 'mem_write', 'mem_search', 'mem_supersede']);
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

  test('mem_supersede tool schema is valid', () => {
    const tool = memoryTools.find((t) => t.name === 'mem_supersede');
    expect(tool).toBeDefined();
    expect(tool?.inputSchema).toBeDefined();
    expect(tool?.inputSchema.type).toBe('object');
    expect(tool?.inputSchema.properties).toBeDefined();
    expect(tool?.inputSchema.properties?.old_note_id).toBeDefined();
    expect(tool?.inputSchema.properties?.new_note_id).toBeDefined();
    expect(tool?.inputSchema.properties?.reason).toBeDefined();
    expect(tool?.inputSchema.properties?.response_format).toBeDefined();
    expect(tool?.inputSchema.required).toContain('old_note_id');
    expect(tool?.inputSchema.required).toContain('new_note_id');
  });

  // Note: Integration tests would require a running backend API
  // These are skipped for now but can be enabled when backend is available
  test.skip('handleMemRead with ID', async () => {
    // Requires running backend
    const result = await handleMemRead({ id: 1 });
    expect(result).toBeDefined();
    expect(result.content).toBeDefined();
    expect(result.structuredContent).toBeDefined();
  });

  test.skip('handleMemWrite creates note', async () => {
    // Requires running backend
    const result = await handleMemWrite({
      relative_path: 'test.md',
      title: 'Test Note',
      content: '# Test\n\nContent',
    });
    expect(result).toBeDefined();
    expect(result.structuredContent).toBeDefined();
  });

  test.skip('handleMemSearch finds notes', async () => {
    // Requires running backend
    const result = await handleMemSearch({ query: 'test' });
    expect(result).toBeDefined();
    expect(result.structuredContent).toBeDefined();
  });

  test.skip('handleMemSupersede marks note as superseded', async () => {
    // Requires running backend
    const result = await handleMemSupersede({
      old_note_id: 1,
      new_note_id: 2,
      reason: 'Updated information',
    });
    expect(result).toBeDefined();
    expect(result.structuredContent).toBeDefined();
    expect(result.content[0].text).toContain('Note Superseded');
  });
});
