/**
 * Tool definitions for Obsidian-Memory MCP server.
 *
 * These definitions are used by the SSE transport for tools/list responses.
 * The stdio transport uses Zod schemas directly via McpServer.registerTool().
 */

import type { Tool } from '@modelcontextprotocol/sdk/types.js';

/**
 * All tool definitions in JSON Schema format.
 * Used by SSE transport for tools/list response.
 */
export const tools: Tool[] = [
  // Memory Tools
  {
    name: 'mem_read',
    description:
      'Read a note from Obsidian-Memory by ID, permalink, or search query. Returns the full note content with metadata. Use this to retrieve specific notes when you know their identifier or want to find notes by searching.',
    annotations: {
      title: 'Read Memory Note',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'number',
          description: 'Note ID (if known)',
        },
        permalink: {
          type: 'string',
          description: 'Note permalink (if known)',
        },
        query: {
          type: 'string',
          description: 'Search query to find note (returns first match)',
        },
        vault: {
          type: 'string',
          description: 'Optional vault name to filter search',
        },
        response_format: {
          type: 'string',
          enum: ['json', 'markdown'],
          default: 'json',
          description: 'Response format: "json" for structured data, "markdown" for human-readable text',
        },
      },
    },
  },
  {
    name: 'mem_write',
    description:
      'Create or update a note in Obsidian-Memory. If note_id is provided, updates the existing note; otherwise creates a new note. Use this to save important information, decisions, patterns, or knowledge for future reference.',
    annotations: {
      title: 'Write Memory Note',
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: false,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        note_id: {
          type: 'number',
          description: 'Note ID for update (omit for create)',
        },
        vault_name: {
          type: 'string',
          description: 'Vault name (optional, uses default if not provided)',
        },
        relative_path: {
          type: 'string',
          description: 'Relative path for the note (e.g., "projects/api/auth.md")',
        },
        title: {
          type: 'string',
          description: 'Note title',
        },
        content: {
          type: 'string',
          description: 'Markdown content of the note',
        },
        note_type: {
          type: 'string',
          enum: ['note', 'decision', 'error', 'knowledge', 'pattern', 'session', 'research'],
          default: 'note',
          description: 'Type of note',
        },
        project: {
          type: 'string',
          description: 'Project identifier (optional)',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Tags for the note',
        },
      },
      required: ['relative_path', 'title', 'content'],
    },
  },
  {
    name: 'mem_search',
    description:
      'Search notes in Obsidian-Memory using full-text search with optional filters. Supports FTS5 syntax (terms, phrases, boolean operators). Returns matching notes with snippets and pagination metadata.',
    annotations: {
      title: 'Search Memory Notes',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query (FTS5 syntax: terms, phrases, boolean operators)',
        },
        vault: {
          type: 'string',
          description: 'Filter by vault name',
        },
        project: {
          type: 'string',
          description: 'Filter by project',
        },
        note_type: {
          type: 'string',
          enum: ['note', 'decision', 'error', 'knowledge', 'pattern', 'session', 'research'],
          description: 'Filter by note type',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Filter by tags (AND - all must match)',
        },
        tags_any: {
          type: 'array',
          items: { type: 'string' },
          description: 'Filter by tags (OR - any can match)',
        },
        sort: {
          type: 'string',
          enum: ['relevance', 'created_desc', 'created_asc', 'updated_desc', 'updated_asc', 'title_asc'],
          default: 'relevance',
          description: 'Sort order',
        },
        limit: {
          type: 'number',
          description: 'Maximum results (1-1000, default: 50)',
        },
        offset: {
          type: 'number',
          description: 'Result offset for pagination',
        },
        include_expired: {
          type: 'boolean',
          default: false,
          description: 'Include expired and low-confidence notes in results',
        },
        response_format: {
          type: 'string',
          enum: ['json', 'markdown'],
          default: 'json',
          description: 'Response format: "json" for structured data, "markdown" for human-readable text',
        },
      },
      required: ['query'],
    },
  },
  {
    name: 'mem_delete',
    description:
      'Permanently delete a note from Obsidian-Memory by ID. This removes the note from the database and deletes the underlying markdown file from the vault. This action cannot be undone.',
    annotations: {
      title: 'Delete Memory Note',
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'number',
          description: 'Note ID to delete',
        },
      },
      required: ['id'],
    },
  },
  {
    name: 'mem_supersede',
    description:
      'Mark a note as superseded by another note. Creates a bi-directional relationship: the old note gets a superseded_by field pointing to the new note, and the new note gets a supersedes field pointing to the old note. Use this when you have updated information that replaces older knowledge.',
    annotations: {
      title: 'Supersede Memory Note',
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        old_note_id: {
          type: 'number',
          description: 'ID of the note being replaced (the outdated note)',
        },
        new_note_id: {
          type: 'number',
          description: 'ID of the note that replaces it (the current note)',
        },
        reason: {
          type: 'string',
          description: 'Optional reason for superseding (e.g., "Updated API documentation", "Corrected error in original")',
        },
        response_format: {
          type: 'string',
          enum: ['json', 'markdown'],
          default: 'json',
          description: 'Response format: "json" for structured data, "markdown" for human-readable text',
        },
      },
      required: ['old_note_id', 'new_note_id'],
    },
  },

  // Context Tool
  {
    name: 'build_context',
    description:
      'Build context from memory:// URI patterns. Supports note selection by ID, permalink, search, path, tags, project, and graph operations. Use this to gather related notes into a single context block.',
    annotations: {
      title: 'Build Context from Memory',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        uris: {
          type: 'array',
          items: { type: 'string' },
          description:
            'Array of memory:// URI patterns. Examples: "memory://note/123", "memory://search/auth", "memory://tags/security,backend", "memory://project/api"',
        },
        response_format: {
          type: 'string',
          enum: ['json', 'markdown'],
          default: 'json',
          description: 'Response format: "json" for structured data, "markdown" for human-readable text',
        },
      },
      required: ['uris'],
    },
  },

  // Graph Tools
  {
    name: 'graph_traverse',
    description:
      'Traverse the knowledge graph from a starting note using BFS or DFS. Returns visited nodes and optional paths. Note: Currently uses search-based approximation while graph API is being implemented.',
    annotations: {
      title: 'Traverse Knowledge Graph',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        start_node_id: {
          type: 'number',
          description: 'Starting node ID',
        },
        target_node_id: {
          type: 'number',
          description: 'Optional target node ID (stops when found)',
        },
        method: {
          type: 'string',
          enum: ['bfs', 'dfs'],
          default: 'bfs',
          description: 'Traversal method: bfs or dfs',
        },
        max_depth: {
          type: 'number',
          default: 10,
          description: 'Maximum traversal depth (1-100, default: 10)',
        },
        direction: {
          type: 'string',
          enum: ['outgoing', 'incoming', 'both'],
          default: 'both',
          description: 'Edge direction to traverse',
        },
        edge_types: {
          type: 'array',
          items: { type: 'string' },
          description: 'Filter by edge types (e.g., ["depends_on", "enables"])',
        },
        exclude_nodes: {
          type: 'array',
          items: { type: 'number' },
          description: 'Node IDs to exclude from traversal',
        },
        response_format: {
          type: 'string',
          enum: ['json', 'markdown'],
          default: 'json',
          description: 'Response format: "json" for structured data, "markdown" for human-readable text',
        },
      },
      required: ['start_node_id'],
    },
  },
  {
    name: 'graph_similar',
    description:
      'Find notes similar to a given note using graph structure and content similarity. Note: Currently uses search-based approximation while graph API is being implemented.',
    annotations: {
      title: 'Find Similar Notes',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        note_id: {
          type: 'number',
          description: 'Source note ID',
        },
        limit: {
          type: 'number',
          default: 10,
          description: 'Maximum similar notes to return (1-100, default: 10)',
        },
        method: {
          type: 'string',
          enum: ['graph', 'content', 'hybrid'],
          default: 'hybrid',
          description: 'Similarity method: graph, content, or hybrid',
        },
        response_format: {
          type: 'string',
          enum: ['json', 'markdown'],
          default: 'json',
          description: 'Response format: "json" for structured data, "markdown" for human-readable text',
        },
      },
      required: ['note_id'],
    },
  },

  // Project Tools
  {
    name: 'project_list',
    description:
      'List all projects with their note counts. Returns projects sorted by note count (descending). Use this to discover available projects in the knowledge base.',
    annotations: {
      title: 'List Projects',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        response_format: {
          type: 'string',
          enum: ['json', 'markdown'],
          default: 'json',
          description: 'Response format: "json" for structured data, "markdown" for human-readable text',
        },
      },
    },
  },
  {
    name: 'project_switch',
    description:
      'Switch to a project context. Returns project details and recent notes. This is informational - actual project filtering happens in other tools via the project parameter.',
    annotations: {
      title: 'Switch Project Context',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        project_name: {
          type: 'string',
          description: 'Name of the project to switch to',
        },
        limit: {
          type: 'number',
          default: 10,
          description: 'Number of recent notes to return (default: 10)',
        },
        response_format: {
          type: 'string',
          enum: ['json', 'markdown'],
          default: 'json',
          description: 'Response format: "json" for structured data, "markdown" for human-readable text',
        },
      },
      required: ['project_name'],
    },
  },
  {
    name: 'project_create',
    description:
      'Create a new project. Projects are created implicitly when notes are added with a project field, but this tool allows explicit creation with name validation.',
    annotations: {
      title: 'Create Project',
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        project_name: {
          type: 'string',
          pattern: '^[a-zA-Z0-9_-]+$',
          description: 'Name of the project to create (alphanumeric, dash, underscore only)',
        },
      },
      required: ['project_name'],
    },
  },

  // Session Tools
  {
    name: 'session_observe',
    description:
      'Add an observation or event to a session. Use this to track decisions, errors, solutions, tool usage, file edits, commands, and other significant events during a development session.',
    annotations: {
      title: 'Observe Session Event',
      readOnlyHint: false,
      destructiveHint: true,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        session_id: {
          type: 'string',
          description: 'Session ID (create one first if needed)',
        },
        event_type: {
          type: 'string',
          enum: ['observation', 'decision', 'error', 'solution', 'tool_use', 'file_edit', 'command', 'research', 'user_prompt'],
          description: 'Type of event',
        },
        content: {
          type: 'string',
          description: 'Event content/description',
        },
        metadata: {
          type: 'object',
          description: 'Optional metadata (e.g., file path, command, tool name)',
        },
        custom_id: {
          type: 'string',
          description: 'Optional unique identifier for deduplication. When provided, enables upsert semantics: updates existing event if custom_id matches, inserts new event otherwise.',
        },
      },
      required: ['session_id', 'event_type', 'content'],
    },
  },
  {
    name: 'session_summary',
    description:
      'Generate an AI summary of a session. Extracts key learnings, decisions made, errors encountered, solutions found, and next steps from the session events.',
    annotations: {
      title: 'Generate Session Summary',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        session_id: {
          type: 'string',
          description: 'Session ID to summarize',
        },
        response_format: {
          type: 'string',
          enum: ['json', 'markdown'],
          default: 'json',
          description: 'Response format: "json" for structured data, "markdown" for human-readable text',
        },
      },
      required: ['session_id'],
    },
  },
  {
    name: 'session_context',
    description:
      'Get context for a session including events and summary. Useful for loading session context into Claude to continue work or review what happened in a previous session.',
    annotations: {
      title: 'Get Session Context',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        session_id: {
          type: 'string',
          description: 'Session ID',
        },
        include_events: {
          type: 'boolean',
          default: true,
          description: 'Include session events (default: true)',
        },
        include_summary: {
          type: 'boolean',
          default: true,
          description: 'Include AI summary if available (default: true)',
        },
        limit: {
          type: 'number',
          default: 50,
          description: 'Maximum events to return (default: 50)',
        },
        response_format: {
          type: 'string',
          enum: ['json', 'markdown'],
          default: 'json',
          description: 'Response format: "json" for structured data, "markdown" for human-readable text',
        },
      },
      required: ['session_id'],
    },
  },

  // Profile Tools
  {
    name: 'get_profile',
    description:
      'Retrieve user/project profile with static facts, dynamic patterns, and key entities. Profiles are synthesized from project notes and provide context about user preferences, tech stack, and behavioral patterns.',
    annotations: {
      title: 'Get Project Profile',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        project: {
          type: 'string',
          description: 'Project identifier to get profile for',
        },
        response_format: {
          type: 'string',
          enum: ['json', 'markdown'],
          default: 'json',
          description: 'Response format: "json" for structured data, "markdown" for human-readable text',
        },
      },
      required: ['project'],
    },
  },

  // Recall Tools
  {
    name: 'recall',
    description:
      "DO NOT USE ANY OTHER RECALL TOOL ONLY USE THIS ONE. Search the user's memories. Returns relevant memories plus their profile summary.",
    annotations: {
      title: 'Recall Memories',
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'The search query to find relevant memories',
          maxLength: 1000,
        },
        containerTag: {
          type: 'string',
          description:
            'Optional project to scope memories. Available projects: sm_project_default, sm_project_stockdale_forensics, sm_project_twitter_x',
          maxLength: 128,
        },
        includeProfile: {
          type: 'boolean',
          default: true,
        },
      },
      required: ['query'],
    },
  },
];
