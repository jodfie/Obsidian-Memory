/**
 * Obsidian-Memory MCP Server
 *
 * Provides memory management tools for Claude Code via Model Context Protocol.
 * Uses McpServer with manual tool registration to avoid Zod type inference issues.
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { tools } from './tools.js';
import { dispatchToolCall } from './handlers.js';

/**
 * Simple logger for MCP server.
 */
const logger = {
  info: (message: string, ...args: unknown[]) => {
    console.error(
      JSON.stringify({
        timestamp: new Date().toISOString(),
        level: 'INFO',
        message,
        ...(args.length > 0 && { data: args }),
      })
    );
  },
  error: (message: string, error?: Error | unknown) => {
    console.error(
      JSON.stringify({
        timestamp: new Date().toISOString(),
        level: 'ERROR',
        message,
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      })
    );
  },
  warn: (message: string, ...args: unknown[]) => {
    console.error(
      JSON.stringify({
        timestamp: new Date().toISOString(),
        level: 'WARN',
        message,
        ...(args.length > 0 && { data: args }),
      })
    );
  },
};

/**
 * Create and configure the MCP server with all tools.
 */
function createServer(): McpServer {
  const server = new McpServer(
    {
      name: 'obsidian-memory',
      version: '0.2.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // Register tools/list handler
  server.server.setRequestHandler(ListToolsRequestSchema, async () => {
    return { tools };
  });

  // Register tools/call handler
  server.server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      const result = await dispatchToolCall(name, args ?? {});
      return {
        content: result.content,
        ...(result.structuredContent !== undefined && {
          structuredContent: result.structuredContent,
        }),
      };
    } catch (error) {
      logger.error(`Tool ${name} failed`, error);
      return {
        content: [
          {
            type: 'text',
            text: `Error: ${error instanceof Error ? error.message : String(error)}`,
          },
        ],
        isError: true,
      };
    }
  });

  return server;
}

/**
 * Initialize and start the MCP server.
 */
async function main(): Promise<void> {
  logger.info('Starting Obsidian-Memory MCP Server');

  const server = createServer();
  const env = process.env as Record<string, string | undefined>;
  const transportType = env['MCP_TRANSPORT'] || 'stdio';

  if (transportType === 'sse') {
    // Use Streamable HTTP transport for HTTP/remote access
    const { createSSEServer } = await import('./transport/sse.js');
    await createSSEServer(server, {
      port: parseInt(env['MCP_SSE_PORT'] || '3000', 10),
      mcpPath: env['MCP_PATH'] || '/mcp',
    });
    logger.info('Obsidian-Memory MCP Server started (Streamable HTTP transport)');
  } else {
    // Default: use stdio transport for CLI
    const transport = new StdioServerTransport();
    await server.connect(transport);
    logger.info('Obsidian-Memory MCP Server started (stdio transport)');
  }
}

// Run if executed directly
if (import.meta.main) {
  main().catch((error) => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

// Export for testing
export { createServer };
