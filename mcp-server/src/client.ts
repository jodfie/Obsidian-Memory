/**
 * HTTP client for communicating with the Obsidian-Memory backend API.
 */

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

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl.replace(/\/$/, ''); // Remove trailing slash
  }

  /**
   * Get a note by ID.
   */
  async getNoteById(id: number): Promise<NoteResponse> {
    const response = await fetch(`${this.baseUrl}/api/notes/${id}`);
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Note with ID ${id} not found`);
      }
      throw new Error(`Failed to get note: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Create a new note.
   */
  async createNote(request: NoteCreateRequest): Promise<NoteResponse> {
    const response = await fetch(`${this.baseUrl}/api/notes`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(`Failed to create note: ${error.detail || response.statusText}`);
    }
    return response.json();
  }

  /**
   * Update an existing note.
   */
  async updateNote(id: number, request: NoteUpdateRequest): Promise<NoteResponse> {
    const response = await fetch(`${this.baseUrl}/api/notes/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Note with ID ${id} not found`);
      }
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(`Failed to update note: ${error.detail || response.statusText}`);
    }
    return response.json();
  }

  /**
   * Search notes.
   */
  async searchNotes(request: SearchRequest): Promise<NoteListResponse> {
    const response = await fetch(`${this.baseUrl}/api/notes/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(`Failed to search notes: ${error.detail || response.statusText}`);
    }
    return response.json();
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
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to list notes: ${response.statusText}`);
    }
    return response.json();
  }
}
