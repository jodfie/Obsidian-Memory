/**
 * Session management tools for Obsidian-Memory MCP server.
 */

import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { ApiClient } from '../client.js';

const API_BASE_URL = process.env.OBSIDIAN_MEMORY_API_URL || 'http://localhost:8000';
const client = new ApiClient(API_BASE_URL);

/**
 * Tool definitions for session operations.
 */
export const sessionTools: Tool[] = [
  {
    name: 'session_observe',
    description:
      'Add an observation or event to a session. Use this to track decisions, errors, solutions, tool usage, file edits, etc.',
    inputSchema: {
      type: 'object',
      properties: {
        session_id: {
          type: 'string',
          description: 'Session ID (create one first if needed)',
        },
        event_type: {
          type: 'string',
          enum: [
            'observation',
            'decision',
            'error',
            'solution',
            'tool_use',
            'file_edit',
            'command',
            'research',
            'user_prompt',
          ],
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
      },
      required: ['session_id', 'event_type', 'content'],
    },
  },
  {
    name: 'session_summary',
    description:
      'Generate an AI summary of a session. Extracts key learnings, decisions, errors, solutions, and next steps.',
    inputSchema: {
      type: 'object',
      properties: {
        session_id: {
          type: 'string',
          description: 'Session ID to summarize',
        },
      },
      required: ['session_id'],
    },
  },
  {
    name: 'session_context',
    description:
      'Get context for a session including events and summary. Useful for loading session context into Claude.',
    inputSchema: {
      type: 'object',
      properties: {
        session_id: {
          type: 'string',
          description: 'Session ID',
        },
        include_events: {
          type: 'boolean',
          description: 'Include session events (default: true)',
        },
        include_summary: {
          type: 'boolean',
          description: 'Include AI summary if available (default: true)',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of events to return (default: 50)',
        },
      },
      required: ['session_id'],
    },
  },
];

/**
 * Handle session_observe tool call.
 */
export async function handleSessionObserve(args: {
  session_id: string;
  event_type: string;
  content: string;
  metadata?: Record<string, unknown>;
}): Promise<{
  session_id: string;
  event_count: number;
  status: string;
}> {
  return await client.observeSessionEvent(
    args.session_id,
    args.event_type,
    args.content,
    args.metadata
  );
}

/**
 * Handle session_summary tool call.
 */
export async function handleSessionSummary(args: {
  session_id: string;
}): Promise<{
  key_learnings: string[];
  decisions: string[];
  errors_encountered: string[];
  solutions_found: string[];
  next_steps: string[];
  summary_text: string;
  compression_ratio: number;
}> {
  return await client.summarizeSession(args.session_id);
}

/**
 * Handle session_context tool call.
 */
export async function handleSessionContext(args: {
  session_id: string;
  include_events?: boolean;
  include_summary?: boolean;
  limit?: number;
}): Promise<{
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
  return await client.getSessionContext(
    args.session_id,
    args.include_events ?? true,
    args.include_summary ?? true,
    args.limit ?? 50
  );
}
