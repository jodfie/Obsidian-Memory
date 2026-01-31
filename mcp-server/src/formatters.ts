/**
 * Response formatters for Obsidian-Memory MCP server.
 * Supports JSON and Markdown output formats.
 */

import type { ResponseFormat } from './constants.js';
import { CHARACTER_LIMIT } from './constants.js';
import type { NoteResponse } from './client.js';

/**
 * Truncate content if it exceeds the character limit.
 */
export function truncateContent(content: string, limit: number = CHARACTER_LIMIT): string {
  if (content.length <= limit) {
    return content;
  }
  return content.slice(0, limit) + `\n\n[Content truncated at ${limit} characters]`;
}

/**
 * Format a single note for display.
 */
export function formatNote(note: NoteResponse, format: ResponseFormat = 'json'): string {
  if (format === 'markdown') {
    const parts: string[] = [
      `# ${note.title}`,
      '',
      `**Vault:** ${note.vault_name}`,
      `**Path:** ${note.relative_path}`,
    ];

    if (note.permalink) parts.push(`**Permalink:** ${note.permalink}`);
    if (note.project) parts.push(`**Project:** ${note.project}`);
    if (note.tags.length > 0) parts.push(`**Tags:** ${note.tags.join(', ')}`);
    if (note.created_at) parts.push(`**Created:** ${note.created_at}`);
    if (note.updated_at) parts.push(`**Updated:** ${note.updated_at}`);

    parts.push('', '---', '', note.content);

    return truncateContent(parts.filter(Boolean).join('\n'));
  }

  return truncateContent(JSON.stringify(note, null, 2));
}

/**
 * Format search results for display.
 */
export function formatSearchResults(
  results: { notes: NoteResponse[]; total: number },
  query: string,
  format: ResponseFormat = 'json',
  hasMore: boolean = false,
  nextOffset: number = 0
): string {
  if (format === 'markdown') {
    const parts: string[] = [
      `# Search Results for "${query}"`,
      '',
      `**Total:** ${results.total} notes found`,
      `**Showing:** ${results.notes.length} results`,
    ];

    if (hasMore) {
      parts.push(`**More available:** Use offset=${nextOffset} to load more`);
    }

    parts.push('', '---', '');

    for (const note of results.notes) {
      parts.push(`## ${note.title}`);
      if (note.permalink) parts.push(`*${note.permalink}*`);
      parts.push(`- **Type:** ${note.note_type}`);
      if (note.project) parts.push(`- **Project:** ${note.project}`);
      if (note.tags.length > 0) parts.push(`- **Tags:** ${note.tags.join(', ')}`);
      parts.push('');
    }

    return truncateContent(parts.join('\n'));
  }

  const response = {
    query,
    total: results.total,
    count: results.notes.length,
    has_more: hasMore,
    next_offset: hasMore ? nextOffset : null,
    notes: results.notes,
  };

  return truncateContent(JSON.stringify(response, null, 2));
}

/**
 * Format project list for display.
 */
export function formatProjectList(
  projects: Array<{ name: string; note_count: number }>,
  format: ResponseFormat = 'json'
): string {
  if (format === 'markdown') {
    const parts: string[] = [
      '# Projects',
      '',
      `**Total:** ${projects.length} projects`,
      '',
      '| Project | Notes |',
      '|---------|-------|',
    ];

    for (const project of projects) {
      parts.push(`| ${project.name} | ${project.note_count} |`);
    }

    return parts.join('\n');
  }

  return JSON.stringify({ projects, total: projects.length }, null, 2);
}

/**
 * Format session summary for display.
 */
export function formatSessionSummary(
  summary: {
    key_learnings: string[];
    decisions: string[];
    errors_encountered: string[];
    solutions_found: string[];
    next_steps: string[];
    summary_text: string;
    compression_ratio: number;
  },
  format: ResponseFormat = 'json'
): string {
  if (format === 'markdown') {
    const parts: string[] = ['# Session Summary', '', summary.summary_text, ''];

    if (summary.key_learnings.length > 0) {
      parts.push('## Key Learnings');
      summary.key_learnings.forEach((l) => parts.push(`- ${l}`));
      parts.push('');
    }

    if (summary.decisions.length > 0) {
      parts.push('## Decisions');
      summary.decisions.forEach((d) => parts.push(`- ${d}`));
      parts.push('');
    }

    if (summary.errors_encountered.length > 0) {
      parts.push('## Errors Encountered');
      summary.errors_encountered.forEach((e) => parts.push(`- ${e}`));
      parts.push('');
    }

    if (summary.solutions_found.length > 0) {
      parts.push('## Solutions Found');
      summary.solutions_found.forEach((s) => parts.push(`- ${s}`));
      parts.push('');
    }

    if (summary.next_steps.length > 0) {
      parts.push('## Next Steps');
      summary.next_steps.forEach((n) => parts.push(`- ${n}`));
      parts.push('');
    }

    parts.push(`*Compression ratio: ${summary.compression_ratio.toFixed(2)}*`);

    return parts.join('\n');
  }

  return JSON.stringify(summary, null, 2);
}

/**
 * Format graph traversal results for display.
 */
export function formatGraphTraversal(
  result: {
    visited_nodes: unknown[];
    paths: unknown[];
    depth_reached: number;
  },
  format: ResponseFormat = 'json'
): string {
  if (format === 'markdown') {
    const parts: string[] = [
      '# Graph Traversal Results',
      '',
      `**Nodes visited:** ${result.visited_nodes.length}`,
      `**Depth reached:** ${result.depth_reached}`,
      '',
      '## Visited Nodes',
      result.visited_nodes.map((n) => `- ${n}`).join('\n'),
    ];

    if (result.paths.length > 0) {
      parts.push('', '## Paths', JSON.stringify(result.paths, null, 2));
    }

    return parts.join('\n');
  }

  return JSON.stringify(result, null, 2);
}

/**
 * Format similar notes results for display.
 */
export function formatSimilarNotes(
  result: {
    similar_notes: unknown[];
    scores: unknown[];
  },
  format: ResponseFormat = 'json'
): string {
  if (format === 'markdown') {
    const parts: string[] = [
      '# Similar Notes',
      '',
      `**Found:** ${result.similar_notes.length} similar notes`,
      '',
    ];

    const notes = result.similar_notes as Array<{ id?: number; title?: string }>;
    const scores = result.scores as Array<{ note_id: number; score: number }>;

    notes.forEach((note, i) => {
      const score = scores[i];
      parts.push(`- **${note.title || 'Unknown'}** (ID: ${note.id || 'N/A'}, Score: ${score?.score?.toFixed(3) || 'N/A'})`);
    });

    return parts.join('\n');
  }

  return JSON.stringify(result, null, 2);
}
