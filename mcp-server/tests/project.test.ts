/**
 * Tests for project management MCP tools.
 */

import { describe, expect, test } from 'bun:test';
import {
  handleProjectCreate,
  handleProjectList,
  handleProjectSwitch,
  projectTools,
} from '../src/tools/project.js';

describe('Project Tools', () => {
  describe('Tool Schemas', () => {
    test('project_list tool has correct schema', () => {
      const tool = projectTools.find((t) => t.name === 'project_list');
      expect(tool).toBeDefined();
      expect(tool?.inputSchema).toEqual({
        type: 'object',
        properties: {},
      });
    });

    test('project_switch tool has correct schema', () => {
      const tool = projectTools.find((t) => t.name === 'project_switch');
      expect(tool).toBeDefined();
      expect(tool?.inputSchema.type).toBe('object');
      expect(tool?.inputSchema.properties?.project_name).toBeDefined();
      expect(tool?.inputSchema.properties?.limit).toBeDefined();
      expect(tool?.inputSchema.required).toContain('project_name');
    });

    test('project_create tool has correct schema', () => {
      const tool = projectTools.find((t) => t.name === 'project_create');
      expect(tool).toBeDefined();
      expect(tool?.inputSchema.type).toBe('object');
      expect(tool?.inputSchema.properties?.project_name).toBeDefined();
      expect(tool?.inputSchema.required).toContain('project_name');
    });
  });

  // Integration tests require a running backend
  // These are skipped for now
  describe.skip('Integration Tests', () => {
    test('handleProjectList returns projects', async () => {
      const result = await handleProjectList();
      expect(result).toHaveProperty('projects');
      expect(Array.isArray(result.projects)).toBe(true);
    });

    test('handleProjectSwitch returns project info', async () => {
      const result = await handleProjectSwitch({ project_name: 'test-project' });
      expect(result).toHaveProperty('project');
      expect(result).toHaveProperty('note_count');
      expect(result).toHaveProperty('recent_notes');
    });

    test('handleProjectCreate validates project name', async () => {
      const result = await handleProjectCreate({ project_name: 'valid-project' });
      expect(result).toHaveProperty('project');
      expect(result).toHaveProperty('status');
    });
  });
});
