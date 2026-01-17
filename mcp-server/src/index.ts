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
  handleMemRead,
  handleMemSearch,
  handleMemWrite,
  memoryTools,
} from './tools/memory.js';

/**
 * Initialize and start the MCP server.
 */
async function main(): Promise<void> {
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

        default:
          throw new Error(`Unknown tool: ${name}`);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      throw new Error(`Tool "${name}" failed: ${message}`);
    }
  });

  // Connect via stdio transport
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error('Obsidian-Memory MCP Server started');
}

// Run if executed directly
if (import.meta.main) {
  main().catch((error) => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}
