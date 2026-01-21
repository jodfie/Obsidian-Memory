/**
 * HTTP client for communicating with the Obsidian-Memory backend API.
 */

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
    metadata?: Record<string, unknown>
  ): Promise<{
    session_id: string;
    event_count: number;
    status: string;
  }> {
    const response = await fetch(`${this.baseUrl}/api/sessions/observe`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        event_type: eventType,
        content,
        metadata,
      }),
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
}
