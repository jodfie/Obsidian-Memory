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

import { ApiClient } from './tools/api-client.js';
import {
  getMemReadTool,
  getMemSearchTool,
  getMemWriteTool,
  handleMemRead,
  handleMemSearch,
  handleMemWrite,
} from './tools/memory-tools.js';

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

  // Create API client
  const apiClient = new ApiClient();

  // List available tools
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [
        getMemReadTool(),
        getMemWriteTool(),
        getMemSearchTool(),
        // Future tools:
        // - graph_traverse
        // - graph_similar
        // - build_context
      ],
    };
  });

  // Handle tool calls
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      switch (name) {
        case 'mem_read':
          return await handleMemRead(
            args as Parameters<typeof handleMemRead>[0],
            apiClient
          );

        case 'mem_write':
          return await handleMemWrite(
            args as Parameters<typeof handleMemWrite>[0],
            apiClient
          );

        case 'mem_search':
          return await handleMemSearch(
            args as Parameters<typeof handleMemSearch>[0],
            apiClient
          );

        default:
          throw new Error(`Unknown tool: ${name}`);
      }
    } catch (error) {
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
