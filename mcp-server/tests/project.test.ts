/**
 * Tests for project management MCP tools.
 */

import { describe, expect, test } from 'bun:test';
import { tools } from '../src/tools.js';
import {
  handleProjectCreate,
  handleProjectList,
  handleProjectSwitch,
} from '../src/handlers.js';

// Get project tools from the tools array
const projectTools = tools.filter((t) =>
  ['project_list', 'project_switch', 'project_create'].includes(t.name)
);

describe('Project Tools', () => {
  describe('Tool Schemas', () => {
    test('project_list tool has correct schema', () => {
      const tool = projectTools.find((t) => t.name === 'project_list');
      expect(tool).toBeDefined();
      expect(tool?.inputSchema.type).toBe('object');
      expect(tool?.inputSchema.properties).toBeDefined();
      // project_list has optional response_format property
      expect(tool?.inputSchema.properties?.response_format).toBeDefined();
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
      const result = await handleProjectList({});
      expect(result.structuredContent).toBeDefined();
    });

    test('handleProjectSwitch returns project info', async () => {
      const result = await handleProjectSwitch({ project_name: 'test-project' });
      expect(result.structuredContent).toBeDefined();
    });

    test('handleProjectCreate validates project name', async () => {
      const result = await handleProjectCreate({ project_name: 'valid-project' });
      expect(result.structuredContent).toBeDefined();
    });
  });
});
