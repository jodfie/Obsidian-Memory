/**HTTP client for backend API calls.*/

import { getConfig } from '../config.js';

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
  parsed: unknown;
}

export interface SearchResult {
  note_id: number;
  vault_name: string;
  relative_path: string;
  permalink: string | null;
  title: string;
  note_type: string;
  project: string | null;
  snippet: string;
  score: number;
  created_at: string | null;
  updated_at: string | null;
  tags: string[];
}

export interface SearchResponse {
  results: SearchResult[];
  total_count: number;
  query: string | null;
  took_ms: number;
}

export interface CreateNoteRequest {
  vault_name: string;
  relative_path: string;
  title: string;
  content: string;
  note_type?: string;
  project?: string | null;
  tags?: string[];
}

export interface UpdateNoteRequest {
  title?: string;
  content?: string;
  note_type?: string;
  project?: string | null;
  tags?: string[] | null;
}

/**
 * HTTP client for backend API.
 */
export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || getConfig().backendUrl;
  }

  /**
   * Make HTTP request to backend API.
   */
  private async request<T>(
    method: string,
    path: string,
    body?: unknown
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const options: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `API request failed: ${response.status} ${response.statusText} - ${errorText}`
      );
    }

    return response.json() as Promise<T>;
  }

  /**
   * Get note by ID.
   */
  async getNoteById(noteId: number): Promise<NoteResponse> {
    return this.request<NoteResponse>('GET', `/api/notes/${noteId}`);
  }

  /**
   * Search notes.
   */
  async searchNotes(params: {
    q?: string;
    vault?: string;
    project?: string;
    note_type?: string;
    tags?: string;
    tags_any?: string;
    limit?: number;
    offset?: number;
  }): Promise<SearchResponse> {
    const queryParams = new URLSearchParams();
    if (params.q) queryParams.append('q', params.q);
    if (params.vault) queryParams.append('vault', params.vault);
    if (params.project) queryParams.append('project', params.project);
    if (params.note_type) queryParams.append('note_type', params.note_type);
    if (params.tags) queryParams.append('tags', params.tags);
    if (params.tags_any) queryParams.append('tags_any', params.tags_any);
    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.offset) queryParams.append('offset', params.offset.toString());

    const query = queryParams.toString();
    return this.request<SearchResponse>(
      'GET',
      `/api/notes${query ? `?${query}` : ''}`
    );
  }

  /**
   * Create a new note.
   */
  async createNote(request: CreateNoteRequest): Promise<NoteResponse> {
    return this.request<NoteResponse>('POST', '/api/notes', request);
  }

  /**
   * Update an existing note.
   */
  async updateNote(
    noteId: number,
    request: UpdateNoteRequest
  ): Promise<NoteResponse> {
    return this.request<NoteResponse>('PUT', `/api/notes/${noteId}`, request);
  }

  /**
   * Delete a note.
   */
  async deleteNote(noteId: number): Promise<void> {
    await this.request('DELETE', `/api/notes/${noteId}`);
  }
}
