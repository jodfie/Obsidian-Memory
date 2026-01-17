'use client';

import { useState, useEffect } from 'react';
import {
  getNoteById,
  createNote,
  updateNote,
  type Note,
} from '../lib/api';

interface MarkdownEditorProps {
  noteId?: number | null;
  initialContent?: string;
  initialTitle?: string;
  onSave?: (note: Note) => void;
  onCancel?: () => void;
}

export default function MarkdownEditor({
  noteId,
  initialContent = '',
  initialTitle = '',
  onSave,
  onCancel,
}: MarkdownEditorProps) {
  const [title, setTitle] = useState(initialTitle);
  const [content, setContent] = useState(initialContent);
  const [preview, setPreview] = useState('');
  const [splitView, setSplitView] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load note if noteId is provided
  useEffect(() => {
    if (noteId) {
      loadNote();
    }
  }, [noteId]);

  // Update preview when content changes
  useEffect(() => {
    updatePreview();
  }, [content]);

  async function loadNote() {
    if (!noteId) return;

    try {
      setLoading(true);
      setError(null);
      const note = await getNoteById(noteId);
      setTitle(note.title);
      setContent(note.content);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load note');
    } finally {
      setLoading(false);
    }
  }

  function updatePreview() {
    // Simple markdown to HTML conversion
    // In production, use a proper markdown library like marked or remark
    let html = content
      // Headers
      .replace(/^# (.*$)/gim, '<h1 class="text-3xl font-bold mt-6 mb-4">$1</h1>')
      .replace(/^## (.*$)/gim, '<h2 class="text-2xl font-semibold mt-5 mb-3">$1</h2>')
      .replace(/^### (.*$)/gim, '<h3 class="text-xl font-semibold mt-4 mb-2">$1</h3>')
      .replace(/^#### (.*$)/gim, '<h4 class="text-lg font-semibold mt-3 mb-2">$1</h4>')
      // Bold and italic
      .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/gim, '<em>$1</em>')
      // Code
      .replace(/`([^`]+)`/gim, '<code class="bg-gray-100 dark:bg-gray-700 px-1 py-0.5 rounded">$1</code>')
      // Wikilinks
      .replace(/\[\[([^\]]+)\]\]/gim, '<a href="#" class="text-blue-600 dark:text-blue-400 hover:underline">$1</a>')
      // Links
      .replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2" class="text-blue-600 dark:text-blue-400 hover:underline">$1</a>')
      // Paragraphs (split by double newlines)
      .split(/\n\n+/)
      .map((para) => {
        if (para.trim().startsWith('<')) {
          return para; // Already HTML
        }
        return `<p class="mb-4">${para.replace(/\n/g, '<br>')}</p>`;
      })
      .join('');

    setPreview(html);
  }

  async function handleSave() {
    try {
      setSaving(true);
      setError(null);

      let note: Note;
      if (noteId) {
        // Update existing note
        note = await updateNote(noteId, {
          title: title || 'Untitled',
          content: content,
        });
      } else {
        // Create new note
        const noteTitle = title || 'Untitled';
        note = await createNote({
          title: noteTitle,
          content: content,
          relative_path: `${noteTitle.toLowerCase().replace(/\s+/g, '-')}.md`,
        });
      }

      if (onSave) {
        onSave(note);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save note');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading note...</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-900">
      {/* Toolbar */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Note title..."
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 mr-4"
          />
          <div className="flex gap-2">
            <button
              onClick={() => setSplitView(!splitView)}
              className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition"
            >
              {splitView ? 'Editor Only' : 'Split View'}
            </button>
            {onCancel && (
              <button
                onClick={onCancel}
                className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600 transition"
              >
                Cancel
              </button>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
        {error && (
          <div className="mt-2 p-2 bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-200 rounded text-sm">
            {error}
          </div>
        )}
      </div>

      {/* Editor and Preview */}
      <div className="flex-1 flex overflow-hidden">
        {/* Editor */}
        <div
          className={`${
            splitView ? 'w-1/2' : 'w-full'
          } border-r border-gray-200 dark:border-gray-700`}
        >
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Start writing your note in Markdown..."
            className="w-full h-full p-6 font-mono text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white border-none focus:outline-none resize-none"
            spellCheck={false}
          />
        </div>

        {/* Preview */}
        {splitView && (
          <div className="w-1/2 overflow-y-auto p-6 bg-white dark:bg-gray-800">
            <div
              className="prose prose-gray dark:prose-invert max-w-none"
              dangerouslySetInnerHTML={{
                __html:
                  preview ||
                  '<p class="text-gray-400 dark:text-gray-500">Preview will appear here...</p>',
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
