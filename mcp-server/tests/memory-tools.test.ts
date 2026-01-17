/**Tests for memory tools.*/

import { describe, expect, test, mock } from 'bun:test';

import { ApiClient } from '../src/tools/api-client';
import {
  getMemReadTool,
  getMemSearchTool,
  getMemWriteTool,
  handleMemRead,
  handleMemSearch,
  handleMemWrite,
} from '../src/tools/memory-tools';

describe('Memory Tools', () => {
  describe('Tool Definitions', () => {
    test('mem_read tool has correct schema', () => {
      const tool = getMemReadTool();
      expect(tool.name).toBe('mem_read');
      expect(tool.inputSchema).toBeDefined();
      expect(tool.inputSchema.type).toBe('object');
    });

    test('mem_write tool has correct schema', () => {
      const tool = getMemWriteTool();
      expect(tool.name).toBe('mem_write');
      expect(tool.inputSchema).toBeDefined();
      expect(tool.inputSchema.required).toContain('title');
      expect(tool.inputSchema.required).toContain('content');
    });

    test('mem_search tool has correct schema', () => {
      const tool = getMemSearchTool();
      expect(tool.name).toBe('mem_search');
      expect(tool.inputSchema).toBeDefined();
    });
  });

  describe('mem_read', () => {
    test('reads note by ID', async () => {
      const mockClient = {
        getNoteById: mock(async (id: number) => ({
          id,
          vault_name: 'test_vault',
          relative_path: 'test.md',
          permalink: 'test',
          title: 'Test Note',
          note_type: 'note',
          project: null,
          content: '# Test Note\n\nContent',
          tags: [],
          created_at: '2025-01-15T10:00:00Z',
          updated_at: '2025-01-16T14:00:00Z',
          parsed: null,
        })),
        searchNotes: mock(),
      } as unknown as ApiClient);

      const result = await handleMemRead({ note_id: 1 }, mockClient);

      expect(result.isError).toBe(false);
      expect(mockClient.getNoteById).toHaveBeenCalledWith(1);
      const content = JSON.parse(result.content[0]!.text);
      expect(content.id).toBe(1);
      expect(content.title).toBe('Test Note');
    });

    test('reads note by permalink', async () => {
      const mockClient = {
        getNoteById: mock(async (id: number) => ({
          id,
          vault_name: 'test_vault',
          relative_path: 'test.md',
          permalink: 'test',
          title: 'Test Note',
          note_type: 'note',
          project: null,
          content: '# Test Note',
          tags: [],
          created_at: null,
          updated_at: null,
          parsed: null,
        })),
        searchNotes: mock(async () => ({
          results: [{ note_id: 1, vault_name: 'test_vault', relative_path: 'test.md', permalink: 'test', title: 'Test Note', note_type: 'note', project: null, snippet: '', score: 1.0, created_at: null, updated_at: null, tags: [] }],
          total_count: 1,
          query: null,
          took_ms: 0,
        })),
      } as unknown as ApiClient;

      const result = await handleMemRead({ permalink: 'test' }, mockClient);

      expect(result.isError).toBe(false);
      expect(mockClient.searchNotes).toHaveBeenCalled();
    });

    test('throws error if no identifier provided', async () => {
      const mockClient = {} as ApiClient;

      await expect(
        handleMemRead({}, mockClient)
      ).rejects.toThrow('Must provide note_id, permalink, or (vault_name + relative_path)');
    });
  });

  describe('mem_write', () => {
    test('creates new note', async () => {
      const mockClient = {
        createNote: mock(async (req) => ({
          id: 1,
          vault_name: req.vault_name,
          relative_path: req.relative_path,
          permalink: 'test-note',
          title: req.title,
          note_type: req.note_type || 'note',
          project: req.project,
          content: req.content,
          tags: req.tags || [],
          created_at: '2025-01-15T10:00:00Z',
          updated_at: '2025-01-15T10:00:00Z',
          parsed: null,
        })),
        updateNote: mock(),
      } as unknown as ApiClient);

      const result = await handleMemWrite(
        {
          vault_name: 'test_vault',
          relative_path: 'test.md',
          title: 'Test Note',
          content: '# Test Note',
        },
        mockClient
      );

      expect(result.isError).toBe(false);
      expect(mockClient.createNote).toHaveBeenCalled();
      const content = JSON.parse(result.content[0]!.text);
      expect(content.id).toBe(1);
    });

    test('updates existing note', async () => {
      const mockClient = {
        updateNote: mock(async (id: number, req) => ({
          id,
          vault_name: 'test_vault',
          relative_path: 'test.md',
          permalink: 'test',
          title: req.title,
          note_type: req.note_type || 'note',
          project: req.project,
          content: req.content,
          tags: req.tags || [],
          created_at: '2025-01-15T10:00:00Z',
          updated_at: '2025-01-16T14:00:00Z',
          parsed: null,
        })),
        createNote: mock(),
      } as unknown as ApiClient;

      const result = await handleMemWrite(
        {
          note_id: 1,
          title: 'Updated Title',
          content: '# Updated',
        },
        mockClient
      );

      expect(result.isError).toBe(false);
      expect(mockClient.updateNote).toHaveBeenCalledWith(1, expect.any(Object));
    });

    test('throws error if vault_name/relative_path missing for new note', async () => {
      const mockClient = {} as ApiClient;

      await expect(
        handleMemWrite(
          {
            title: 'Test',
            content: '# Test',
          },
          mockClient
        )
      ).rejects.toThrow('vault_name and relative_path are required for new notes');
    });
  });

  describe('mem_search', () => {
    test('searches notes with query', async () => {
      const mockClient = {
        searchNotes: mock(async () => ({
          results: [
            {
              note_id: 1,
              vault_name: 'test_vault',
              relative_path: 'test.md',
              permalink: 'test',
              title: 'Test Note',
              note_type: 'note',
              project: null,
              snippet: 'Test <mark>content</mark>',
              score: 1.5,
              created_at: null,
              updated_at: null,
              tags: ['test'],
            },
          ],
          total_count: 1,
          query: 'content',
          took_ms: 10.5,
        })),
      } as unknown as ApiClient;

      const result = await handleMemSearch({ query: 'content' }, mockClient);

      expect(result.isError).toBe(false);
      expect(mockClient.searchNotes).toHaveBeenCalledWith(
        expect.objectContaining({ q: 'content' })
      );
      const content = JSON.parse(result.content[0]!.text);
      expect(content.total_count).toBe(1);
      expect(content.results.length).toBe(1);
    });

    test('searches with filters', async () => {
      const mockClient = {
        searchNotes: mock(async () => ({
          results: [],
          total_count: 0,
          query: 'test',
          took_ms: 5.0,
        })),
      } as unknown as ApiClient;

      await handleMemSearch(
        {
          query: 'test',
          vault: 'test_vault',
          project: 'test-project',
          note_type: 'decision',
          tags: 'tag1,tag2',
          limit: 10,
        },
        mockClient
      );

      expect(mockClient.searchNotes).toHaveBeenCalledWith(
        expect.objectContaining({
          q: 'test',
          vault: 'test_vault',
          project: 'test-project',
          note_type: 'decision',
          tags: 'tag1,tag2',
          limit: 10,
        })
      );
    });
  });
});
