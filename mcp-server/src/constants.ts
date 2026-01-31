/**
 * Constants for Obsidian-Memory MCP server.
 */

const env = process.env as Record<string, string | undefined>;

/**
 * API base URL for the Obsidian-Memory backend.
 */
export const API_BASE_URL = env['OBSIDIAN_MEMORY_API_URL'] || 'http://localhost:8000';

/**
 * Maximum character limit for response content to prevent context overflow.
 */
export const CHARACTER_LIMIT = 100000;

/**
 * Default pagination limit for search results.
 */
export const DEFAULT_LIMIT = 50;

/**
 * Maximum pagination limit allowed.
 */
export const MAX_LIMIT = 1000;

/**
 * Default search result sort order.
 */
export const DEFAULT_SORT = 'relevance';

/**
 * Valid note types.
 */
export const NOTE_TYPES = [
  'note',
  'decision',
  'error',
  'knowledge',
  'pattern',
  'session',
  'research',
] as const;

export type NoteType = (typeof NOTE_TYPES)[number];

/**
 * Valid sort options for search.
 */
export const SORT_OPTIONS = [
  'relevance',
  'created_desc',
  'created_asc',
  'updated_desc',
  'updated_asc',
  'title_asc',
] as const;

export type SortOption = (typeof SORT_OPTIONS)[number];

/**
 * Valid session event types.
 */
export const SESSION_EVENT_TYPES = [
  'observation',
  'decision',
  'error',
  'solution',
  'tool_use',
  'file_edit',
  'command',
  'research',
  'user_prompt',
] as const;

export type SessionEventType = (typeof SESSION_EVENT_TYPES)[number];

/**
 * Graph traversal methods.
 */
export const TRAVERSAL_METHODS = ['bfs', 'dfs'] as const;

export type TraversalMethod = (typeof TRAVERSAL_METHODS)[number];

/**
 * Graph edge directions.
 */
export const EDGE_DIRECTIONS = ['outgoing', 'incoming', 'both'] as const;

export type EdgeDirection = (typeof EDGE_DIRECTIONS)[number];

/**
 * Similarity methods for graph_similar.
 */
export const SIMILARITY_METHODS = ['graph', 'content', 'hybrid'] as const;

export type SimilarityMethod = (typeof SIMILARITY_METHODS)[number];

/**
 * Response format options.
 */
export const RESPONSE_FORMATS = ['json', 'markdown'] as const;

export type ResponseFormat = (typeof RESPONSE_FORMATS)[number];
