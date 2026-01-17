/**
 * Tests for session management MCP tools.
 */

import { describe, expect, test } from 'bun:test';
import {
  handleSessionContext,
  handleSessionObserve,
  handleSessionSummary,
  sessionTools,
} from '../src/tools/session.js';

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
      expect(result).toHaveProperty('session_id');
      expect(result).toHaveProperty('event_count');
    });

    test('handleSessionSummary generates summary', async () => {
      const result = await handleSessionSummary({ session_id: 'test-session' });
      expect(result).toHaveProperty('key_learnings');
      expect(result).toHaveProperty('summary_text');
    });

    test('handleSessionContext returns context', async () => {
      const result = await handleSessionContext({ session_id: 'test-session' });
      expect(result).toHaveProperty('session_id');
      expect(result).toHaveProperty('event_count');
    });
  });
});
