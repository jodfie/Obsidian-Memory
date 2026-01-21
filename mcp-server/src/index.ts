/**
 * Obsidian-Memory MCP Server
 *
 * Provides memory management tools for Claude Code via Model Context Protocol.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { handleBuildContext } from './tools/context.js';
import {
  handleGraphSimilar,
  handleGraphTraverse,
} from './tools/graph.js';
import {
  handleMemRead,
  handleMemSearch,
  handleMemWrite,
  memoryTools,
} from './tools/memory.js';
import {
  handleProjectCreate,
  handleProjectList,
  handleProjectSwitch,
} from './tools/project.js';
import {
  handleSessionContext,
  handleSessionObserve,
  handleSessionSummary,
} from './tools/session.js';

/**
 * Simple logger for MCP server.
 */
const logger = {
  info: (message: string, ...args: unknown[]) => {
    console.error(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'INFO',
      message,
      ...(args.length > 0 && { data: args }),
    }));
  },
  error: (message: string, error?: Error | unknown) => {
    console.error(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'ERROR',
      message,
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
    }));
  },
  warn: (message: string, ...args: unknown[]) => {
    console.error(JSON.stringify({
      timestamp: new Date().toISOString(),
      level: 'WARN',
      message,
      ...(args.length > 0 && { data: args }),
    }));
  },
};

/**
 * Initialize and start the MCP server.
 */
async function main(): Promise<void> {
  logger.info('Starting Obsidian-Memory MCP Server');

  // Create server instance
  const server = new Server(
    {
      name: 'obsidian-memory',
      version: '0.1.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  // List available tools
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: memoryTools,
    };
  });

  // Handle tool calls
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      switch (name) {
        case 'mem_read':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleMemRead(args as Parameters<typeof handleMemRead>[0]), null, 2),
              },
            ],
          };

        case 'mem_write':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleMemWrite(args as Parameters<typeof handleMemWrite>[0]), null, 2),
              },
            ],
          };

        case 'mem_search':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleMemSearch(args as Parameters<typeof handleMemSearch>[0]), null, 2),
              },
            ],
          };

        case 'build_context':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleBuildContext(args as Parameters<typeof handleBuildContext>[0]), null, 2),
              },
            ],
          };

        case 'graph_traverse':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleGraphTraverse(args as Parameters<typeof handleGraphTraverse>[0]), null, 2),
              },
            ],
          };

        case 'graph_similar':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleGraphSimilar(args as Parameters<typeof handleGraphSimilar>[0]), null, 2),
              },
            ],
          };

        case 'project_list':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleProjectList(), null, 2),
              },
            ],
          };

        case 'project_switch':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleProjectSwitch(args as Parameters<typeof handleProjectSwitch>[0]), null, 2),
              },
            ],
          };

        case 'project_create':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleProjectCreate(args as Parameters<typeof handleProjectCreate>[0]), null, 2),
              },
            ],
          };

        case 'session_observe':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleSessionObserve(args as Parameters<typeof handleSessionObserve>[0]), null, 2),
              },
            ],
          };

        case 'session_summary':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleSessionSummary(args as Parameters<typeof handleSessionSummary>[0]), null, 2),
              },
            ],
          };

        case 'session_context':
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(await handleSessionContext(args as Parameters<typeof handleSessionContext>[0]), null, 2),
              },
            ],
          };

        default:
          throw new Error(`Unknown tool: ${name}`);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logger.error(`Tool "${name}" failed`, error);
      throw new Error(`Tool "${name}" failed: ${message}`);
    }
  });

  // Determine transport based on environment
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
