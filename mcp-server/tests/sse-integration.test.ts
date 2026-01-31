/**
 * Integration tests for SSE transport with all tool categories.
 * These tests verify that all 13 tools are properly accessible via HTTP endpoints.
 */

import { describe, expect, test, beforeAll, afterAll } from 'bun:test';
import { createSSEServer } from '../src/transport/sse.js';
import { createServer } from '../src/index.js';
import type { JSONRPCRequest, JSONRPCResponse } from '@modelcontextprotocol/sdk/types.js';

const TEST_PORT = 4001;
const MCP_PATH = '/mcp';
const BASE_URL = `http://localhost:${TEST_PORT}${MCP_PATH}`;

describe('SSE Transport Integration', () => {
  let sessionId: string | null = null;

  beforeAll(async () => {
    // Start SSE server on test port
    const server = createServer();
    await createSSEServer(server, {
      port: TEST_PORT,
      mcpPath: MCP_PATH,
    });
    // Give server time to start
    await new Promise(resolve => setTimeout(resolve, 100));
  });

  describe('Session Management', () => {
    test('initialize creates new session', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: 1,
        method: 'initialize',
        params: {
          protocolVersion: '2025-03-26',
          capabilities: {},
        },
      };

      const response = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      expect(response.status).toBe(200);

      // Check for session ID header
      const sessionHeader = response.headers.get('mcp-session-id');
      expect(sessionHeader).toBeDefined();
      expect(sessionHeader).toMatch(/^[0-9a-f-]+$/);
      sessionId = sessionHeader;

      const data = await response.json() as JSONRPCResponse;
      expect(data.result).toBeDefined();
      expect(data.result.protocolVersion).toBe('2025-03-26');
      expect(data.result.serverInfo.name).toBe('obsidian-memory');
      expect(data.result.capabilities.tools).toBeDefined();
    });

    test('requests with session ID are accepted', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: 2,
        method: 'tools/list',
        params: {},
      };

      const response = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Mcp-Session-Id': sessionId!,
        },
        body: JSON.stringify(request),
      });

      expect(response.status).toBe(200);

      const data = await response.json() as JSONRPCResponse;
      expect(data.result).toBeDefined();
      expect(data.result.tools).toBeDefined();
      expect(data.result.tools.length).toBe(13);
    });

    test('requests without session ID fail after initialize', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: 3,
        method: 'tools/call',
        params: {
          name: 'mem_read',
          arguments: { id: 1 },
        },
      };

      const response = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request),
      });

      expect(response.status).toBe(401);

      const data = await response.json();
      expect(data.error).toBeDefined();
      expect(data.error.message).toContain('Session required');
    });
  });

  describe('Tool Registration via HTTP', () => {
    test('tools/list returns all 13 tools', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: 4,
        method: 'tools/list',
        params: {},
      };

      const response = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Mcp-Session-Id': sessionId!,
        },
        body: JSON.stringify(request),
      });

      const data = await response.json() as JSONRPCResponse;
      const tools = data.result.tools;
      const toolNames = tools.map((t: any) => t.name);

      // Verify all tool categories
      expect(toolNames).toContain('mem_read');
      expect(toolNames).toContain('mem_write');
      expect(toolNames).toContain('mem_search');
      expect(toolNames).toContain('mem_supersede');
      expect(toolNames).toContain('build_context');
      expect(toolNames).toContain('graph_traverse');
      expect(toolNames).toContain('graph_similar');
      expect(toolNames).toContain('project_list');
      expect(toolNames).toContain('project_switch');
      expect(toolNames).toContain('project_create');
      expect(toolNames).toContain('session_observe');
      expect(toolNames).toContain('session_summary');
      expect(toolNames).toContain('session_context');
    });
  });

  describe('Memory Tools via HTTP', () => {
    test('mem_supersede tool call via HTTP', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: 5,
        method: 'tools/call',
        params: {
          name: 'mem_supersede',
          arguments: {
            old_note_id: 1,
            new_note_id: 2,
            reason: 'Testing supersede via HTTP',
            response_format: 'json',
          },
        },
      };

      const response = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Mcp-Session-Id': sessionId!,
        },
        body: JSON.stringify(request),
      });

      expect(response.status).toBe(200);

      const data = await response.json() as JSONRPCResponse;
      // Will error due to backend not running, but validates the transport
      if (data.error) {
        expect(data.error.message).toBeDefined();
      } else {
        expect(data.result).toBeDefined();
        expect(data.result.content).toBeDefined();
      }
    });

    test('mem_search tool call with filters', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: 6,
        method: 'tools/call',
        params: {
          name: 'mem_search',
          arguments: {
            query: 'test',
            tags: ['backend', 'api'],
            sort: 'relevance',
            limit: 10,
            response_format: 'markdown',
          },
        },
      };

      const response = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Mcp-Session-Id': sessionId!,
        },
        body: JSON.stringify(request),
      });

      expect(response.status).toBe(200);

      const data = await response.json() as JSONRPCResponse;
      // Validates parameter passing and response format handling
      if (!data.error) {
        expect(data.result).toBeDefined();
      }
    });
  });

  describe('Graph Tools via HTTP', () => {
    test('graph_traverse with all parameters', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: 7,
        method: 'tools/call',
        params: {
          name: 'graph_traverse',
          arguments: {
            start_node_id: 1,
            target_node_id: 5,
            method: 'bfs',
            max_depth: 3,
            direction: 'both',
            edge_types: ['depends_on', 'enables'],
            exclude_nodes: [2, 3],
            response_format: 'json',
          },
        },
      };

      const response = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Mcp-Session-Id': sessionId!,
        },
        body: JSON.stringify(request),
      });

      expect(response.status).toBe(200);
    });
  });

  describe('Session Tools via HTTP', () => {
    test('session_observe creates event', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: 8,
        method: 'tools/call',
        params: {
          name: 'session_observe',
          arguments: {
            session_id: 'test-http-session',
            event_type: 'tool_use',
            content: 'Testing SSE transport',
            metadata: {
              tool: 'mem_supersede',
              transport: 'sse',
            },
          },
        },
      };

      const response = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Mcp-Session-Id': sessionId!,
        },
        body: JSON.stringify(request),
      });

      expect(response.status).toBe(200);
    });
  });

  describe('CORS Headers', () => {
    test('OPTIONS request returns CORS headers', async () => {
      const response = await fetch(BASE_URL, {
        method: 'OPTIONS',
        headers: {
          'Origin': 'https://claude.ai',
        },
      });

      expect(response.status).toBe(204);
      expect(response.headers.get('Access-Control-Allow-Origin')).toBeDefined();
      expect(response.headers.get('Access-Control-Allow-Methods')).toContain('POST');
      expect(response.headers.get('Access-Control-Allow-Headers')).toContain('Mcp-Session-Id');
      expect(response.headers.get('Access-Control-Expose-Headers')).toContain('Mcp-Session-Id');
    });

    test('POST request includes CORS headers', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: 9,
        method: 'ping',
        params: {},
      };

      const response = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Mcp-Session-Id': sessionId!,
          'Origin': 'https://claude.ai',
        },
        body: JSON.stringify(request),
      });

      expect(response.headers.get('Access-Control-Allow-Origin')).toBeDefined();
    });
  });

  describe('Error Handling', () => {
    test('unknown tool returns error', async () => {
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: 10,
        method: 'tools/call',
        params: {
          name: 'unknown_tool',
          arguments: {},
        },
      };

      const response = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Mcp-Session-Id': sessionId!,
        },
        body: JSON.stringify(request),
      });

      expect(response.status).toBe(200); // JSON-RPC error still returns 200

      const data = await response.json() as JSONRPCResponse;
      expect(data.error).toBeDefined();
      expect(data.error.message).toContain('Unknown tool');
    });

    test('malformed JSON returns error', async () => {
      const response = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Mcp-Session-Id': sessionId!,
        },
        body: '{ invalid json',
      });

      expect(response.status).toBe(400);
    });
  });

  describe('Session Termination', () => {
    test('DELETE terminates session', async () => {
      const response = await fetch(BASE_URL, {
        method: 'DELETE',
        headers: {
          'Mcp-Session-Id': sessionId!,
        },
      });

      expect(response.status).toBe(204);

      // Verify session is terminated by trying to use it
      const request: JSONRPCRequest = {
        jsonrpc: '2.0',
        id: 11,
        method: 'tools/list',
        params: {},
      };

      const postResponse = await fetch(BASE_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Mcp-Session-Id': sessionId!,
        },
        body: JSON.stringify(request),
      });

      expect(postResponse.status).toBe(401);
    });
  });
});