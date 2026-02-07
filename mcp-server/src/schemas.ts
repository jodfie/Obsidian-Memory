/**
 * Zod schemas for Obsidian-Memory MCP server tool validation.
 */

import { z } from 'zod';
import {
  NOTE_TYPES,
  SORT_OPTIONS,
  SESSION_EVENT_TYPES,
  TRAVERSAL_METHODS,
  EDGE_DIRECTIONS,
  SIMILARITY_METHODS,
  RESPONSE_FORMATS,
  DEFAULT_LIMIT,
  MAX_LIMIT,
} from './constants.js';

// ============================================================================
// Common Schemas
// ============================================================================

export const responseFormatSchema = z
  .enum(RESPONSE_FORMATS)
  .optional()
  .describe('Response format: "json" for structured data, "markdown" for human-readable text (default: json)');

export const paginationSchema = z.object({
  limit: z
    .number()
    .int()
    .min(1)
    .max(MAX_LIMIT)
    .optional()
    .describe(`Maximum number of results (1-${MAX_LIMIT}, default: ${DEFAULT_LIMIT})`),
  offset: z
    .number()
    .int()
    .min(0)
    .optional()
    .describe('Result offset for pagination (default: 0)'),
});

// ============================================================================
// Memory Tools Schemas
// ============================================================================

export const memReadInputSchema = {
  id: z.number().int().positive().optional().describe('Note ID (if known)'),
  permalink: z.string().optional().describe('Note permalink (if known)'),
  query: z.string().optional().describe('Search query to find note (returns first match)'),
  vault: z.string().optional().describe('Optional vault name to filter search'),
  response_format: responseFormatSchema,
};

export const memWriteInputSchema = {
  note_id: z.number().int().positive().optional().describe('Note ID for update (omit for create)'),
  vault_name: z.string().optional().describe('Vault name (optional, uses default if not provided)'),
  relative_path: z.string().min(1).describe('Relative path for the note (e.g., "projects/api/auth.md")'),
  title: z.string().min(1).describe('Note title'),
  content: z.string().describe('Markdown content of the note'),
  note_type: z.enum(NOTE_TYPES).optional().describe('Type of note (default: note)'),
  project: z.string().optional().describe('Project identifier (optional)'),
  tags: z.array(z.string()).optional().describe('Tags for the note'),
};

export const memSearchInputSchema = {
  query: z.string().min(1).describe('Search query (FTS5 syntax: terms, phrases, boolean operators)'),
  vault: z.string().optional().describe('Filter by vault name'),
  project: z.string().optional().describe('Filter by project'),
  note_type: z.enum(NOTE_TYPES).optional().describe('Filter by note type'),
  tags: z.array(z.string()).optional().describe('Filter by tags (AND - all must match)'),
  tags_any: z.array(z.string()).optional().describe('Filter by tags (OR - any can match)'),
  sort: z.enum(SORT_OPTIONS).optional().describe('Sort order (default: relevance)'),
  limit: z
    .number()
    .int()
    .min(1)
    .max(MAX_LIMIT)
    .optional()
    .describe(`Maximum results (1-${MAX_LIMIT}, default: ${DEFAULT_LIMIT})`),
  offset: z.number().int().min(0).optional().describe('Result offset for pagination (default: 0)'),
  response_format: responseFormatSchema,
};

export const memDeleteInputSchema = {
  id: z.number().int().positive().describe('Note ID to delete'),
};

// ============================================================================
// Context Tool Schemas
// ============================================================================

export const buildContextInputSchema = {
  uris: z
    .array(z.string())
    .min(1)
    .describe(
      'Array of memory:// URI patterns. Examples: "memory://note/123", "memory://search/auth", "memory://tags/security,backend", "memory://project/api"'
    ),
  response_format: responseFormatSchema,
};

// ============================================================================
// Graph Tools Schemas
// ============================================================================

export const graphTraverseInputSchema = {
  start_node_id: z.number().int().positive().describe('Starting node ID'),
  target_node_id: z.number().int().positive().optional().describe('Optional target node ID (stops when found)'),
  method: z.enum(TRAVERSAL_METHODS).optional().describe('Traversal method: bfs or dfs (default: bfs)'),
  max_depth: z.number().int().min(1).max(100).optional().describe('Maximum traversal depth (1-100, default: 10)'),
  direction: z.enum(EDGE_DIRECTIONS).optional().describe('Edge direction to traverse (default: both)'),
  edge_types: z.array(z.string()).optional().describe('Filter by edge types (e.g., ["depends_on", "enables"])'),
  exclude_nodes: z.array(z.number().int()).optional().describe('Node IDs to exclude from traversal'),
  response_format: responseFormatSchema,
};

export const graphSimilarInputSchema = {
  note_id: z.number().int().positive().describe('Source note ID'),
  limit: z.number().int().min(1).max(100).optional().describe('Maximum similar notes to return (1-100, default: 10)'),
  method: z.enum(SIMILARITY_METHODS).optional().describe('Similarity method: graph, content, or hybrid (default: hybrid)'),
  response_format: responseFormatSchema,
};

// ============================================================================
// Project Tools Schemas
// ============================================================================

export const projectListInputSchema = {
  response_format: responseFormatSchema,
};

export const projectSwitchInputSchema = {
  project_name: z.string().min(1).describe('Name of the project to switch to'),
  limit: z.number().int().min(1).max(100).optional().describe('Number of recent notes to return (default: 10)'),
  response_format: responseFormatSchema,
};

export const projectCreateInputSchema = {
  project_name: z
    .string()
    .min(1)
    .regex(/^[a-zA-Z0-9_-]+$/, 'Project name must be alphanumeric, dash, or underscore only')
    .describe('Name of the project to create (alphanumeric, dash, underscore only)'),
};

// ============================================================================
// Session Tools Schemas
// ============================================================================

export const sessionObserveInputSchema = {
  session_id: z.string().min(1).describe('Session ID (create one first if needed)'),
  event_type: z.enum(SESSION_EVENT_TYPES).describe('Type of event'),
  content: z.string().min(1).describe('Event content/description'),
  metadata: z.record(z.unknown()).optional().describe('Optional metadata (e.g., file path, command, tool name)'),
};

export const sessionSummaryInputSchema = {
  session_id: z.string().min(1).describe('Session ID to summarize'),
  response_format: responseFormatSchema,
};

export const sessionContextInputSchema = {
  session_id: z.string().min(1).describe('Session ID'),
  include_events: z.boolean().optional().describe('Include session events (default: true)'),
  include_summary: z.boolean().optional().describe('Include AI summary if available (default: true)'),
  limit: z.number().int().min(1).max(1000).optional().describe('Maximum events to return (default: 50)'),
  response_format: responseFormatSchema,
};
