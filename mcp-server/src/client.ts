/**
 * HTTP client for communicating with the Obsidian-Memory backend API.
 */

import { API_BASE_URL } from './constants.js';

// Get API token from environment (using bracket notation for TypeScript)
const API_TOKEN: string | null = (process.env as Record<string, string | undefined>)['OBSIDIAN_MEMORY_API_TOKEN'] || null;

export interface NoteResponse {
  id: number | null;
  vault_name: string;
  relative_path: string;
  permalink: string | null;
  title: string;
  note_type: string;
  project: string | null;
  content: string;
  tags: string[];
  created_at: string | null;
  updated_at: string | null;
}

export interface NoteListResponse {
  notes: NoteResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface NoteCreateRequest {
  vault_name?: string | null;
  relative_path: string;
  title: string;
  content: string;
  note_type?: string;
  project?: string | null;
  tags?: string[];
}

export interface NoteUpdateRequest {
  title?: string | null;
  content?: string | null;
  note_type?: string | null;
  project?: string | null;
  tags?: string[] | null;
}

export interface SearchRequest {
  query?: string;
  vault?: string | null;
  project?: string | null;
  note_type?: string | null;
  tags?: string[];
  tags_any?: string[];
  sort?: string;
  limit?: number;
  offset?: number;
  include_expired?: boolean;
}

export class ApiClient {
  private baseUrl: string;
  private apiToken: string | null;

  constructor(baseUrl: string = 'http://localhost:8000', apiToken?: string | null) {
    this.baseUrl = baseUrl.replace(/\/$/, ''); // Remove trailing slash
    this.apiToken = apiToken || API_TOKEN;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this.apiToken) {
      headers['Authorization'] = `Bearer ${this.apiToken}`;
    }
    return headers;
  }

  /**
   * Get a note by ID.
   */
  async getNoteById(id: number): Promise<NoteResponse> {
    const response = await fetch(`${this.baseUrl}/api/notes/${id}`, {
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Note with ID ${id} not found`);
      }
      throw new Error(`Failed to get note: ${response.statusText}`);
    }
    return response.json() as Promise<NoteResponse>;
  }

  /**
   * Create a new note.
   */
  async createNote(request: NoteCreateRequest): Promise<NoteResponse> {
    const response = await fetch(`${this.baseUrl}/api/notes`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to create note: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<NoteResponse>;
  }

  /**
   * Update an existing note.
   */
  async updateNote(id: number, request: NoteUpdateRequest): Promise<NoteResponse> {
    const response = await fetch(`${this.baseUrl}/api/notes/${id}`, {
      method: 'PUT',
      headers: this.getHeaders(),
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Note with ID ${id} not found`);
      }
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to update note: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<NoteResponse>;
  }

  /**
   * Search notes.
   */
  async searchNotes(request: SearchRequest): Promise<NoteListResponse> {
    const response = await fetch(`${this.baseUrl}/api/notes/search`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to search notes: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<NoteListResponse>;
  }

  /**
   * List notes with optional filtering.
   */
  async listNotes(params: {
    vault?: string | null;
    project?: string | null;
    limit?: number;
    offset?: number;
  }): Promise<NoteListResponse> {
    const queryParams = new URLSearchParams();
    if (params.vault) queryParams.append('vault', params.vault);
    if (params.project) queryParams.append('project', params.project);
    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.offset) queryParams.append('offset', params.offset.toString());

    const url = `${this.baseUrl}/api/notes${queryParams.toString() ? `?${queryParams}` : ''}`;
    const response = await fetch(url, {
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      throw new Error(`Failed to list notes: ${response.statusText}`);
    }
    return response.json() as Promise<NoteListResponse>;
  }

  /**
   * List all projects.
   */
  async listProjects(): Promise<{ projects: Array<{ name: string; note_count: number }> }> {
    const response = await fetch(`${this.baseUrl}/api/projects`, {
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      throw new Error(`Failed to list projects: ${response.statusText}`);
    }
    return response.json() as Promise<{ projects: Array<{ name: string; note_count: number }> }>;
  }

  /**
   * List notes for a specific project.
   */
  async listProjectNotes(
    projectName: string,
    limit?: number,
    offset?: number
  ): Promise<{
    project: string;
    notes: Array<{
      note_id: number;
      title: string;
      permalink: string | null;
      note_type: string;
      updated_at: string | null;
    }>;
    total_count: number;
    limit: number;
    offset: number;
  }> {
    const queryParams = new URLSearchParams();
    if (limit) queryParams.append('limit', limit.toString());
    if (offset) queryParams.append('offset', offset.toString());

    const url = `${this.baseUrl}/api/projects/${encodeURIComponent(projectName)}/notes${queryParams.toString() ? `?${queryParams}` : ''}`;
    const response = await fetch(url, {
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Project "${projectName}" not found`);
      }
      throw new Error(`Failed to list project notes: ${response.statusText}`);
    }
    return response.json() as Promise<{
      project: string;
      notes: Array<{
        note_id: number;
        title: string;
        permalink: string | null;
        note_type: string;
        updated_at: string | null;
      }>;
      total_count: number;
      limit: number;
      offset: number;
    }>;
  }

  /**
   * Create a new project.
   */
  async createProject(projectName: string): Promise<{
    project: string;
    status: string;
    message: string;
  }> {
    const response = await fetch(`${this.baseUrl}/api/projects`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ project_name: projectName }),
    });
    if (!response.ok) {
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to create project: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<{
      project: string;
      status: string;
      message: string;
    }>;
  }

  /**
   * Create a new session.
   */
  async createSession(project?: string | null): Promise<{
    session_id: string;
    project: string | null;
    started_at: string;
    status: string;
  }> {
    const response = await fetch(`${this.baseUrl}/api/sessions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ project }),
    });
    if (!response.ok) {
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to create session: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<{
      session_id: string;
      project: string | null;
      started_at: string;
      status: string;
    }>;
  }

  /**
   * Observe/add an event to a session.
   */
  async observeSessionEvent(
    sessionId: string,
    eventType: string,
    content: string,
    metadata?: Record<string, unknown>,
    customId?: string
  ): Promise<{
    session_id: string;
    event_count: number;
    status: string;
  }> {
    const body: Record<string, unknown> = {
      session_id: sessionId,
      event_type: eventType,
      content,
      metadata,
    };
    if (customId !== undefined) {
      body.custom_id = customId;
    }
    const response = await fetch(`${this.baseUrl}/api/sessions/observe`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to observe event: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<{
      session_id: string;
      event_count: number;
      status: string;
    }>;
  }

  /**
   * Summarize a session.
   */
  async summarizeSession(sessionId: string): Promise<{
    key_learnings: string[];
    decisions: string[];
    errors_encountered: string[];
    solutions_found: string[];
    next_steps: string[];
    summary_text: string;
    compression_ratio: number;
  }> {
    const response = await fetch(`${this.baseUrl}/api/sessions/${sessionId}/summary`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to summarize session: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<{
      key_learnings: string[];
      decisions: string[];
      errors_encountered: string[];
      solutions_found: string[];
      next_steps: string[];
      summary_text: string;
      compression_ratio: number;
    }>;
  }

  /**
   * Get session context.
   */
  async getSessionContext(
    sessionId: string,
    includeEvents: boolean = true,
    includeSummary: boolean = true,
    limit: number = 50
  ): Promise<{
    session_id: string;
    project: string | null;
    started_at: string;
    ended_at: string | null;
    status: string;
    event_count: number;
    events?: Array<{
      event_type: string;
      content: string;
      timestamp: string;
      metadata: Record<string, unknown>;
    }>;
    summary?: {
      key_learnings: string[];
      decisions: string[];
      errors_encountered: string[];
      solutions_found: string[];
      next_steps: string[];
      summary_text: string;
      compression_ratio: number;
    };
  }> {
    const response = await fetch(`${this.baseUrl}/api/sessions/context`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        session_id: sessionId,
        include_events: includeEvents,
        include_summary: includeSummary,
        limit,
      }),
    });
    if (!response.ok) {
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to get session context: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<{
      session_id: string;
      project: string | null;
      started_at: string;
      ended_at: string | null;
      status: string;
      event_count: number;
      events?: Array<{
        event_type: string;
        content: string;
        timestamp: string;
        metadata: Record<string, unknown>;
      }>;
      summary?: {
        key_learnings: string[];
        decisions: string[];
        errors_encountered: string[];
        solutions_found: string[];
        next_steps: string[];
        summary_text: string;
        compression_ratio: number;
      };
    }>;
  }

  /**
   * Traverse the knowledge graph using BFS or DFS.
   */
  async traverseGraph(params: {
    start_node_id: number;
    target_node_id?: number;
    method?: 'bfs' | 'dfs';
    max_depth?: number;
    direction?: 'outgoing' | 'incoming' | 'both';
    edge_types?: string[];
    exclude_nodes?: number[];
  }): Promise<{
    start_node_id: number;
    target_node_id: number | null;
    method: string;
    visited_nodes: number[];
    paths: number[][];
    depth_reached: number;
  }> {
    const response = await fetch(`${this.baseUrl}/api/graph/traverse`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        start_node_id: params.start_node_id,
        target_node_id: params.target_node_id || null,
        method: params.method || 'bfs',
        max_depth: params.max_depth || 10,
        direction: params.direction || 'outgoing',
        edge_types: params.edge_types || null,
        exclude_nodes: params.exclude_nodes || [],
      }),
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Start node ${params.start_node_id} not found`);
      }
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to traverse graph: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<{
      start_node_id: number;
      target_node_id: number | null;
      method: string;
      visited_nodes: number[];
      paths: number[][];
      depth_reached: number;
    }>;
  }

  /**
   * Find notes similar to a given note.
   */
  async findSimilarNotes(
    nodeId: number,
    limit?: number,
    method?: 'graph' | 'content' | 'hybrid'
  ): Promise<{
    source_node_id: number;
    method: string;
    similar_notes: Array<{
      note_id: number;
      title: string;
      vault_name: string;
      relative_path: string;
      note_type: string;
      score: number;
    }>;
    count: number;
  }> {
    const queryParams = new URLSearchParams();
    if (limit) queryParams.append('limit', limit.toString());
    if (method) queryParams.append('method', method);

    const url = `${this.baseUrl}/api/graph/nodes/${nodeId}/similar${queryParams.toString() ? `?${queryParams}` : ''}`;
    const response = await fetch(url, {
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Node ${nodeId} not found`);
      }
      throw new Error(`Failed to find similar notes: ${response.statusText}`);
    }
    return response.json() as Promise<{
      source_node_id: number;
      method: string;
      similar_notes: Array<{
        note_id: number;
        title: string;
        vault_name: string;
        relative_path: string;
        note_type: string;
        score: number;
      }>;
      count: number;
    }>;
  }

  /**
   * Get neighbors of a node in the graph.
   */
  async getGraphNeighbors(
    nodeId: number,
    direction?: 'outgoing' | 'incoming' | 'both'
  ): Promise<{
    node_id: number;
    neighbors: number[];
    direction: string;
  }> {
    const queryParams = new URLSearchParams();
    if (direction) queryParams.append('direction', direction);

    const url = `${this.baseUrl}/api/graph/nodes/${nodeId}/neighbors${queryParams.toString() ? `?${queryParams}` : ''}`;
    const response = await fetch(url, {
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Node ${nodeId} not found`);
      }
      throw new Error(`Failed to get neighbors: ${response.statusText}`);
    }
    return response.json() as Promise<{
      node_id: number;
      neighbors: number[];
      direction: string;
    }>;
  }

  /**
   * Delete a note by ID.
   */
  async deleteNote(id: number): Promise<{ id: number; message: string }> {
    const response = await fetch(`${this.baseUrl}/api/notes/${id}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Note with ID ${id} not found`);
      }
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to delete note: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<{ id: number; message: string }>;
  }

  /**
   * Supersede a note with another note.
   * Creates a bi-directional supersedes relationship.
   */
  async supersedeNote(
    oldNoteId: number,
    newNoteId: number,
    reason?: string
  ): Promise<{
    old_note_id: number;
    new_note_id: number;
    old_note_title: string;
    new_note_title: string;
    message: string;
  }> {
    const response = await fetch(`${this.baseUrl}/api/notes/supersede`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        old_note_id: oldNoteId,
        new_note_id: newNoteId,
        reason: reason || null,
      }),
    });
    if (!response.ok) {
      if (response.status === 404) {
        const error = (await response.json().catch(() => ({ detail: 'Note not found' }))) as { detail?: string };
        throw new Error(error.detail || 'Note not found');
      }
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to supersede note: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<{
      old_note_id: number;
      new_note_id: number;
      old_note_title: string;
      new_note_title: string;
      message: string;
    }>;
  }
  /**
   * Get profile for a project.
   */
  async getProfile(project: string): Promise<ProfileResponse> {
    const response = await fetch(`${this.baseUrl}/api/profile/${encodeURIComponent(project)}`, {
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new ProfileNotFoundError(project);
      }
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to get profile: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<ProfileResponse>;
  }

  /**
   * Trigger profile synthesis for a project.
   */
  async synthesizeProfile(project: string): Promise<{ status: string; message: string; project: string }> {
    const response = await fetch(`${this.baseUrl}/api/profile/${encodeURIComponent(project)}/synthesize`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to trigger synthesis: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<{ status: string; message: string; project: string }>;
  }

  /**
   * Get recall configuration.
   */
  async getRecallConfig(): Promise<RecallConfig> {
    const response = await fetch(`${this.baseUrl}/api/recall/config`, {
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      throw new Error(`Failed to get recall config: ${response.statusText}`);
    }
    return response.json() as Promise<RecallConfig>;
  }

  /**
   * Perform lightweight recall search.
   */
  async recallSearch(params: {
    query: string;
    project?: string | null;
    limit?: number;
    threshold?: number;
  }): Promise<RecallResponse> {
    const response = await fetch(`${this.baseUrl}/api/recall/search`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        query: params.query,
        project: params.project || null,
        limit: params.limit,
        threshold: params.threshold,
      }),
    });
    if (!response.ok) {
      const error = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
      throw new Error(`Failed to recall search: ${error.detail || response.statusText}`);
    }
    return response.json() as Promise<RecallResponse>;
  }
}

export interface ProfileResponse {
  project: string;
  static_facts: string[];
  dynamic_patterns: string[];
  key_entities: Record<string, string[]>;
  profile_version: number;
  last_synthesized: string | null;
  synthesis_note_count: number;
}

export class ProfileNotFoundError extends Error {
  constructor(project: string) {
    super(`No profile synthesized yet for project: ${project}`);
    this.name = 'ProfileNotFoundError';
  }
}

export interface RecallConfig {
  enabled: boolean;
  max_results: number;
  min_relevance: number;
  include_profile: boolean;
  max_snippet_length: number;
}

export interface RecallMemory {
  id: number;
  title: string;
  snippet: string;
  note_type: string;
  project: string | null;
  score: number;
  tags: string[];
}

export interface RecallResponse {
  memories: RecallMemory[];
  query: string;
  total_found: number;
  latency_ms: number;
}

/**
 * Singleton API client instance.
 * Use this shared instance across all tools to avoid creating multiple connections.
 */
export const apiClient = new ApiClient(API_BASE_URL);
