/**
 * Context building tool for Obsidian-Memory MCP server.
 * Supports memory:// URI patterns for flexible note selection.
 */

/**
 * Context building utilities for Obsidian-Memory MCP server.
 * Supports memory:// URI patterns for flexible note selection.
 */

import { apiClient } from '../client.js';

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
  params: Record<string, string | undefined>;
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
  const params: Record<string, string | undefined> = {};

  switch (type) {
    case 'note':
      if (parts.length < 2 || !parts[1]) {
        throw new Error(`Invalid memory://note URI: ${uri}`);
      }
      // Check if it's a number (ID) or string (permalink)
      const noteRef: string = parts[1];
      if (/^\d+$/.test(noteRef)) {
        params['id'] = noteRef;
      } else {
        params['permalink'] = noteRef;
      }
      break;

    case 'search':
      if (parts.length < 2) {
        throw new Error(`Invalid memory://search URI: ${uri}`);
      }
      params['query'] = decodeURIComponent(parts.slice(1).join('/'));
      break;

    case 'path':
      if (parts.length < 3) {
        throw new Error(`Invalid memory://path URI: ${uri}`);
      }
      params['vault'] = parts[1];
      params['path'] = parts.slice(2).join('/');
      break;

    case 'graph':
      if (parts.length < 2) {
        throw new Error(`Invalid memory://graph URI: ${uri}`);
      }
      const graphOp = parts[1];
      params['operation'] = graphOp;

      switch (graphOp) {
        case 'neighbors':
        case 'reachable':
          if (parts.length < 3) {
            throw new Error(`Invalid memory://graph/${graphOp} URI: ${uri}`);
          }
          params['node_id'] = parts[2];
          break;

        case 'path':
          if (parts.length < 4) {
            throw new Error(`Invalid memory://graph/path URI: ${uri}`);
          }
          params['from_id'] = parts[2];
          params['to_id'] = parts[3];
          break;

        default:
          throw new Error(`Unknown graph operation: ${graphOp}`);
      }
      break;

    case 'tags':
      if (parts.length < 2) {
        throw new Error(`Invalid memory://tags URI: ${uri}`);
      }
      params['tags'] = parts[1];
      break;

    case 'project':
      if (parts.length < 2) {
        throw new Error(`Invalid memory://project URI: ${uri}`);
      }
      params['project'] = parts[1];
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
        const noteId = params['id'];
        const permalink = params['permalink'];
        if (noteId && typeof noteId === 'string') {
          note = await apiClient.getNoteById(parseInt(noteId, 10));
        } else if (permalink) {
          // Search by permalink
          const results = await apiClient.searchNotes({
            query: `permalink:${permalink}`,
            limit: 1,
          });
          if (results.notes.length > 0 && results.notes[0]?.['id']) {
            note = await apiClient.getNoteById(results.notes[0]['id']!);
          }
        }
        if (note && note['id'] && !noteIds.has(note['id'])) {
          notes.push(note);
          noteIds.add(note['id']);
        }
        break;
      }

      case 'search': {
        const query = params['query'];
        if (!query) {
          throw new Error('Search query is required');
        }
        const results = await apiClient.searchNotes({
          query: query,
          limit: 50,
        });
        for (const result of results.notes) {
          if (result.id && !noteIds.has(result.id)) {
            const fullNote = await apiClient.getNoteById(result.id);
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
        const path = params['path'];
        const vault = params['vault'];
        if (!path) {
          throw new Error('Path is required');
        }
        const results = await apiClient.searchNotes({
          query: `path:${path}`,
          vault: vault || null,
          limit: 1,
        });
        if (results.notes.length > 0 && results.notes[0]?.['id']) {
          const note = await apiClient.getNoteById(results.notes[0]['id']!);
          if (note && note['id'] && !noteIds.has(note['id'])) {
            notes.push(note);
            noteIds.add(note['id']);
          }
        }
        break;
      }

      case 'graph': {
        const operation = params['operation'];
        const nodeId = params['node_id'];
        const fromId = params['from_id'];
        const toId = params['to_id'];

        switch (operation) {
          case 'neighbors': {
            if (!nodeId) {
              throw new Error('Node ID required for neighbors operation');
            }
            const neighborsResult = await apiClient.getGraphNeighbors(
              parseInt(nodeId, 10),
              'both'
            );
            // Fetch full note details for each neighbor
            for (const neighborId of neighborsResult.neighbors) {
              if (!noteIds.has(neighborId)) {
                try {
                  const note = await apiClient.getNoteById(neighborId);
                  if (note && note.id) {
                    notes.push(note);
                    noteIds.add(note.id);
                  }
                } catch {
                  // Skip notes that can't be fetched
                }
              }
            }
            break;
          }

          case 'reachable': {
            if (!nodeId) {
              throw new Error('Node ID required for reachable operation');
            }
            // Use BFS traversal to find all reachable nodes
            const traverseResult = await apiClient.traverseGraph({
              start_node_id: parseInt(nodeId, 10),
              method: 'bfs',
              max_depth: 5,
              direction: 'both',
            });
            // Fetch full note details for each visited node
            for (const visitedId of traverseResult.visited_nodes) {
              if (!noteIds.has(visitedId)) {
                try {
                  const note = await apiClient.getNoteById(visitedId);
                  if (note && note.id) {
                    notes.push(note);
                    noteIds.add(note.id);
                  }
                } catch {
                  // Skip notes that can't be fetched
                }
              }
            }
            break;
          }

          case 'path': {
            if (!fromId || !toId) {
              throw new Error('Both from_id and to_id required for path operation');
            }
            // Use BFS with target to find path
            const pathResult = await apiClient.traverseGraph({
              start_node_id: parseInt(fromId, 10),
              target_node_id: parseInt(toId, 10),
              method: 'bfs',
              max_depth: 10,
              direction: 'both',
            });
            // Collect all nodes from paths found
            const pathNodes = new Set<number>();
            for (const path of pathResult.paths) {
              for (const pathNodeId of path) {
                pathNodes.add(pathNodeId);
              }
            }
            // Also add start node
            pathNodes.add(parseInt(fromId, 10));
            // Fetch full note details for path nodes
            for (const pathNodeId of pathNodes) {
              if (!noteIds.has(pathNodeId)) {
                try {
                  const note = await apiClient.getNoteById(pathNodeId);
                  if (note && note.id) {
                    notes.push(note);
                    noteIds.add(note.id);
                  }
                } catch {
                  // Skip notes that can't be fetched
                }
              }
            }
            break;
          }

          default:
            throw new Error(`Unknown graph operation: ${operation}`);
        }
        break;
      }

      case 'tags': {
        const tagsStr = params['tags'];
        if (!tagsStr) {
          throw new Error('Tags are required');
        }
        const tagList = tagsStr.split(',').map((t) => t.trim());
        const results = await apiClient.searchNotes({
          query: '*',
          tags: tagList,
          limit: 50,
        });
        for (const result of results.notes) {
          if (result['id'] && !noteIds.has(result['id'])) {
            const fullNote = await apiClient.getNoteById(result['id']);
            if (fullNote) {
              notes.push(fullNote);
              noteIds.add(result['id']);
            }
          }
        }
        break;
      }

      case 'project': {
        const project = params['project'];
        if (!project) {
          throw new Error('Project is required');
        }
        const results = await apiClient.searchNotes({
          query: '*',
          project: project || null,
          limit: 50,
        });
        for (const result of results.notes) {
          if (result.id && !noteIds.has(result.id)) {
            const fullNote = await apiClient.getNoteById(result.id);
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
