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
      tools: [
        // Tools will be added per specifications:
        // - mem_read
        // - mem_write
        // - mem_search
        // - graph_traverse
        // - graph_similar
        // - build_context
      ],
    };
  });

  // Handle tool calls
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    // Tool implementations will be added per specifications
    throw new Error(`Tool "${name}" not yet implemented`);
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
