/**
 * Streamable HTTP transport for MCP server (2025-03-26 spec).
 *
 * This transport implements the unified endpoint pattern:
 * - POST /mcp - Handle JSON-RPC requests (initialize, tools/call, etc.)
 * - GET /mcp - Open SSE stream for server notifications
 * - DELETE /mcp - Terminate session
 *
 * Authentication is handled externally by the OAuth gateway (Traefik ForwardAuth).
 * This transport is a pure MCP protocol handler with no authentication logic.
 */

import type { JSONRPCRequest, JSONRPCResponse } from '@modelcontextprotocol/sdk/types.js';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { dispatchToolCall } from '../handlers.js';
import { tools } from '../tools.js';

export interface SSEServerOptions {
  port?: number;
  mcpPath?: string;
}

interface MCPSession {
  id: string;
  controller: ReadableStreamDefaultController | null;
  lastActivity: number;
  initialized: boolean;
}

/**
 * Allowed CORS origins for production security.
 */
const ALLOWED_ORIGINS = [
  'https://claude.ai',
  'https://claude.com',
  'https://www.claude.ai',
  'http://localhost:6274', // Claude Code / MCP Inspector
];

/**
 * Get CORS headers based on origin.
 */
function getCorsHeaders(origin: string | null, exposeSessionId = false): Record<string, string> {
  const headers: Record<string, string> = {
    'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Accept, Authorization, Mcp-Session-Id',
  };

  // In development, allow all origins
  const env = process.env as Record<string, string | undefined>;
  const isDev = env['NODE_ENV'] !== 'production';

  if (isDev) {
    headers['Access-Control-Allow-Origin'] = origin || '*';
  } else if (origin && ALLOWED_ORIGINS.some(allowed => origin.startsWith(allowed))) {
    headers['Access-Control-Allow-Origin'] = origin;
  } else {
    // Default to claude.ai for production
    headers['Access-Control-Allow-Origin'] = 'https://claude.ai';
  }

  if (exposeSessionId) {
    headers['Access-Control-Expose-Headers'] = 'Mcp-Session-Id';
  }

  return headers;
}

/**
 * Handle MCP JSON-RPC requests directly.
 * This processes the standard MCP protocol methods.
 */
async function handleMcpRequest(body: JSONRPCRequest): Promise<JSONRPCResponse> {
  const { method, params, id } = body;

  try {
    switch (method) {
      case 'initialize': {
        return {
          jsonrpc: '2.0',
          id,
          result: {
            protocolVersion: '2025-03-26',
            capabilities: {
              tools: {},
            },
            serverInfo: {
              name: 'obsidian-memory',
              version: '0.2.0',
            },
          },
        };
      }

      case 'notifications/initialized': {
        // No response needed for notifications
        return {
          jsonrpc: '2.0',
          id,
          result: {},
        };
      }

      case 'tools/list': {
        return {
          jsonrpc: '2.0',
          id,
          result: {
            tools,
          },
        };
      }

      case 'tools/call': {
        const { name, arguments: args } = params as { name: string; arguments: Record<string, unknown> };

        try {
          const result = await dispatchToolCall(name, args);
          const response: { content: typeof result.content; structuredContent?: unknown } = {
            content: result.content,
          };
          if (result.structuredContent !== undefined) {
            response.structuredContent = result.structuredContent;
          }
          return {
            jsonrpc: '2.0',
            id,
            result: response,
          };
        } catch (toolError) {
          return {
            jsonrpc: '2.0',
            id,
            error: {
              code: -32603,
              message: toolError instanceof Error ? toolError.message : String(toolError),
            },
          };
        }
      }

      case 'ping': {
        return {
          jsonrpc: '2.0',
          id,
          result: {},
        };
      }

      default:
        return {
          jsonrpc: '2.0',
          id,
          error: {
            code: -32601,
            message: `Method not found: ${method}`,
          },
        };
    }
  } catch (error) {
    console.error(`Error handling MCP request ${method}:`, error);
    return {
      jsonrpc: '2.0',
      id,
      error: {
        code: -32603,
        message: error instanceof Error ? error.message : String(error),
      },
    };
  }
}

/**
 * Check if request is an initialize request.
 */
function isInitializeRequest(body: unknown): boolean {
  return (
    typeof body === 'object' &&
    body !== null &&
    'method' in body &&
    (body as { method: string }).method === 'initialize'
  );
}

/**
 * Create a Streamable HTTP server for MCP.
 *
 * @param server - MCP server instance
 * @param options - Server options
 */
export async function createSSEServer(
  _server: McpServer, // McpServer instance available but using direct handlers for HTTP
  options: SSEServerOptions = {}
): Promise<void> {
  const env = process.env as Record<string, string | undefined>;
  const port = options.port || parseInt(env['MCP_SSE_PORT'] || '3000', 10);
  const mcpPath = options.mcpPath || '/mcp';

  // For Bun runtime, we can use Bun.serve
  if (typeof Bun !== 'undefined') {
    const sessions = new Map<string, MCPSession>();

    // Clean up inactive sessions periodically
    setInterval(() => {
      const now = Date.now();
      for (const [id, session] of sessions.entries()) {
        if (now - session.lastActivity > 300000) {
          // 5 minutes inactivity
          try {
            session.controller?.close();
          } catch {
            // Ignore errors
          }
          sessions.delete(id);
        }
      }
    }, 60000); // Check every minute

    Bun.serve({
      port,
      async fetch(req) {
        const url = new URL(req.url);
        const origin = req.headers.get('origin');

        // CORS preflight
        if (req.method === 'OPTIONS') {
          return new Response(null, {
            headers: getCorsHeaders(origin, true),
          });
        }

        // Unified MCP endpoint (Streamable HTTP transport)
        if (url.pathname === mcpPath) {
          const sessionId = req.headers.get('mcp-session-id');

          // POST - Handle JSON-RPC requests
          // Note: Authentication is handled by the OAuth gateway (Traefik ForwardAuth)
          if (req.method === 'POST') {
            try {
              const body = (await req.json()) as JSONRPCRequest;

              console.error(`MCP Request: ${body.method} (id: ${body.id})`);

              // Handle initialize - create new session
              if (isInitializeRequest(body)) {
                const newSessionId = crypto.randomUUID();
                const session: MCPSession = {
                  id: newSessionId,
                  controller: null,
                  lastActivity: Date.now(),
                  initialized: true,
                };
                sessions.set(newSessionId, session);

                const response = await handleMcpRequest(body);
                console.error(`MCP Response: session created (id: ${newSessionId})`);

                return new Response(JSON.stringify(response), {
                  headers: {
                    'Content-Type': 'application/json',
                    'Mcp-Session-Id': newSessionId,
                    ...getCorsHeaders(origin, true),
                  },
                });
              }

              // For other requests, require valid session
              if (!sessionId) {
                return new Response(JSON.stringify({
                  jsonrpc: '2.0',
                  error: { code: -32000, message: 'Missing Mcp-Session-Id header' },
                  id: body.id,
                }), {
                  status: 400,
                  headers: {
                    'Content-Type': 'application/json',
                    ...getCorsHeaders(origin),
                  },
                });
              }

              const session = sessions.get(sessionId);
              if (!session) {
                return new Response(JSON.stringify({
                  jsonrpc: '2.0',
                  error: { code: -32000, message: 'Invalid session' },
                  id: body.id,
                }), {
                  status: 404,
                  headers: {
                    'Content-Type': 'application/json',
                    ...getCorsHeaders(origin),
                  },
                });
              }

              session.lastActivity = Date.now();

              // Process the MCP request
              const response = await handleMcpRequest(body);
              console.error(`MCP Response: ${'error' in response ? 'error' : 'success'} (id: ${response.id})`);

              // If session has an SSE stream, also send response there
              if (session.controller) {
                try {
                  const sseMessage = `data: ${JSON.stringify(response)}\n\n`;
                  session.controller.enqueue(sseMessage);
                } catch {
                  // SSE stream closed, ignore
                }
              }

              return new Response(JSON.stringify(response), {
                headers: {
                  'Content-Type': 'application/json',
                  ...getCorsHeaders(origin),
                },
              });
            } catch (error) {
              console.error('MCP message error:', error);
              return new Response(JSON.stringify({
                jsonrpc: '2.0',
                error: {
                  code: -32700,
                  message: 'Parse error',
                },
                id: null,
              }), {
                status: 400,
                headers: {
                  'Content-Type': 'application/json',
                  ...getCorsHeaders(origin),
                },
              });
            }
          }

          // GET - Open SSE stream for server notifications
          if (req.method === 'GET') {
            if (!sessionId) {
              return new Response('Missing Mcp-Session-Id header', {
                status: 400,
                headers: getCorsHeaders(origin),
              });
            }

            const session = sessions.get(sessionId);
            if (!session) {
              return new Response('Session not found', {
                status: 404,
                headers: getCorsHeaders(origin),
              });
            }

            const stream = new ReadableStream({
              start(controller) {
                session.controller = controller;
                session.lastActivity = Date.now();

                // Send initial keepalive
                controller.enqueue(': keepalive\n\n');

                // Clean up on close
                req.signal.addEventListener('abort', () => {
                  session.controller = null;
                  try {
                    controller.close();
                  } catch {
                    // Ignore errors
                  }
                });
              },
            });

            return new Response(stream, {
              headers: {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                ...getCorsHeaders(origin),
              },
            });
          }

          // DELETE - Terminate session
          if (req.method === 'DELETE') {
            if (sessionId) {
              const session = sessions.get(sessionId);
              if (session?.controller) {
                try {
                  session.controller.close();
                } catch {
                  // Ignore errors
                }
              }
              sessions.delete(sessionId);
            }
            return new Response(null, {
              status: 200,
              headers: getCorsHeaders(origin),
            });
          }

          return new Response('Method not allowed', {
            status: 405,
            headers: getCorsHeaders(origin),
          });
        }

        // Health check
        if (url.pathname === '/health' && req.method === 'GET') {
          return new Response(
            JSON.stringify({
              status: 'healthy',
              transport: 'streamable-http',
              protocol: '2025-03-26',
              sessions: sessions.size,
            }),
            {
              headers: {
                'Content-Type': 'application/json',
                ...getCorsHeaders(origin),
              },
            }
          );
        }

        return new Response('Not Found', { status: 404 });
      },
    });

    console.error(`MCP Streamable HTTP server listening on http://localhost:${port}${mcpPath}`);
    console.error(`Protocol version: 2025-03-26`);
    console.error(`Health check: http://localhost:${port}/health`);
    console.error(`Note: Authentication handled externally by OAuth gateway`);
  } else {
    throw new Error(
      'Streamable HTTP transport requires Bun runtime. Use stdio transport for Node.js.'
    );
  }
}
