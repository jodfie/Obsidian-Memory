/**
 * API client for Obsidian-Memory backend.
 */

/**
 * Get API base URL: localStorage (Settings) overrides env.
 */
function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('api_url');
    if (stored?.trim()) return stored.trim();
  }
  return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
}

export interface Note {
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
  notes: Note[];
  total: number;
  limit: number;
  offset: number;
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

export interface Project {
  name: string;
  note_count: number;
}

export interface ProjectListResponse {
  projects: Project[];
}

export interface Session {
  session_id: string;
  project: string | null;
  started_at: string;
  ended_at: string | null;
  status: string;
  event_count: number;
}

export interface SessionListResponse {
  sessions: Session[];
}

export interface GraphNode {
  id: number;
  title: string;
  permalink: string | null;
  vault_name: string;
  note_type: string;
  project: string | null;
  tags: string[];
}

export interface GraphEdge {
  source: number;
  target: number;
  target_title: string;
  type: string;
  context: string | null;
  weight: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/**
 * Get API token from localStorage or environment.
 */
function getApiToken(): string | null {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('api_token') || null;
  }
  return null;
}

/**
 * Fetch wrapper with error handling and authentication.
 */
async function fetchAPI<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const base = getApiBaseUrl();
  const url = `${base}${endpoint}`;
  const token = getApiToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: response.statusText,
    }));
    throw new Error(error.detail || `API error: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get a note by ID.
 */
export async function getNoteById(id: number): Promise<Note> {
  return fetchAPI<Note>(`/api/notes/${id}`);
}

/**
 * List notes with optional filtering.
 */
export async function listNotes(params: {
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

  const query = queryParams.toString();
  return fetchAPI<NoteListResponse>(`/api/notes${query ? `?${query}` : ''}`);
}

/**
 * Search notes.
 */
export async function searchNotes(
  request: SearchRequest
): Promise<NoteListResponse> {
  return fetchAPI<NoteListResponse>('/api/notes/search', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Create a new note.
 */
export async function createNote(request: {
  title: string;
  content: string;
  relative_path: string;
  vault_name?: string | null;
  note_type?: string;
  project?: string | null;
  tags?: string[];
}): Promise<Note> {
  return fetchAPI<Note>('/api/notes', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Update an existing note.
 */
export async function updateNote(
  id: number,
  request: {
    title?: string | null;
    content?: string | null;
    note_type?: string | null;
    project?: string | null;
    tags?: string[] | null;
  }
): Promise<Note> {
  return fetchAPI<Note>(`/api/notes/${id}`, {
    method: 'PUT',
    body: JSON.stringify(request),
  });
}

/**
 * List all projects.
 */
export async function listProjects(): Promise<ProjectListResponse> {
  return fetchAPI<ProjectListResponse>('/api/projects');
}

/**
 * List sessions.
 */
export async function listSessions(params?: {
  project?: string | null;
  limit?: number;
}): Promise<SessionListResponse> {
  const queryParams = new URLSearchParams();
  if (params?.project) queryParams.append('project', params.project);
  if (params?.limit) queryParams.append('limit', params.limit.toString());

  const query = queryParams.toString();
  return fetchAPI<SessionListResponse>(
    `/api/sessions${query ? `?${query}` : ''}`
  );
}

/**
 * Get the knowledge graph.
 */
export async function getGraph(): Promise<GraphResponse> {
  return fetchAPI<GraphResponse>('/api/graph');
}

/**
 * List notes for a project.
 */
export interface ProjectNote {
  note_id: number;
  title: string;
  permalink: string | null;
  note_type: string;
  updated_at: string | null;
}

export interface ProjectNotesResponse {
  notes: ProjectNote[];
  total: number;
  limit: number;
  offset: number;
}

export async function getProjectNotes(
  projectName: string,
  params?: { limit?: number; offset?: number }
): Promise<ProjectNotesResponse> {
  const queryParams = new URLSearchParams();
  if (params?.limit != null)
    queryParams.append('limit', params.limit.toString());
  if (params?.offset != null)
    queryParams.append('offset', params.offset.toString());
  const query = queryParams.toString();
  return fetchAPI<ProjectNotesResponse>(
    `/api/projects/${encodeURIComponent(projectName)}/notes${query ? `?${query}` : ''}`
  );
}

/**
 * Get session context (events, summary).
 */
export interface SessionContextRequest {
  session_id: string;
  include_events?: boolean;
  include_summary?: boolean;
  limit?: number;
}

export interface SessionContext {
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
}

export async function getSessionContext(
  request: SessionContextRequest
): Promise<SessionContext> {
  return fetchAPI<SessionContext>('/api/sessions/context', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Get health status.
 */
export async function getHealth(): Promise<{ status: string }> {
  return fetchAPI<{ status: string }>('/health');
}
