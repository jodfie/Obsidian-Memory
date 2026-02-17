/**
 * Unified tool handlers for Obsidian-Memory MCP server.
 *
 * These handlers are used by both stdio and SSE transports.
 * All handlers use the singleton apiClient and shared formatters.
 */

import { apiClient, type NoteResponse, type ProfileResponse, ProfileNotFoundError } from './client.js';
import { DEFAULT_LIMIT, type ResponseFormat } from './constants.js';
import {
  formatNote,
  formatSearchResults,
  formatProjectList,
  formatSessionSummary,
  formatGraphTraversal,
  formatSimilarNotes,
  truncateContent,
} from './formatters.js';
import { buildContext } from './tools/context.js';

// ============================================================================
// Response Types
// ============================================================================

export interface ToolResponse {
  content: Array<{ type: 'text'; text: string }>;
  structuredContent?: unknown;
}

// ============================================================================
// Memory Tool Handlers
// ============================================================================

export interface MemReadInput {
  id?: number;
  permalink?: string;
  query?: string;
  vault?: string;
  response_format?: ResponseFormat;
}

export async function handleMemRead({
  id,
  permalink,
  query,
  vault,
  response_format = 'json',
}: MemReadInput): Promise<ToolResponse> {
  let note: NoteResponse;

  if (id) {
    note = await apiClient.getNoteById(id);
  } else if (permalink) {
    const results = await apiClient.searchNotes({
      query: `permalink:${permalink}`,
      vault: vault || null,
      limit: 1,
    });
    if (results.notes.length === 0 || !results.notes[0]?.id) {
      throw new Error(`Note with permalink "${permalink}" not found`);
    }
    note = await apiClient.getNoteById(results.notes[0].id);
  } else if (query) {
    const results = await apiClient.searchNotes({
      query,
      vault: vault || null,
      limit: 1,
    });
    if (results.notes.length === 0 || !results.notes[0]?.id) {
      throw new Error(`No notes found matching query: "${query}"`);
    }
    note = await apiClient.getNoteById(results.notes[0].id);
  } else {
    throw new Error('Must provide id, permalink, or query');
  }

  const text = formatNote(note, response_format);
  return {
    content: [{ type: 'text', text }],
    structuredContent: { note },
  };
}

export interface MemWriteInput {
  note_id?: number;
  vault_name?: string;
  relative_path: string;
  title: string;
  content: string;
  note_type?: string;
  project?: string;
  tags?: string[];
}

export async function handleMemWrite({
  note_id,
  vault_name,
  relative_path,
  title,
  content,
  note_type,
  project,
  tags,
}: MemWriteInput): Promise<ToolResponse> {
  let result: NoteResponse;
  let message: string;

  if (note_id) {
    const note = await apiClient.updateNote(note_id, {
      title,
      content,
      note_type: note_type || null,
      project: project || null,
      tags: tags || null,
    });
    result = note;
    message = `Note updated: ${note.title} (ID: ${note.id})`;
  } else {
    const note = await apiClient.createNote({
      vault_name: vault_name || null,
      relative_path,
      title,
      content,
      note_type: note_type || 'note',
      project: project || null,
      tags: tags || [],
    });
    result = note;
    message = `Note created: ${note.title} (ID: ${note.id})`;
  }

  return {
    content: [{ type: 'text', text: message }],
    structuredContent: { note: result, message },
  };
}

export interface MemDeleteInput {
  id: number;
}

export async function handleMemDelete({
  id,
}: MemDeleteInput): Promise<ToolResponse> {
  const result = await apiClient.deleteNote(id);

  return {
    content: [{ type: 'text', text: result.message || `Note ${id} deleted successfully` }],
    structuredContent: result,
  };
}

export interface MemSearchInput {
  query: string;
  vault?: string;
  project?: string;
  note_type?: string;
  tags?: string[];
  tags_any?: string[];
  sort?: string;
  limit?: number;
  offset?: number;
  include_expired?: boolean;
  response_format?: ResponseFormat;
}

export async function handleMemSearch({
  query,
  vault,
  project,
  note_type,
  tags,
  tags_any,
  sort,
  limit,
  offset,
  include_expired,
  response_format = 'json',
}: MemSearchInput): Promise<ToolResponse> {
  const results = await apiClient.searchNotes({
    query,
    vault: vault || null,
    project: project || null,
    note_type: note_type || null,
    ...(tags && { tags }),
    ...(tags_any && { tags_any }),
    sort: sort || 'relevance',
    limit: limit || DEFAULT_LIMIT,
    offset: offset || 0,
    ...(include_expired !== undefined && { include_expired }),
  });

  const actualOffset = offset || 0;
  const hasMore = actualOffset + results.notes.length < results.total;
  const nextOffset = actualOffset + results.notes.length;

  const text = formatSearchResults(results, query, response_format, hasMore, nextOffset);

  return {
    content: [{ type: 'text', text }],
    structuredContent: {
      query,
      total: results.total,
      count: results.notes.length,
      has_more: hasMore,
      next_offset: hasMore ? nextOffset : null,
      notes: results.notes,
    },
  };
}

export interface MemSupersedeInput {
  old_note_id: number;
  new_note_id: number;
  reason?: string;
  response_format?: ResponseFormat;
}

export async function handleMemSupersede({
  old_note_id,
  new_note_id,
  reason,
  response_format = 'json',
}: MemSupersedeInput): Promise<ToolResponse> {
  const result = await apiClient.supersedeNote(old_note_id, new_note_id, reason);

  let text: string;
  if (response_format === 'markdown') {
    text = `## Note Superseded

**Old Note:** ${result.old_note_title} (ID: ${result.old_note_id})
**New Note:** ${result.new_note_title} (ID: ${result.new_note_id})

${result.message}`;
  } else {
    text = JSON.stringify(result, null, 2);
  }

  return {
    content: [{ type: 'text', text }],
    structuredContent: result,
  };
}

// ============================================================================
// Context Tool Handler
// ============================================================================

export interface BuildContextInput {
  uris: string[];
  response_format?: ResponseFormat;
}

export async function handleBuildContext({
  uris,
  response_format = 'json',
}: BuildContextInput): Promise<ToolResponse> {
  const result = await buildContext(uris);

  if (response_format === 'markdown') {
    return {
      content: [{ type: 'text', text: truncateContent(result.content) }],
      structuredContent: result,
    };
  }

  return {
    content: [{ type: 'text', text: truncateContent(JSON.stringify(result, null, 2)) }],
    structuredContent: result,
  };
}

// ============================================================================
// Graph Tool Handlers
// ============================================================================

export interface GraphTraverseInput {
  start_node_id: number;
  target_node_id?: number;
  method?: 'bfs' | 'dfs';
  max_depth?: number;
  direction?: 'outgoing' | 'incoming' | 'both';
  edge_types?: string[];
  exclude_nodes?: number[];
  response_format?: ResponseFormat;
}

export async function handleGraphTraverse({
  start_node_id,
  target_node_id,
  method = 'bfs',
  max_depth = 10,
  direction = 'outgoing',
  edge_types,
  exclude_nodes,
  response_format = 'json',
}: GraphTraverseInput): Promise<ToolResponse> {
  const result = await apiClient.traverseGraph({
    start_node_id,
    ...(target_node_id !== undefined && { target_node_id }),
    method,
    max_depth,
    direction,
    ...(edge_types !== undefined && { edge_types }),
    ...(exclude_nodes !== undefined && { exclude_nodes }),
  });

  const text = formatGraphTraversal(result, response_format);

  return {
    content: [{ type: 'text', text }],
    structuredContent: result,
  };
}

export interface GraphSimilarInput {
  note_id: number;
  limit?: number;
  method?: 'graph' | 'content' | 'hybrid';
  response_format?: ResponseFormat;
}

export async function handleGraphSimilar({
  note_id,
  limit = 10,
  method = 'hybrid',
  response_format = 'json',
}: GraphSimilarInput): Promise<ToolResponse> {
  const result = await apiClient.findSimilarNotes(note_id, limit, method);

  const formattedResult = {
    similar_notes: result.similar_notes,
    scores: result.similar_notes.map((n) => ({ note_id: n.note_id, score: n.score })),
  };

  const text = formatSimilarNotes(formattedResult, response_format);

  return {
    content: [{ type: 'text', text }],
    structuredContent: result,
  };
}

// ============================================================================
// Project Tool Handlers
// ============================================================================

export interface ProjectListInput {
  response_format?: ResponseFormat;
}

export async function handleProjectList({
  response_format = 'json',
}: ProjectListInput = {}): Promise<ToolResponse> {
  const result = await apiClient.listProjects();
  const text = formatProjectList(result.projects, response_format);

  return {
    content: [{ type: 'text', text }],
    structuredContent: result,
  };
}

export interface ProjectSwitchInput {
  project_name: string;
  limit?: number;
  response_format?: ResponseFormat;
}

export async function handleProjectSwitch({
  project_name,
  limit,
  response_format = 'json',
}: ProjectSwitchInput): Promise<ToolResponse> {
  const projectNotes = await apiClient.listProjectNotes(project_name, limit || 10, 0);
  const projects = await apiClient.listProjects();
  const project = projects.projects.find((p) => p.name === project_name);

  const result = {
    project: project_name,
    note_count: project?.note_count || projectNotes.total_count,
    recent_notes: projectNotes.notes,
  };

  if (response_format === 'markdown') {
    const parts = [
      `# Project: ${project_name}`,
      '',
      `**Notes:** ${result.note_count}`,
      '',
      '## Recent Notes',
      ...projectNotes.notes.map((n) => `- **${n.title}** (${n.note_type})`),
    ];
    return {
      content: [{ type: 'text', text: parts.join('\n') }],
      structuredContent: result,
    };
  }

  return {
    content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
    structuredContent: result,
  };
}

export interface ProjectCreateInput {
  project_name: string;
}

export async function handleProjectCreate({
  project_name,
}: ProjectCreateInput): Promise<ToolResponse> {
  const result = await apiClient.createProject(project_name);

  return {
    content: [{ type: 'text', text: result.message }],
    structuredContent: result,
  };
}

// ============================================================================
// Session Tool Handlers
// ============================================================================

export interface SessionObserveInput {
  session_id: string;
  event_type: string;
  content: string;
  metadata?: Record<string, unknown>;
  custom_id?: string;
}

export async function handleSessionObserve({
  session_id,
  event_type,
  content,
  metadata,
  custom_id,
}: SessionObserveInput): Promise<ToolResponse> {
  const result = await apiClient.observeSessionEvent(session_id, event_type, content, metadata, custom_id);

  return {
    content: [{ type: 'text', text: `Event recorded in session ${session_id} (${result.event_count} total events)` }],
    structuredContent: result,
  };
}

export interface SessionSummaryInput {
  session_id: string;
  response_format?: ResponseFormat;
}

export async function handleSessionSummary({
  session_id,
  response_format = 'json',
}: SessionSummaryInput): Promise<ToolResponse> {
  const result = await apiClient.summarizeSession(session_id);
  const text = formatSessionSummary(result, response_format);

  return {
    content: [{ type: 'text', text }],
    structuredContent: result,
  };
}

export interface SessionContextInput {
  session_id: string;
  include_events?: boolean;
  include_summary?: boolean;
  limit?: number;
  response_format?: ResponseFormat;
}

export async function handleSessionContext({
  session_id,
  include_events = true,
  include_summary = true,
  limit = 50,
  response_format = 'json',
}: SessionContextInput): Promise<ToolResponse> {
  const result = await apiClient.getSessionContext(
    session_id,
    include_events,
    include_summary,
    limit
  );

  if (response_format === 'markdown') {
    const parts = [
      `# Session: ${session_id}`,
      '',
      `**Project:** ${result.project || 'None'}`,
      `**Status:** ${result.status}`,
      `**Started:** ${result.started_at}`,
      result.ended_at ? `**Ended:** ${result.ended_at}` : '',
      `**Events:** ${result.event_count}`,
    ];

    if (result.events && result.events.length > 0) {
      parts.push('', '## Events', '');
      result.events.forEach((e) => {
        parts.push(`### ${e.event_type} (${e.timestamp})`);
        parts.push(e.content);
        parts.push('');
      });
    }

    if (result.summary) {
      parts.push('', '## Summary', '', result.summary.summary_text);
    }

    return {
      content: [{ type: 'text', text: truncateContent(parts.filter(Boolean).join('\n')) }],
      structuredContent: result,
    };
  }

  return {
    content: [{ type: 'text', text: truncateContent(JSON.stringify(result, null, 2)) }],
    structuredContent: result,
  };
}

// ============================================================================
// Profile Tool Handlers
// ============================================================================

export interface GetProfileInput {
  project: string;
  response_format?: ResponseFormat;
}

export async function handleGetProfile({
  project,
  response_format = 'json',
}: GetProfileInput): Promise<ToolResponse> {
  try {
    const profile = await apiClient.getProfile(project);

    if (response_format === 'markdown') {
      const text = formatProfile(profile);
      return {
        content: [{ type: 'text', text }],
        structuredContent: profile,
      };
    }

    return {
      content: [{ type: 'text', text: JSON.stringify(profile, null, 2) }],
      structuredContent: profile,
    };
  } catch (error) {
    if (error instanceof ProfileNotFoundError) {
      const message =
        `No profile synthesized yet for project: ${project}.\n` +
        `To create one, use the POST /api/profile/${project}/synthesize endpoint ` +
        `or write more notes to trigger auto-synthesis.`;
      return {
        content: [{ type: 'text', text: message }],
      };
    }
    throw error;
  }
}

function formatProfile(profile: ProfileResponse): string {
  const lines: string[] = [];

  lines.push(`# Profile: ${profile.project}`);
  lines.push(`*Version ${profile.profile_version} | ${profile.synthesis_note_count} notes analyzed*`);
  if (profile.last_synthesized) {
    lines.push(`*Last synthesized: ${profile.last_synthesized}*`);
  }
  lines.push('');

  if (profile.static_facts.length > 0) {
    lines.push('## Static Profile');
    for (const fact of profile.static_facts) {
      lines.push(`- ${fact}`);
    }
    lines.push('');
  }

  if (profile.dynamic_patterns.length > 0) {
    lines.push('## Dynamic Patterns');
    for (const pattern of profile.dynamic_patterns) {
      lines.push(`- ${pattern}`);
    }
    lines.push('');
  }

  if (Object.keys(profile.key_entities).length > 0) {
    lines.push('## Key Entities');
    for (const [category, entities] of Object.entries(profile.key_entities)) {
      lines.push(`**${category}**: ${entities.join(', ')}`);
    }
    lines.push('');
  }

  return lines.join('\n');
}

// ============================================================================
// Tool Dispatcher
// ============================================================================

/**
 * Dispatch a tool call to the appropriate handler.
 * Used by the SSE transport to handle tools via HTTP.
 */
export async function dispatchToolCall(
  toolName: string,
  args: Record<string, unknown>
): Promise<ToolResponse> {
  // Use unknown as intermediate cast for type safety with Record<string, unknown>
  switch (toolName) {
    case 'mem_read':
      return handleMemRead(args as unknown as MemReadInput);
    case 'mem_write':
      return handleMemWrite(args as unknown as MemWriteInput);
    case 'mem_search':
      return handleMemSearch(args as unknown as MemSearchInput);
    case 'mem_delete':
      return handleMemDelete(args as unknown as MemDeleteInput);
    case 'mem_supersede':
      return handleMemSupersede(args as unknown as MemSupersedeInput);
    case 'build_context':
      return handleBuildContext(args as unknown as BuildContextInput);
    case 'graph_traverse':
      return handleGraphTraverse(args as unknown as GraphTraverseInput);
    case 'graph_similar':
      return handleGraphSimilar(args as unknown as GraphSimilarInput);
    case 'project_list':
      return handleProjectList(args as unknown as ProjectListInput);
    case 'project_switch':
      return handleProjectSwitch(args as unknown as ProjectSwitchInput);
    case 'project_create':
      return handleProjectCreate(args as unknown as ProjectCreateInput);
    case 'session_observe':
      return handleSessionObserve(args as unknown as SessionObserveInput);
    case 'session_summary':
      return handleSessionSummary(args as unknown as SessionSummaryInput);
    case 'session_context':
      return handleSessionContext(args as unknown as SessionContextInput);
    case 'get_profile':
      return handleGetProfile(args as unknown as GetProfileInput);
    default:
      throw new Error(`Unknown tool: ${toolName}`);
  }
}
