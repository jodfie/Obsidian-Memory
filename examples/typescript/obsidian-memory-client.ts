/**
 * Obsidian-Memory TypeScript SDK Example
 *
 * A simple client library for interacting with the Obsidian-Memory API.
 *
 * Usage:
 *   import { ObsidianMemoryClient } from './obsidian-memory-client';
 *
 *   const client = new ObsidianMemoryClient({
 *     baseUrl: 'http://localhost:8000',
 *     authToken: 'your-token',  // Optional if auth is disabled
 *   });
 *
 *   // List notes
 *   const { notes, total } = await client.listNotes({ limit: 10 });
 *
 *   // Search notes
 *   const results = await client.search('machine learning', { project: 'research' });
 *
 *   // Create a note
 *   const note = await client.createNote({
 *     vaultName: 'my-vault',
 *     title: 'New Note',
 *     content: '# My Note\n\nContent here...',
 *   });
 */

// Types

export interface Note {
  id: number;
  vault_name: string;
  relative_path: string;
  permalink: string;
  title: string;
  note_type: string;
  content: string;
  tags: string[];
  project: string | null;
  created_at: string;
  updated_at: string;
  supersedes?: number | null;
  superseded_by?: number | null;
}

export interface Project {
  name: string;
  note_count: number;
}

export interface GraphNode {
  id: number;
  title: string;
  permalink: string;
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

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface HealthStatus {
  status: string;
  version?: string;
  vault_connected?: boolean;
  timestamp?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface SupersedeResult {
  old_note_id: number;
  new_note_id: number;
  old_note_title: string;
  new_note_title: string;
  message: string;
}

// Errors

export class ObsidianMemoryError extends Error {
  constructor(
    message: string,
    public statusCode?: number
  ) {
    super(message);
    this.name = 'ObsidianMemoryError';
  }
}

export class NotFoundError extends ObsidianMemoryError {
  constructor(message: string = 'Resource not found') {
    super(message, 404);
    this.name = 'NotFoundError';
  }
}

export class AuthenticationError extends ObsidianMemoryError {
  constructor(message: string = 'Authentication failed') {
    super(message, 401);
    this.name = 'AuthenticationError';
  }
}

export class RateLimitError extends ObsidianMemoryError {
  constructor(
    message: string = 'Rate limit exceeded',
    public retryAfter: number = 60
  ) {
    super(message, 429);
    this.name = 'RateLimitError';
  }
}

// Client Options

export interface ClientOptions {
  baseUrl?: string;
  authToken?: string;
  timeout?: number;
}

// Request Options

export interface ListNotesOptions {
  vault?: string;
  project?: string;
  limit?: number;
  offset?: number;
}

export interface SearchOptions {
  vault?: string;
  project?: string;
  noteType?: string;
  tags?: string[];
  limit?: number;
  offset?: number;
}

export interface CreateNoteOptions {
  vaultName: string;
  title: string;
  content: string;
  relativePath?: string;
  noteType?: string;
  project?: string;
  tags?: string[];
}

export interface UpdateNoteOptions {
  title?: string;
  content?: string;
  tags?: string[];
  project?: string;
}

// Client Implementation

export class ObsidianMemoryClient {
  private baseUrl: string;
  private authToken?: string;
  private timeout: number;

  constructor(options: ClientOptions = {}) {
    this.baseUrl = (options.baseUrl || 'http://localhost:8000').replace(
      /\/$/,
      ''
    );
    this.authToken = options.authToken;
    this.timeout = options.timeout || 30000;
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this.authToken) {
      headers['Authorization'] = `Bearer ${this.authToken}`;
    }
    return headers;
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (response.status === 401) {
      throw new AuthenticationError('Authentication required');
    }
    if (response.status === 403) {
      throw new AuthenticationError('Invalid credentials');
    }
    if (response.status === 404) {
      throw new NotFoundError();
    }
    if (response.status === 429) {
      const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
      throw new RateLimitError('Rate limit exceeded', retryAfter);
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new ObsidianMemoryError(
        error.detail || `HTTP ${response.status}`,
        response.status
      );
    }

    return response.json();
  }

  private async get<T>(
    path: string,
    params?: Record<string, string | number>
  ): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: this.getHeaders(),
      signal: AbortSignal.timeout(this.timeout),
    });

    return this.handleResponse<T>(response);
  }

  private async post<T>(path: string, data?: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: data ? JSON.stringify(data) : undefined,
      signal: AbortSignal.timeout(this.timeout),
    });

    return this.handleResponse<T>(response);
  }

  private async put<T>(path: string, data?: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'PUT',
      headers: this.getHeaders(),
      body: data ? JSON.stringify(data) : undefined,
      signal: AbortSignal.timeout(this.timeout),
    });

    return this.handleResponse<T>(response);
  }

  private async delete<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
      signal: AbortSignal.timeout(this.timeout),
    });

    return this.handleResponse<T>(response);
  }

  // Health & Metrics

  async health(): Promise<HealthStatus> {
    return this.get<HealthStatus>('/health');
  }

  async metrics(): Promise<Record<string, unknown>> {
    return this.get('/metrics');
  }

  // Notes

  async listNotes(
    options: ListNotesOptions = {}
  ): Promise<{ notes: Note[]; total: number }> {
    const params: Record<string, string | number> = {
      limit: options.limit || 50,
      offset: options.offset || 0,
    };
    if (options.vault) params.vault = options.vault;
    if (options.project) params.project = options.project;

    const data = await this.get<{ notes: Note[]; total: number }>(
      '/api/notes',
      params
    );
    return data;
  }

  async getNote(noteId: number): Promise<Note> {
    return this.get<Note>(`/api/notes/${noteId}`);
  }

  async createNote(options: CreateNoteOptions): Promise<Note> {
    const relativePath =
      options.relativePath ||
      `notes/${options.title.toLowerCase().replace(/\s+/g, '-')}.md`;

    return this.post<Note>('/api/notes', {
      vault_name: options.vaultName,
      relative_path: relativePath,
      title: options.title,
      content: options.content,
      note_type: options.noteType || 'note',
      project: options.project,
      tags: options.tags || [],
    });
  }

  async updateNote(noteId: number, options: UpdateNoteOptions): Promise<Note> {
    const updates: Record<string, unknown> = {};
    if (options.title !== undefined) updates.title = options.title;
    if (options.content !== undefined) updates.content = options.content;
    if (options.tags !== undefined) updates.tags = options.tags;
    if (options.project !== undefined) updates.project = options.project;

    return this.put<Note>(`/api/notes/${noteId}`, updates);
  }

  async deleteNote(noteId: number): Promise<void> {
    await this.delete(`/api/notes/${noteId}`);
  }

  async search(
    query: string,
    options: SearchOptions = {}
  ): Promise<{ notes: Note[]; total: number }> {
    const searchParams: Record<string, unknown> = {
      query,
      limit: options.limit || 50,
      offset: options.offset || 0,
    };
    if (options.vault) searchParams.vault = options.vault;
    if (options.project) searchParams.project = options.project;
    if (options.noteType) searchParams.note_type = options.noteType;
    if (options.tags) searchParams.tags = options.tags;

    return this.post<{ notes: Note[]; total: number }>(
      '/api/notes/search',
      searchParams
    );
  }

  async supersedeNote(
    oldNoteId: number,
    newNoteId: number,
    reason?: string
  ): Promise<SupersedeResult> {
    return this.post<SupersedeResult>('/api/notes/supersede', {
      old_note_id: oldNoteId,
      new_note_id: newNoteId,
      reason,
    });
  }

  // Projects

  async listProjects(): Promise<Project[]> {
    const data = await this.get<{ projects: Project[] }>('/api/projects');
    return data.projects;
  }

  async getProjectNotes(
    projectName: string,
    options: { limit?: number; offset?: number } = {}
  ): Promise<{ notes: Array<Record<string, unknown>>; total: number }> {
    const data = await this.get<{
      notes: Array<Record<string, unknown>>;
      total_count: number;
    }>(`/api/projects/${encodeURIComponent(projectName)}/notes`, {
      limit: options.limit || 50,
      offset: options.offset || 0,
    });
    return { notes: data.notes, total: data.total_count };
  }

  // Graph

  async getGraph(): Promise<Graph> {
    return this.get<Graph>('/api/graph');
  }

  async getNeighbors(
    nodeId: number
  ): Promise<{ incoming: GraphEdge[]; outgoing: GraphEdge[] }> {
    return this.get(`/api/graph/nodes/${nodeId}/neighbors`);
  }
}

// Example usage
async function main() {
  const client = new ObsidianMemoryClient({
    baseUrl: 'http://localhost:8000',
    // authToken: 'your-token-here',  // Uncomment if auth is enabled
  });

  try {
    // Check health
    const health = await client.health();
    console.log(`API Status: ${health.status}`);

    // List notes
    const { notes, total } = await client.listNotes({ limit: 5 });
    console.log(`\nFound ${total} notes:`);
    notes.forEach((note) => {
      console.log(`  - ${note.title} (${note.vault_name})`);
    });

    // Search example
    const searchResults = await client.search('python', { limit: 3 });
    console.log(
      `\nSearch results for 'python' (${searchResults.total} total):`
    );
    searchResults.notes.forEach((note) => {
      console.log(`  - ${note.title}`);
    });

    // Create a note example (commented out to avoid side effects)
    // const newNote = await client.createNote({
    //   vaultName: 'my-vault',
    //   title: 'API Test Note',
    //   content: '# Test Note\n\nCreated via TypeScript SDK.',
    //   tags: ['test', 'api'],
    // });
    // console.log(`\nCreated note: ${newNote.id} - ${newNote.title}`);

    // Get graph stats
    const graph = await client.getGraph();
    console.log(
      `\nKnowledge graph: ${graph.nodes.length} nodes, ${graph.edges.length} edges`
    );
  } catch (error) {
    if (error instanceof RateLimitError) {
      console.error(`Rate limited. Retry after ${error.retryAfter} seconds.`);
    } else if (error instanceof AuthenticationError) {
      console.error('Authentication failed:', error.message);
    } else if (error instanceof NotFoundError) {
      console.error('Resource not found');
    } else {
      console.error('Error:', error);
    }
  }
}

// Run example if executed directly
main().catch(console.error);
