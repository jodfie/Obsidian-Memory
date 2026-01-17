/**MCP tools for memory operations.*/

import {
  CallToolResult,
  TextContent,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';

import { ApiClient } from './api-client.js';

/**
 * Get mem_read tool definition.
 */
export function getMemReadTool(): Tool {
  return {
    name: 'mem_read',
    description:
      'Read a note from Obsidian-Memory by ID, permalink, or path. Returns the full note content with parsed structure.',
    inputSchema: {
      type: 'object',
      properties: {
        note_id: {
          type: 'number',
          description: 'Note ID from search index',
        },
        permalink: {
          type: 'string',
          description: 'Note permalink (URL-safe slug)',
        },
        vault_name: {
          type: 'string',
          description: 'Vault name (required if using relative_path)',
        },
        relative_path: {
          type: 'string',
          description: 'Relative path within vault (requires vault_name)',
        },
      },
      oneOf: [
        { required: ['note_id'] },
        { required: ['permalink'] },
        { required: ['vault_name', 'relative_path'] },
      ],
    },
  };
}

/**
 * Handle mem_read tool call.
 */
export async function handleMemRead(
  args: {
    note_id?: number;
    permalink?: string;
    vault_name?: string;
    relative_path?: string;
  },
  apiClient: ApiClient
): Promise<CallToolResult> {
  let note;

  if (args.note_id) {
    note = await apiClient.getNoteById(args.note_id);
  } else if (args.permalink) {
    // Search for note by permalink
    const searchResults = await apiClient.searchNotes({
      q: `permalink:${args.permalink}`,
      limit: 1,
    });
    if (searchResults.results.length === 0) {
      throw new Error(`Note with permalink "${args.permalink}" not found`);
    }
    note = await apiClient.getNoteById(searchResults.results[0]!.note_id);
  } else if (args.vault_name && args.relative_path) {
    // Search for note by vault and path
    const searchResults = await apiClient.searchNotes({
      vault: args.vault_name,
      limit: 1000, // Get all notes in vault to find by path
    });
    const found = searchResults.results.find(
      (r) => r.relative_path === args.relative_path
    );
    if (!found) {
      throw new Error(
        `Note not found: ${args.vault_name}/${args.relative_path}`
      );
    }
    note = await apiClient.getNoteById(found.note_id);
  } else {
    throw new Error(
      'Must provide note_id, permalink, or (vault_name + relative_path)'
    );
  }

  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify(
          {
            id: note.id,
            vault_name: note.vault_name,
            relative_path: note.relative_path,
            permalink: note.permalink,
            title: note.title,
            note_type: note.note_type,
            project: note.project,
            content: note.content,
            tags: note.tags,
            created_at: note.created_at,
            updated_at: note.updated_at,
            parsed: note.parsed,
          },
          null,
          2
        ),
      } as TextContent,
    ],
    isError: false,
  };
}

/**
 * Get mem_write tool definition.
 */
export function getMemWriteTool(): Tool {
  return {
    name: 'mem_write',
    description:
      'Create or update a note in Obsidian-Memory. If note_id is provided, updates existing note. Otherwise creates new note.',
    inputSchema: {
      type: 'object',
      properties: {
        note_id: {
          type: 'number',
          description: 'Note ID to update (omit to create new)',
        },
        vault_name: {
          type: 'string',
          description: 'Vault name (required for new notes)',
        },
        relative_path: {
          type: 'string',
          description: 'Relative path within vault (required for new notes)',
        },
        title: {
          type: 'string',
          description: 'Note title',
        },
        content: {
          type: 'string',
          description: 'Markdown content (with or without frontmatter)',
        },
        note_type: {
          type: 'string',
          description: 'Note type (note, decision, error, knowledge, pattern, session, research)',
          enum: [
            'note',
            'decision',
            'error',
            'knowledge',
            'pattern',
            'session',
            'research',
          ],
        },
        project: {
          type: 'string',
          description: 'Project identifier',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Tags for the note',
        },
      },
      required: ['title', 'content'],
    },
  };
}

/**
 * Handle mem_write tool call.
 */
export async function handleMemWrite(
  args: {
    note_id?: number;
    vault_name?: string;
    relative_path?: string;
    title: string;
    content: string;
    note_type?: string;
    project?: string;
    tags?: string[];
  },
  apiClient: ApiClient
): Promise<CallToolResult> {
  let note;

  if (args.note_id) {
    // Update existing note
    note = await apiClient.updateNote(args.note_id, {
      title: args.title,
      content: args.content,
      note_type: args.note_type,
      project: args.project,
      tags: args.tags,
    });
  } else {
    // Create new note
    if (!args.vault_name || !args.relative_path) {
      throw new Error(
        'vault_name and relative_path are required for new notes'
      );
    }
    note = await apiClient.createNote({
      vault_name: args.vault_name,
      relative_path: args.relative_path,
      title: args.title,
      content: args.content,
      note_type: args.note_type || 'note',
      project: args.project,
      tags: args.tags,
    });
  }

  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify(
          {
            id: note.id,
            vault_name: note.vault_name,
            relative_path: note.relative_path,
            permalink: note.permalink,
            title: note.title,
            note_type: note.note_type,
            project: note.project,
            created_at: note.created_at,
            updated_at: note.updated_at,
          },
          null,
          2
        ),
      } as TextContent,
    ],
    isError: false,
  };
}

/**
 * Get mem_search tool definition.
 */
export function getMemSearchTool(): Tool {
  return {
    name: 'mem_search',
    description:
      'Search notes in Obsidian-Memory using full-text search with optional filters.',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description:
            'Search query (FTS5 syntax: terms, phrases, AND/OR/NOT, prefix: "term*")',
        },
        vault: {
          type: 'string',
          description: 'Filter by vault name',
        },
        project: {
          type: 'string',
          description: 'Filter by project',
        },
        note_type: {
          type: 'string',
          description: 'Filter by note type',
          enum: [
            'note',
            'decision',
            'error',
            'knowledge',
            'pattern',
            'session',
            'research',
          ],
        },
        tags: {
          type: 'string',
          description: 'Comma-separated tags (AND filter)',
        },
        tags_any: {
          type: 'string',
          description: 'Comma-separated tags (OR filter)',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results (default: 50)',
          default: 50,
        },
        offset: {
          type: 'number',
          description: 'Result offset for pagination (default: 0)',
          default: 0,
        },
      },
    },
  };
}

/**
 * Handle mem_search tool call.
 */
export async function handleMemSearch(
  args: {
    query?: string;
    vault?: string;
    project?: string;
    note_type?: string;
    tags?: string;
    tags_any?: string;
    limit?: number;
    offset?: number;
  },
  apiClient: ApiClient
): Promise<CallToolResult> {
  const results = await apiClient.searchNotes({
    q: args.query,
    vault: args.vault,
    project: args.project,
    note_type: args.note_type,
    tags: args.tags,
    tags_any: args.tags_any,
    limit: args.limit || 50,
    offset: args.offset || 0,
  });

  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify(
          {
            results: results.results.map((r) => ({
              note_id: r.note_id,
              vault_name: r.vault_name,
              relative_path: r.relative_path,
              permalink: r.permalink,
              title: r.title,
              note_type: r.note_type,
              project: r.project,
              snippet: r.snippet,
              score: r.score,
              tags: r.tags,
            })),
            total_count: results.total_count,
            query: results.query,
            took_ms: results.took_ms,
          },
          null,
          2
        ),
      } as TextContent,
    ],
    isError: false,
  };
}
