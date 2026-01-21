/**
 * Streamable HTTP transport for MCP server (2025-03-26 spec).
 *
 * This transport implements the unified endpoint pattern:
 * - POST /mcp - Handle JSON-RPC requests (initialize, tools/call, etc.)
 * - GET /mcp - Open SSE stream for server notifications
 * - DELETE /mcp - Terminate session
 *
 * OAuth endpoints for Claude.ai connector:
 * - GET /authorize - OAuth authorization redirect to Cloudflare Access
 * - POST /token - OAuth token exchange proxy to Cloudflare Access
 * - GET /.well-known/oauth-authorization-server - OAuth server metadata
 * - GET /.well-known/oauth-protected-resource - Protected resource metadata (MCP spec)
 * - GET /.well-known/openid-configuration - OIDC discovery
 */

import type { JSONRPCRequest, JSONRPCResponse } from '@modelcontextprotocol/sdk/types.js';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { handleBuildContext } from '../tools/context.js';
import { handleGraphSimilar, handleGraphTraverse } from '../tools/graph.js';
import { handleMemRead, handleMemSearch, handleMemWrite, memoryTools } from '../tools/memory.js';
import { handleProjectCreate, handleProjectList, handleProjectSwitch } from '../tools/project.js';
import { handleSessionContext, handleSessionObserve, handleSessionSummary } from '../tools/session.js';

export interface SSEServerOptions {
  port?: number;
  mcpPath?: string;
}

/**
 * OAuth configuration from environment variables.
 */
interface OAuthConfig {
  clientId: string;
  clientSecret: string;
  teamDomain: string;
  issuer: string;
  authorizationEndpoint: string;
  tokenEndpoint: string;
  jwksUri: string;
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
 * Validate Bearer token from Authorization header.
 * Returns true if valid or if auth is disabled.
 */
async function validateBearerToken(authHeader: string | null, oauthConfig: OAuthConfig): Promise<boolean> {
  // If no OAuth configured, allow all requests (development mode)
  if (!oauthConfig.clientId || !oauthConfig.clientSecret) {
    return true;
  }

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return false;
  }

  const token = authHeader.slice(7);

  try {
    // Introspect token with Cloudflare Access
    const response = await fetch(`${oauthConfig.issuer}/cdn-cgi/access/sso/oidc/${oauthConfig.clientId}/introspect`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        token,
        client_id: oauthConfig.clientId,
        client_secret: oauthConfig.clientSecret,
      }).toString(),
    });

    if (!response.ok) {
      console.error('Token introspection failed:', response.status);
      return false;
    }

    const data = await response.json() as { active?: boolean };
    return data.active === true;
  } catch (error) {
    console.error('Token validation error:', error);
    return false;
  }
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
              version: '0.1.0',
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
            tools: memoryTools,
          },
        };
      }

      case 'tools/call': {
        const { name, arguments: args } = params as { name: string; arguments: Record<string, unknown> };
        let resultContent: unknown;

        switch (name) {
          case 'mem_read':
            resultContent = await handleMemRead(args as Parameters<typeof handleMemRead>[0]);
            break;
          case 'mem_write':
            resultContent = await handleMemWrite(args as Parameters<typeof handleMemWrite>[0]);
            break;
          case 'mem_search':
            resultContent = await handleMemSearch(args as Parameters<typeof handleMemSearch>[0]);
            break;
          case 'build_context':
            resultContent = await handleBuildContext(args as Parameters<typeof handleBuildContext>[0]);
            break;
          case 'graph_traverse':
            resultContent = await handleGraphTraverse(args as Parameters<typeof handleGraphTraverse>[0]);
            break;
          case 'graph_similar':
            resultContent = await handleGraphSimilar(args as Parameters<typeof handleGraphSimilar>[0]);
            break;
          case 'project_list':
            resultContent = await handleProjectList();
            break;
          case 'project_switch':
            resultContent = await handleProjectSwitch(args as Parameters<typeof handleProjectSwitch>[0]);
            break;
          case 'project_create':
            resultContent = await handleProjectCreate(args as Parameters<typeof handleProjectCreate>[0]);
            break;
          case 'session_observe':
            resultContent = await handleSessionObserve(args as Parameters<typeof handleSessionObserve>[0]);
            break;
          case 'session_summary':
            resultContent = await handleSessionSummary(args as Parameters<typeof handleSessionSummary>[0]);
            break;
          case 'session_context':
            resultContent = await handleSessionContext(args as Parameters<typeof handleSessionContext>[0]);
            break;
          default:
            return {
              jsonrpc: '2.0',
              id,
              error: {
                code: -32601,
                message: `Unknown tool: ${name}`,
              },
            };
        }

        return {
          jsonrpc: '2.0',
          id,
          result: {
            content: [
              {
                type: 'text',
                text: JSON.stringify(resultContent, null, 2),
              },
            ],
          },
        };
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
  _server: Server, // Server instance available but using direct handlers for HTTP
  options: SSEServerOptions = {}
): Promise<void> {
  const env = process.env as Record<string, string | undefined>;
  const port = options.port || parseInt(env['MCP_SSE_PORT'] || '3000', 10);
  const mcpPath = options.mcpPath || '/mcp';

  // OAuth configuration from environment
  const oauthConfig: OAuthConfig = {
    clientId: env['CLOUDFLARE_OAUTH_CLIENT_ID'] || '',
    clientSecret: env['CLOUDFLARE_OAUTH_CLIENT_SECRET'] || '',
    teamDomain: env['CLOUDFLARE_ACCESS_TEAM_DOMAIN'] || 'redleif.cloudflareaccess.com',
    issuer: '',
    authorizationEndpoint: '',
    tokenEndpoint: '',
    jwksUri: '',
  };

  // Derive OAuth endpoints from client ID and team domain
  oauthConfig.issuer = `https://${oauthConfig.teamDomain}`;
  oauthConfig.authorizationEndpoint = `https://${oauthConfig.teamDomain}/cdn-cgi/access/sso/oidc/${oauthConfig.clientId}/authorization`;
  oauthConfig.tokenEndpoint = `https://${oauthConfig.teamDomain}/cdn-cgi/access/sso/oidc/${oauthConfig.clientId}/token`;
  oauthConfig.jwksUri = `https://${oauthConfig.teamDomain}/cdn-cgi/access/certs`;

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
          if (req.method === 'POST') {
            // Validate auth for protected endpoints
            const authHeader = req.headers.get('authorization');
            const isValid = await validateBearerToken(authHeader, oauthConfig);
            if (!isValid && oauthConfig.clientId) {
              return new Response(JSON.stringify({
                jsonrpc: '2.0',
                error: { code: -32001, message: 'Unauthorized' },
                id: null,
              }), {
                status: 401,
                headers: {
                  'Content-Type': 'application/json',
                  'WWW-Authenticate': 'Bearer',
                  ...getCorsHeaders(origin),
                },
              });
            }

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

        // OAuth 2.0 Authorization Endpoint - redirects to Cloudflare Access
        if (url.pathname === '/authorize' && req.method === 'GET') {
          // Build the Cloudflare Access authorization URL with all query params
          const cfAuthUrl = new URL(oauthConfig.authorizationEndpoint);

          // Forward all OAuth parameters to Cloudflare
          for (const [key, value] of url.searchParams.entries()) {
            cfAuthUrl.searchParams.set(key, value);
          }

          // Ensure client_id is set
          if (!cfAuthUrl.searchParams.has('client_id')) {
            cfAuthUrl.searchParams.set('client_id', oauthConfig.clientId);
          }

          console.error(`OAuth: Redirecting to Cloudflare Access: ${cfAuthUrl.toString()}`);

          return new Response(null, {
            status: 302,
            headers: {
              'Location': cfAuthUrl.toString(),
            },
          });
        }

        // OAuth 2.0 Token Endpoint - proxies to Cloudflare Access
        if (url.pathname === '/token' && req.method === 'POST') {
          try {
            // Get the request body
            const contentType = req.headers.get('content-type') || '';
            let body: string;

            if (contentType.includes('application/x-www-form-urlencoded')) {
              body = await req.text();
            } else if (contentType.includes('application/json')) {
              const jsonBody = await req.json();
              body = new URLSearchParams(jsonBody as Record<string, string>).toString();
            } else {
              body = await req.text();
            }

            // Parse the body to add client credentials if not present
            const params = new URLSearchParams(body);
            if (!params.has('client_id')) {
              params.set('client_id', oauthConfig.clientId);
            }
            if (!params.has('client_secret')) {
              params.set('client_secret', oauthConfig.clientSecret);
            }

            console.error(`OAuth: Proxying token request to Cloudflare Access`);

            // Forward to Cloudflare Access token endpoint
            const cfResponse = await fetch(oauthConfig.tokenEndpoint, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
              },
              body: params.toString(),
            });

            const cfData = await cfResponse.text();

            return new Response(cfData, {
              status: cfResponse.status,
              headers: {
                'Content-Type': cfResponse.headers.get('Content-Type') || 'application/json',
                ...getCorsHeaders(origin),
              },
            });
          } catch (error) {
            console.error('OAuth token error:', error);
            return new Response(
              JSON.stringify({
                error: 'server_error',
                error_description: error instanceof Error ? error.message : String(error),
              }),
              {
                status: 500,
                headers: {
                  'Content-Type': 'application/json',
                  ...getCorsHeaders(origin),
                },
              }
            );
          }
        }

        // OAuth 2.0 Protected Resource Metadata (MCP 2025-03-26 spec requirement)
        if (url.pathname === '/.well-known/oauth-protected-resource' && req.method === 'GET') {
          const serverUrl = env['MCP_SERVER_URL'] || `http://localhost:${port}`;

          const metadata = {
            resource: `${serverUrl}/mcp`,
            authorization_servers: [oauthConfig.issuer],
            scopes_supported: ['mcp:tools', 'openid', 'email', 'profile'],
            resource_name: 'Obsidian-Memory MCP Server',
          };

          return new Response(JSON.stringify(metadata, null, 2), {
            headers: {
              'Content-Type': 'application/json',
              ...getCorsHeaders(origin),
            },
          });
        }

        // OAuth 2.0 Authorization Server Metadata
        if (url.pathname === '/.well-known/oauth-authorization-server' && req.method === 'GET') {
          const serverUrl = env['MCP_SERVER_URL'] || `http://localhost:${port}`;

          const metadata = {
            issuer: serverUrl,
            authorization_endpoint: `${serverUrl}/authorize`,
            token_endpoint: `${serverUrl}/token`,
            token_endpoint_auth_methods_supported: ['client_secret_post', 'client_secret_basic'],
            grant_types_supported: ['authorization_code', 'refresh_token'],
            response_types_supported: ['code'],
            scopes_supported: ['openid', 'email', 'profile', 'mcp:tools'],
            code_challenge_methods_supported: ['S256'],
            jwks_uri: oauthConfig.jwksUri,
          };

          return new Response(JSON.stringify(metadata, null, 2), {
            headers: {
              'Content-Type': 'application/json',
              ...getCorsHeaders(origin),
            },
          });
        }

        // OpenID Connect Discovery Endpoint
        if (url.pathname === '/.well-known/openid-configuration' && req.method === 'GET') {
          const serverUrl = env['MCP_SERVER_URL'] || `http://localhost:${port}`;

          const config = {
            issuer: oauthConfig.issuer,
            authorization_endpoint: `${serverUrl}/authorize`,
            token_endpoint: `${serverUrl}/token`,
            userinfo_endpoint: `${oauthConfig.issuer}/cdn-cgi/access/sso/oidc/${oauthConfig.clientId}/userinfo`,
            jwks_uri: oauthConfig.jwksUri,
            response_types_supported: ['code'],
            subject_types_supported: ['public'],
            id_token_signing_alg_values_supported: ['RS256'],
            scopes_supported: ['openid', 'email', 'profile', 'mcp:tools'],
            token_endpoint_auth_methods_supported: ['client_secret_post', 'client_secret_basic'],
            claims_supported: ['sub', 'email', 'name', 'preferred_username'],
            code_challenge_methods_supported: ['S256'],
            grant_types_supported: ['authorization_code', 'refresh_token'],
          };

          return new Response(JSON.stringify(config, null, 2), {
            headers: {
              'Content-Type': 'application/json',
              ...getCorsHeaders(origin),
            },
          });
        }

        return new Response('Not Found', { status: 404 });
      },
    });

    console.error(`MCP Streamable HTTP server listening on http://localhost:${port}${mcpPath}`);
    console.error(`Protocol version: 2025-03-26`);
    console.error(`Health check: http://localhost:${port}/health`);
    console.error(`OAuth authorize: http://localhost:${port}/authorize`);
    console.error(`OAuth token: http://localhost:${port}/token`);
    console.error(`OAuth metadata: http://localhost:${port}/.well-known/oauth-authorization-server`);
    console.error(`Protected resource: http://localhost:${port}/.well-known/oauth-protected-resource`);
    if (oauthConfig.clientId) {
      console.error(`OAuth configured with client ID: ${oauthConfig.clientId.substring(0, 8)}...`);
    } else {
      console.error(`WARNING: OAuth not configured - set CLOUDFLARE_OAUTH_CLIENT_ID and CLOUDFLARE_OAUTH_CLIENT_SECRET`);
    }
  } else {
    throw new Error(
      'Streamable HTTP transport requires Bun runtime. Use stdio transport for Node.js.'
    );
  }
}
