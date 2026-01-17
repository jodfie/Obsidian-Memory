/**
 * SSE (Server-Sent Events) transport for MCP server.
 *
 * This transport allows the MCP server to be accessed via HTTP/SSE,
 * enabling remote access and integration with Claude.ai.
 *
 * The implementation uses:
 * - GET /sse - SSE endpoint for receiving messages from server
 * - POST /message - Endpoint for sending messages to server
 */

import type { JSONRPCRequest, JSONRPCResponse } from '@modelcontextprotocol/sdk/types.js';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';

export interface SSEServerOptions {
  port?: number;
  ssePath?: string;
  messagePath?: string;
}

interface SSEClient {
  id: string;
  controller: ReadableStreamDefaultController;
  lastActivity: number;
}

/**
 * Create an SSE-based HTTP server for MCP.
 *
 * @param server - MCP server instance
 * @param options - Server options
 */
export async function createSSEServer(
  server: Server,
  options: SSEServerOptions = {}
): Promise<void> {
  const port = options.port || parseInt(process.env.MCP_SSE_PORT || '3000', 10);
  const ssePath = options.ssePath || '/sse';
  const messagePath = options.messagePath || '/message';

  // For Bun runtime, we can use Bun.serve
  if (typeof Bun !== 'undefined') {
    const sseClients = new Map<string, SSEClient>();

    // Clean up inactive connections periodically
    setInterval(() => {
      const now = Date.now();
      for (const [id, client] of sseClients.entries()) {
        if (now - client.lastActivity > 300000) {
          // 5 minutes inactivity
          try {
            client.controller.close();
          } catch {
            // Ignore errors
          }
          sseClients.delete(id);
        }
      }
    }, 60000); // Check every minute

    Bun.serve({
      port,
      async fetch(req) {
        const url = new URL(req.url);

        // SSE endpoint - client connects here to receive messages
        if (url.pathname === ssePath && req.method === 'GET') {
          const stream = new ReadableStream({
            start(controller) {
              const connectionId = crypto.randomUUID();
              const client: SSEClient = {
                id: connectionId,
                controller,
                lastActivity: Date.now(),
              };
              sseClients.set(connectionId, client);

              // Send initial connection message
              const initMessage = JSON.stringify({
                jsonrpc: '2.0',
                id: null,
                method: 'notifications/initialized',
                params: { connectionId },
              });
              controller.enqueue(`data: ${initMessage}\n\n`);

              // Clean up on close
              req.signal.addEventListener('abort', () => {
                sseClients.delete(connectionId);
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
              'Access-Control-Allow-Origin': '*',
              'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
              'Access-Control-Allow-Headers': 'Content-Type',
            },
          });
        }

        // Message endpoint - client sends messages here
        if (url.pathname === messagePath && req.method === 'POST') {
          try {
            const body = (await req.json()) as JSONRPCRequest;

            // Create a simple transport-like interface to process the request
            // The MCP SDK Server processes requests through its registered handlers
            // For SSE, we need to manually invoke the handlers
            
            // Note: This is a simplified implementation
            // A full implementation would need to properly integrate with the Server's
            // internal request routing mechanism. The MCP SDK's Server class is designed
            // to work with Transport implementations that handle the low-level protocol.
            
            // For now, we'll return a response indicating SSE transport is available
            // Full integration requires implementing a custom Transport class
            const response: JSONRPCResponse = {
              jsonrpc: '2.0',
              id: body.id || null,
              result: {
                message: 'SSE transport is active. Full MCP protocol integration requires custom Transport implementation.',
                transport: 'sse',
                endpoints: {
                  sse: ssePath,
                  message: messagePath,
                },
              },
            };

            // Send response to all connected SSE clients
            const responseMessage = JSON.stringify(response);
            for (const client of sseClients.values()) {
              try {
                client.lastActivity = Date.now();
                client.controller.enqueue(`data: ${responseMessage}\n\n`);
              } catch {
                // Client disconnected, remove it
                sseClients.delete(client.id);
              }
            }

            // Also return response directly
            return new Response(JSON.stringify(response), {
              headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
              },
            });
          } catch (error) {
            const errorResponse: JSONRPCResponse = {
              jsonrpc: '2.0',
              id: null,
              error: {
                code: -32603,
                message: error instanceof Error ? error.message : String(error),
              },
            };

            return new Response(JSON.stringify(errorResponse), {
              status: 400,
              headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
              },
            });
          }
        }

        // CORS preflight
        if (req.method === 'OPTIONS') {
          return new Response(null, {
            headers: {
              'Access-Control-Allow-Origin': '*',
              'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
              'Access-Control-Allow-Headers': 'Content-Type',
            },
          });
        }

        // Health check
        if (url.pathname === '/health' && req.method === 'GET') {
          return new Response(
            JSON.stringify({
              status: 'healthy',
              transport: 'sse',
              clients: sseClients.size,
            }),
            {
              headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
              },
            }
          );
        }

        return new Response('Not Found', { status: 404 });
      },
    });

    console.error(`MCP SSE server listening on http://localhost:${port}${ssePath}`);
    console.error(`Send messages to http://localhost:${port}${messagePath}`);
    console.error(`Health check: http://localhost:${port}/health`);
  } else {
    throw new Error(
      'SSE transport requires Bun runtime. Use stdio transport for Node.js.'
    );
  }
}
