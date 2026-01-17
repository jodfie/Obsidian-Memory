/**
 * Memory management tools for Obsidian-Memory MCP server.
 */

import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { ApiClient } from '../client.js';
import {
  buildContextTool,
  handleBuildContext,
} from './context.js';

const API_BASE_URL = process.env.OBSIDIAN_MEMORY_API_URL || 'http://localhost:8000';
const client = new ApiClient(API_BASE_URL);

/**
 * Tool definitions for memory operations.
 */
export const memoryTools: Tool[] = [
  buildContextTool,
  {
    name: 'mem_read',
    description: 'Read a note from Obsidian-Memory by ID, permalink, or search query. Returns the full note content with metadata.',
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'number',
          description: 'Note ID (if known)',
        },
        permalink: {
          type: 'string',
          description: 'Note permalink (if known)',
        },
        query: {
          type: 'string',
          description: 'Search query to find note (returns first match)',
        },
        vault: {
          type: 'string',
          description: 'Optional vault name to filter search',
        },
      },
      oneOf: [
        { required: ['id'] },
        { required: ['permalink'] },
        { required: ['query'] },
      ],
    },
  },
  {
    name: 'mem_write',
    description: 'Create or update a note in Obsidian-Memory. If note_id is provided, updates existing note; otherwise creates new note.',
    inputSchema: {
      type: 'object',
      properties: {
        note_id: {
          type: 'number',
          description: 'Note ID for update (omit for create)',
        },
        vault_name: {
          type: 'string',
          description: 'Vault name (optional, uses default if not provided)',
        },
        relative_path: {
          type: 'string',
          description: 'Relative path for the note (e.g., "projects/api/auth.md")',
        },
        title: {
          type: 'string',
          description: 'Note title',
        },
        content: {
          type: 'string',
          description: 'Markdown content of the note',
        },
        note_type: {
          type: 'string',
          enum: ['note', 'decision', 'error', 'knowledge', 'pattern', 'session', 'research'],
          description: 'Type of note',
        },
        project: {
          type: 'string',
          description: 'Project identifier (optional)',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Tags for the note',
        },
      },
      required: ['relative_path', 'title', 'content'],
    },
  },
  {
    name: 'mem_search',
    description: 'Search notes in Obsidian-Memory using full-text search with optional filters. Returns matching notes with snippets.',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query (FTS5 syntax supported: terms, phrases, boolean operators)',
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
          enum: ['note', 'decision', 'error', 'knowledge', 'pattern', 'session', 'research'],
          description: 'Filter by note type',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Filter by tags (AND - all must match)',
        },
        tags_any: {
          type: 'array',
          items: { type: 'string' },
          description: 'Filter by tags (OR - any can match)',
        },
        sort: {
          type: 'string',
          enum: ['relevance', 'created_desc', 'created_asc', 'updated_desc', 'updated_asc', 'title_asc'],
          description: 'Sort order',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results (default: 50, max: 1000)',
        },
        offset: {
          type: 'number',
          description: 'Result offset for pagination',
        },
      },
      required: ['query'],
    },
  },
];

/**
 * Handle mem_read tool call.
 */
export async function handleMemRead(args: {
  id?: number;
  permalink?: string;
  query?: string;
  vault?: string;
}): Promise<{ content: string; note: unknown }> {
  let note;

  if (args.id) {
    note = await client.getNoteById(args.id);
  } else if (args.permalink) {
    // Search by permalink - we'll need to search and filter
    const results = await client.searchNotes({
      query: `permalink:${args.permalink}`,
      vault: args.vault || undefined,
      limit: 1,
    });
    if (results.notes.length === 0) {
      throw new Error(`Note with permalink "${args.permalink}" not found`);
    }
    note = await client.getNoteById(results.notes[0].id!);
  } else if (args.query) {
    // Search and return first match
    const results = await client.searchNotes({
      query: args.query,
      vault: args.vault || undefined,
      limit: 1,
    });
    if (results.notes.length === 0) {
      throw new Error(`No notes found matching query: "${args.query}"`);
    }
    note = await client.getNoteById(results.notes[0].id!);
  } else {
    throw new Error('Must provide id, permalink, or query');
  }

  return {
    content: [
      `# ${note.title}`,
      '',
      `**Vault:** ${note.vault_name}`,
      `**Path:** ${note.relative_path}`,
      note.permalink ? `**Permalink:** ${note.permalink}` : '',
      note.project ? `**Project:** ${note.project}` : '',
      note.tags.length > 0 ? `**Tags:** ${note.tags.join(', ')}` : '',
      note.created_at ? `**Created:** ${note.created_at}` : '',
      note.updated_at ? `**Updated:** ${note.updated_at}` : '',
      '',
      '---',
      '',
      note.content,
    ]
      .filter(Boolean)
      .join('\n'),
    note,
  };
}

/**
 * Handle mem_write tool call.
 */
export async function handleMemWrite(args: {
  note_id?: number;
  vault_name?: string;
  relative_path: string;
  title: string;
  content: string;
  note_type?: string;
  project?: string;
  tags?: string[];
}): Promise<{ note: unknown; message: string }> {
  if (args.note_id) {
    // Update existing note
    const note = await client.updateNote(args.note_id, {
      title: args.title,
      content: args.content,
      note_type: args.note_type || undefined,
      project: args.project || undefined,
      tags: args.tags || undefined,
    });
    return {
      note,
      message: `Note updated: ${note.title} (ID: ${note.id})`,
    };
  } else {
    // Create new note
    const note = await client.createNote({
      vault_name: args.vault_name || undefined,
      relative_path: args.relative_path,
      title: args.title,
      content: args.content,
      note_type: args.note_type || 'note',
      project: args.project || undefined,
      tags: args.tags || [],
    });
    return {
      note,
      message: `Note created: ${note.title} (ID: ${note.id})`,
    };
  }
}

/**
 * Handle mem_search tool call.
 */
export async function handleMemSearch(args: {
  query: string;
  vault?: string;
  project?: string;
  note_type?: string;
  tags?: string[];
  tags_any?: string[];
  sort?: string;
  limit?: number;
  offset?: number;
}): Promise<{ results: unknown[]; total: number; query: string }> {
  const results = await client.searchNotes({
    query: args.query,
    vault: args.vault || undefined,
    project: args.project || undefined,
    note_type: args.note_type || undefined,
    tags: args.tags || undefined,
    tags_any: args.tags_any || undefined,
    sort: args.sort || 'relevance',
    limit: args.limit || 50,
    offset: args.offset || 0,
  });

  return {
    results: results.notes,
    total: results.total,
    query: args.query,
  };
}
