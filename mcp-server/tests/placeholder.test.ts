/**
 * Placeholder tests to verify test infrastructure works.
 */

import { describe, expect, test } from 'bun:test';

describe('Test Infrastructure', () => {
  test('placeholder test passes', () => {
    expect(true).toBe(true);
  });

  test('can import from src', async () => {
    const module = await import('../src/index');
    expect(module.createServer).toBeDefined();
    expect(typeof module.createServer).toBe('function');
  });
});
