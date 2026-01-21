/**
 * Project management tools for Obsidian-Memory MCP server.
 */

import type { Tool } from '@modelcontextprotocol/sdk/types.js';
import { ApiClient } from '../client.js';

const env = process.env as Record<string, string | undefined>;
const API_BASE_URL = env['OBSIDIAN_MEMORY_API_URL'] || 'http://localhost:8000';
const client = new ApiClient(API_BASE_URL);

/**
 * Tool definitions for project operations.
 */
export const projectTools: Tool[] = [
  {
    name: 'project_list',
    description:
      'List all projects with their note counts. Returns projects sorted by note count (descending).',
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
    },
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'project_switch',
    description:
      'Switch to a project context. Returns project details and recent notes. This is informational - actual project filtering happens in other tools.',
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
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
          description: 'Number of recent notes to return (default: 10)',
        },
      },
      required: ['project_name'],
    },
  },
  {
    name: 'project_create',
    description:
      'Create a new project. Projects are created implicitly when notes are added, but this validates the project name.',
    annotations: {
      readOnlyHint: false,
      destructiveHint: true,
    },
    inputSchema: {
      type: 'object',
      properties: {
        project_name: {
          type: 'string',
          description: 'Name of the project to create (alphanumeric, dash, underscore only)',
        },
      },
      required: ['project_name'],
    },
  },
];

/**
 * Handle project_list tool call.
 */
export async function handleProjectList(): Promise<{
  projects: Array<{ name: string; note_count: number }>;
}> {
  const result = await client.listProjects();
  return result;
}

/**
 * Handle project_switch tool call.
 */
export async function handleProjectSwitch(args: {
  project_name: string;
  limit?: number;
}): Promise<{
  project: string;
  note_count: number;
  recent_notes: Array<{
    note_id: number;
    title: string;
    permalink: string | null;
    note_type: string;
    updated_at: string | null;
  }>;
}> {
  const projectNotes = await client.listProjectNotes(
    args.project_name,
    args.limit || 10,
    0
  );

  // Get project list to find note count
  const projects = await client.listProjects();
  const project = projects.projects.find((p) => p.name === args.project_name);

  return {
    project: args.project_name,
    note_count: project?.note_count || projectNotes.total_count,
    recent_notes: projectNotes.notes,
  };
}

/**
 * Handle project_create tool call.
 */
export async function handleProjectCreate(args: {
  project_name: string;
}): Promise<{
  project: string;
  status: string;
  message: string;
}> {
  return await client.createProject(args.project_name);
}
