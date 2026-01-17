/**
 * Tests for context building tool.
 */

import { describe, expect, test } from 'bun:test';
import { buildContext, parseMemoryUri } from '../src/tools/context.js';

describe('Context Building', () => {
  test('parseMemoryUri - note by ID', () => {
    const result = parseMemoryUri('memory://note/123');
    expect(result.type).toBe('note');
    expect(result.params.id).toBe('123');
  });

  test('parseMemoryUri - note by permalink', () => {
    const result = parseMemoryUri('memory://note/auth-jwt-impl');
    expect(result.type).toBe('note');
    expect(result.params.permalink).toBe('auth-jwt-impl');
  });

  test('parseMemoryUri - search', () => {
    const result = parseMemoryUri('memory://search/authentication');
    expect(result.type).toBe('search');
    expect(result.params.query).toBe('authentication');
  });

  test('parseMemoryUri - path', () => {
    const result = parseMemoryUri('memory://path/test_vault/projects/api/auth.md');
    expect(result.type).toBe('path');
    expect(result.params.vault).toBe('test_vault');
    expect(result.params.path).toBe('projects/api/auth.md');
  });

  test('parseMemoryUri - graph neighbors', () => {
    const result = parseMemoryUri('memory://graph/neighbors/123');
    expect(result.type).toBe('graph');
    expect(result.params.operation).toBe('neighbors');
    expect(result.params.node_id).toBe('123');
  });

  test('parseMemoryUri - graph path', () => {
    const result = parseMemoryUri('memory://graph/path/1/5');
    expect(result.type).toBe('graph');
    expect(result.params.operation).toBe('path');
    expect(result.params.from_id).toBe('1');
    expect(result.params.to_id).toBe('5');
  });

  test('parseMemoryUri - graph reachable', () => {
    const result = parseMemoryUri('memory://graph/reachable/123');
    expect(result.type).toBe('graph');
    expect(result.params.operation).toBe('reachable');
    expect(result.params.node_id).toBe('123');
  });

  test('parseMemoryUri - tags', () => {
    const result = parseMemoryUri('memory://tags/security,backend');
    expect(result.type).toBe('tags');
    expect(result.params.tags).toBe('security,backend');
  });

  test('parseMemoryUri - project', () => {
    const result = parseMemoryUri('memory://project/api-service');
    expect(result.type).toBe('project');
    expect(result.params.project).toBe('api-service');
  });

  test('parseMemoryUri - invalid URI', () => {
    expect(() => parseMemoryUri('invalid://uri')).toThrow('Invalid memory URI');
  });

  test('parseMemoryUri - invalid format', () => {
    expect(() => parseMemoryUri('memory://')).toThrow('Invalid memory URI format');
  });

  // Note: Integration tests for buildContext would require a running backend
  test.skip('buildContext with multiple URIs', async () => {
    const result = await buildContext([
      'memory://note/1',
      'memory://search/authentication',
    ]);
    expect(result.total_notes).toBeGreaterThanOrEqual(0);
    expect(result.content).toBeDefined();
  });
});
