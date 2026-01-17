/**
 * Context building tool for Obsidian-Memory MCP server.
 * Supports memory:// URI patterns for flexible note selection.
 */

import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { ApiClient } from '../client.js';

const API_BASE_URL = process.env.OBSIDIAN_MEMORY_API_URL || 'http://localhost:8000';
const client = new ApiClient(API_BASE_URL);

/**
 * Parse a memory:// URI pattern.
 *
 * Supported patterns:
 * - memory://note/{id} - Note by ID
 * - memory://note/{permalink} - Note by permalink
 * - memory://search/{query} - Search query
 * - memory://path/{vault}/{path} - Note by path
 * - memory://graph/neighbors/{id} - Neighbors of a note
 * - memory://graph/path/{from_id}/{to_id} - Path between notes
 * - memory://graph/reachable/{id} - All reachable nodes
 * - memory://tags/{tag1,tag2} - Notes with tags
 * - memory://project/{project} - Notes in project
 */
export function parseMemoryUri(uri: string): {
  type: string;
  params: Record<string, string>;
} {
  if (!uri.startsWith('memory://')) {
    throw new Error(`Invalid memory URI: ${uri}`);
  }

  const path = uri.slice('memory://'.length);
  const parts = path.split('/').filter(Boolean);

  if (parts.length === 0) {
    throw new Error(`Invalid memory URI format: ${uri}`);
  }

  const type = parts[0];
  const params: Record<string, string> = {};

  switch (type) {
    case 'note':
      if (parts.length < 2) {
        throw new Error(`Invalid memory://note URI: ${uri}`);
      }
      // Check if it's a number (ID) or string (permalink)
      const noteRef = parts[1];
      if (/^\d+$/.test(noteRef)) {
        params.id = noteRef;
      } else {
        params.permalink = noteRef;
      }
      break;

    case 'search':
      if (parts.length < 2) {
        throw new Error(`Invalid memory://search URI: ${uri}`);
      }
      params.query = decodeURIComponent(parts.slice(1).join('/'));
      break;

    case 'path':
      if (parts.length < 3) {
        throw new Error(`Invalid memory://path URI: ${uri}`);
      }
      params.vault = parts[1];
      params.path = parts.slice(2).join('/');
      break;

    case 'graph':
      if (parts.length < 2) {
        throw new Error(`Invalid memory://graph URI: ${uri}`);
      }
      const graphOp = parts[1];
      params.operation = graphOp;

      switch (graphOp) {
        case 'neighbors':
        case 'reachable':
          if (parts.length < 3) {
            throw new Error(`Invalid memory://graph/${graphOp} URI: ${uri}`);
          }
          params.node_id = parts[2];
          break;

        case 'path':
          if (parts.length < 4) {
            throw new Error(`Invalid memory://graph/path URI: ${uri}`);
          }
          params.from_id = parts[2];
          params.to_id = parts[3];
          break;

        default:
          throw new Error(`Unknown graph operation: ${graphOp}`);
      }
      break;

    case 'tags':
      if (parts.length < 2) {
        throw new Error(`Invalid memory://tags URI: ${uri}`);
      }
      params.tags = parts[1];
      break;

    case 'project':
      if (parts.length < 2) {
        throw new Error(`Invalid memory://project URI: ${uri}`);
      }
      params.project = parts[1];
      break;

    default:
      throw new Error(`Unknown memory URI type: ${type}`);
  }

  return { type, params };
}

/**
 * Build context from memory:// URI patterns.
 */
export async function buildContext(uris: string[]): Promise<{
  content: string;
  notes: unknown[];
  total_notes: number;
}> {
  const notes: unknown[] = [];
  const noteIds = new Set<number>();

  for (const uri of uris) {
    const { type, params } = parseMemoryUri(uri);

    switch (type) {
      case 'note': {
        let note;
        if (params.id) {
          note = await client.getNoteById(parseInt(params.id, 10));
        } else if (params.permalink) {
          // Search by permalink
          const results = await client.searchNotes({
            query: `permalink:${params.permalink}`,
            limit: 1,
          });
          if (results.notes.length > 0) {
            note = await client.getNoteById(results.notes[0].id!);
          }
        }
        if (note && note.id && !noteIds.has(note.id)) {
          notes.push(note);
          noteIds.add(note.id);
        }
        break;
      }

      case 'search': {
        const results = await client.searchNotes({
          query: params.query,
          limit: 50,
        });
        for (const result of results.notes) {
          if (result.id && !noteIds.has(result.id)) {
            const fullNote = await client.getNoteById(result.id);
            if (fullNote) {
              notes.push(fullNote);
              noteIds.add(result.id);
            }
          }
        }
        break;
      }

      case 'path': {
        // Note: This would require a new API endpoint
        // For now, search by path
        const results = await client.searchNotes({
          query: `path:${params.path}`,
          vault: params.vault,
          limit: 1,
        });
        if (results.notes.length > 0) {
          const note = await client.getNoteById(results.notes[0].id!);
          if (note && note.id && !noteIds.has(note.id)) {
            notes.push(note);
            noteIds.add(note.id);
          }
        }
        break;
      }

      case 'graph': {
        // Graph operations would require graph API endpoints
        // For now, return empty or placeholder
        // TODO: Implement when graph API is available
        break;
      }

      case 'tags': {
        const tagList = params.tags.split(',').map((t) => t.trim());
        const results = await client.searchNotes({
          query: '*',
          tags: tagList,
          limit: 50,
        });
        for (const result of results.notes) {
          if (result.id && !noteIds.has(result.id)) {
            const fullNote = await client.getNoteById(result.id);
            if (fullNote) {
              notes.push(fullNote);
              noteIds.add(result.id);
            }
          }
        }
        break;
      }

      case 'project': {
        const results = await client.searchNotes({
          query: '*',
          project: params.project,
          limit: 50,
        });
        for (const result of results.notes) {
          if (result.id && !noteIds.has(result.id)) {
            const fullNote = await client.getNoteById(result.id);
            if (fullNote) {
              notes.push(fullNote);
              noteIds.add(result.id);
            }
          }
        }
        break;
      }
    }
  }

  // Format context
  const contentParts: string[] = [];
  for (const note of notes) {
    const n = note as {
      title: string;
      content: string;
      vault_name: string;
      relative_path: string;
      permalink: string | null;
      tags: string[];
      created_at: string | null;
      updated_at: string | null;
    };

    contentParts.push(`# ${n.title}`);
    if (n.permalink) {
      contentParts.push(`**Permalink:** ${n.permalink}`);
    }
    if (n.tags.length > 0) {
      contentParts.push(`**Tags:** ${n.tags.join(', ')}`);
    }
    if (n.created_at) {
      contentParts.push(`**Created:** ${n.created_at}`);
    }
    if (n.updated_at) {
      contentParts.push(`**Updated:** ${n.updated_at}`);
    }
    contentParts.push('');
    contentParts.push('---');
    contentParts.push('');
    contentParts.push(n.content);
    contentParts.push('');
    contentParts.push('');
  }

  return {
    content: contentParts.join('\n'),
    notes,
    total_notes: notes.length,
  };
}

/**
 * build_context tool definition.
 */
export const buildContextTool: Tool = {
  name: 'build_context',
  description:
    'Build context from memory:// URI patterns. Supports note selection by ID, permalink, search, path, tags, project, and graph operations.',
  inputSchema: {
    type: 'object',
    properties: {
      uris: {
        type: 'array',
        items: { type: 'string' },
        description:
          'Array of memory:// URI patterns to include in context',
        examples: [
          'memory://note/123',
          'memory://note/auth-jwt-impl',
          'memory://search/authentication',
          'memory://path/test_vault/projects/api/auth.md',
          'memory://tags/security,backend',
          'memory://project/api-service',
        ],
      },
    },
    required: ['uris'],
  },
};

/**
 * Handle build_context tool call.
 */
export async function handleBuildContext(args: {
  uris: string[];
}): Promise<{ content: string; notes: unknown[]; total_notes: number }> {
  return buildContext(args.uris);
}
