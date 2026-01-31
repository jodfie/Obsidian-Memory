/**
 * Tests for session management MCP tools.
 */

import { describe, expect, test } from 'bun:test';
import { tools } from '../src/tools.js';
import {
  handleSessionContext,
  handleSessionObserve,
  handleSessionSummary,
} from '../src/handlers.js';

// Get session tools from the tools array
const sessionTools = tools.filter((t) =>
  ['session_observe', 'session_summary', 'session_context'].includes(t.name)
);

describe('Session Tools', () => {
  describe('Tool Schemas', () => {
    test('session_observe tool has correct schema', () => {
      const tool = sessionTools.find((t) => t.name === 'session_observe');
      expect(tool).toBeDefined();
      expect(tool?.inputSchema.type).toBe('object');
      expect(tool?.inputSchema.properties?.session_id).toBeDefined();
      expect(tool?.inputSchema.properties?.event_type).toBeDefined();
      expect(tool?.inputSchema.properties?.content).toBeDefined();
      expect(tool?.inputSchema.required).toContain('session_id');
      expect(tool?.inputSchema.required).toContain('event_type');
      expect(tool?.inputSchema.required).toContain('content');
    });

    test('session_summary tool has correct schema', () => {
      const tool = sessionTools.find((t) => t.name === 'session_summary');
      expect(tool).toBeDefined();
      expect(tool?.inputSchema.type).toBe('object');
      expect(tool?.inputSchema.properties?.session_id).toBeDefined();
      expect(tool?.inputSchema.required).toContain('session_id');
    });

    test('session_context tool has correct schema', () => {
      const tool = sessionTools.find((t) => t.name === 'session_context');
      expect(tool).toBeDefined();
      expect(tool?.inputSchema.type).toBe('object');
      expect(tool?.inputSchema.properties?.session_id).toBeDefined();
      expect(tool?.inputSchema.properties?.include_events).toBeDefined();
      expect(tool?.inputSchema.properties?.include_summary).toBeDefined();
      expect(tool?.inputSchema.properties?.limit).toBeDefined();
      expect(tool?.inputSchema.required).toContain('session_id');
    });
  });

  // Integration tests require a running backend
  // These are skipped for now
  describe.skip('Integration Tests', () => {
    test('handleSessionObserve adds event to session', async () => {
      const result = await handleSessionObserve({
        session_id: 'test-session',
        event_type: 'observation',
        content: 'Test observation',
      });
      expect(result.structuredContent).toBeDefined();
    });

    test('handleSessionSummary generates summary', async () => {
      const result = await handleSessionSummary({ session_id: 'test-session' });
      expect(result.structuredContent).toBeDefined();
    });

    test('handleSessionContext returns context', async () => {
      const result = await handleSessionContext({ session_id: 'test-session' });
      expect(result.structuredContent).toBeDefined();
    });
  });
});
