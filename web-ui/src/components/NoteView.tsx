'use client';

/**
 * Note view/editor component with title input and TipTap editor.
 *
 * Features:
 * - Title input field
 * - TipTap WYSIWYG editor for content
 * - Save status indicator
 * - Breadcrumb path display
 * - Autosave with debounce
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import TipTapEditor from '@/components/TipTapEditor';
import { ConnectionStatusCompact } from '@/components/ConnectionStatus';
import { useUpdateNote } from '@/lib/hooks/useNotes';
import type { Note } from '@/lib/supabase-client';
import type { ConnectionStatus } from '@/lib/supabase-realtime';

// ============================================================================
// Types
// ============================================================================

interface NoteViewProps {
  /** The note to display/edit */
  note: Note | null | undefined;
  /** Whether the note is loading */
  isLoading?: boolean;
  /** Connection status for realtime sync */
  connectionStatus?: ConnectionStatus;
  /** Callback when a wikilink is clicked */
  onWikilinkClick?: (target: string) => void;
  /** Additional CSS classes */
  className?: string;
}

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Extracts breadcrumb parts from a note path.
 */
function getBreadcrumbs(path: string): string[] {
  if (!path) return [];
  // Remove .md extension and split by /
  return path.replace(/\.md$/, '').split('/').filter(Boolean);
}

// ============================================================================
// Breadcrumb Component
// ============================================================================

interface BreadcrumbsProps {
  path: string;
}

function Breadcrumbs({ path }: BreadcrumbsProps) {
  const parts = getBreadcrumbs(path);

  if (parts.length === 0) return null;

  return (
    <nav className="flex items-center text-xs text-gray-500 dark:text-gray-400 overflow-x-auto">
      {parts.map((part, index) => (
        <span key={index} className="flex items-center">
          {index > 0 && (
            <svg
              className="w-3 h-3 mx-1 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          )}
          <span className="whitespace-nowrap">{part}</span>
        </span>
      ))}
    </nav>
  );
}

// ============================================================================
// Save Status Indicator
// ============================================================================

interface SaveStatusIndicatorProps {
  status: SaveStatus;
}

function SaveStatusIndicator({ status }: SaveStatusIndicatorProps) {
  const statusConfig: Record<SaveStatus, { text: string; className: string }> = {
    idle: { text: '', className: '' },
    saving: {
      text: 'Saving...',
      className: 'text-gray-500 dark:text-gray-400',
    },
    saved: {
      text: 'Saved',
      className: 'text-green-600 dark:text-green-400',
    },
    error: {
      text: 'Error saving',
      className: 'text-red-600 dark:text-red-400',
    },
  };

  const config = statusConfig[status];

  if (status === 'idle') return null;

  return (
    <span className={`text-xs ${config.className} flex items-center gap-1`}>
      {status === 'saving' && (
        <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      )}
      {status === 'saved' && (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M5 13l4 4L19 7"
          />
        </svg>
      )}
      {status === 'error' && (
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      )}
      {config.text}
    </span>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function NoteView({
  note,
  isLoading = false,
  connectionStatus = 'disconnected',
  onWikilinkClick,
  className = '',
}: NoteViewProps) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const titleRef = useRef<HTMLInputElement>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastSavedRef = useRef<{ title: string; content: string } | null>(null);

  const updateNote = useUpdateNote();

  // Update local state when note changes
  useEffect(() => {
    if (note) {
      setTitle(note.title || '');
      setContent(note.content || '');
      lastSavedRef.current = { title: note.title || '', content: note.content || '' };
    }
  }, [note?.id]); // Only update when note ID changes

  // Autosave function
  const performSave = useCallback(
    async (newTitle: string, newContent: string) => {
      if (!note?.id) return;

      // Check if anything changed
      if (
        lastSavedRef.current &&
        newTitle === lastSavedRef.current.title &&
        newContent === lastSavedRef.current.content
      ) {
        return;
      }

      setSaveStatus('saving');
      try {
        await updateNote.mutateAsync({
          id: note.id,
          title: newTitle,
          content: newContent,
        });
        lastSavedRef.current = { title: newTitle, content: newContent };
        setSaveStatus('saved');
        // Clear saved status after 2 seconds
        setTimeout(() => setSaveStatus('idle'), 2000);
      } catch (error) {
        console.error('Failed to save note:', error);
        setSaveStatus('error');
      }
    },
    [note?.id, updateNote]
  );

  // Debounced save on title change
  const handleTitleChange = useCallback(
    (newTitle: string) => {
      setTitle(newTitle);

      // Clear existing timeout
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }

      // Schedule save
      saveTimeoutRef.current = setTimeout(() => {
        performSave(newTitle, content);
      }, 2000);
    },
    [content, performSave]
  );

  // Handle content autosave from TipTap
  const handleAutoSave = useCallback(
    (newContent: string) => {
      setContent(newContent);
      performSave(title, newContent);
    },
    [title, performSave]
  );

  // Handle content change (without autosave - TipTap handles that)
  const handleContentChange = useCallback((newContent: string) => {
    setContent(newContent);
  }, []);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  // Loading state
  if (isLoading) {
    return (
      <div className={`flex flex-col h-full bg-white dark:bg-gray-900 ${className}`}>
        <div className="p-4 animate-pulse">
          <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-4" />
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mb-6" />
          <div className="space-y-3">
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded" />
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-5/6" />
            <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-4/6" />
          </div>
        </div>
      </div>
    );
  }

  // No note selected
  if (!note) {
    return (
      <div className={`flex flex-col h-full bg-white dark:bg-gray-900 ${className}`}>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <svg
              className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-1">
              No note selected
            </h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Select a note from the sidebar to view or edit it
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full bg-white dark:bg-gray-900 ${className}`}>
      {/* Header */}
      <div className="flex-shrink-0 px-6 pt-4 pb-2 border-b border-gray-200 dark:border-gray-700">
        {/* Status Bar */}
        <div className="flex items-center justify-between mb-2">
          <Breadcrumbs path={note.path} />
          <div className="flex items-center gap-3">
            <SaveStatusIndicator status={saveStatus} />
            <ConnectionStatusCompact status={connectionStatus} />
          </div>
        </div>

        {/* Title Input */}
        <input
          ref={titleRef}
          type="text"
          value={title}
          onChange={(e) => handleTitleChange(e.target.value)}
          placeholder="Untitled"
          className="
            w-full text-2xl font-bold
            bg-transparent
            text-gray-900 dark:text-white
            placeholder-gray-400 dark:placeholder-gray-500
            border-none outline-none
            focus:ring-0
          "
        />
      </div>

      {/* Editor */}
      <div className="flex-1 overflow-hidden">
        <TipTapEditor
          key={note.id} // Force re-render when note changes
          initialContent={content}
          onChange={handleContentChange}
          onAutoSave={handleAutoSave}
          autoSaveDelay={2000}
          placeholder="Start writing..."
          onWikilinkClick={onWikilinkClick}
          className="h-full border-0 rounded-none"
        />
      </div>
    </div>
  );
}

// ============================================================================
// New Note View Component
// ============================================================================

interface NewNoteViewProps {
  /** Callback when note is created */
  onNoteCreated: (note: Note) => void;
  /** Callback to cancel creation */
  onCancel: () => void;
  /** Connection status */
  connectionStatus?: ConnectionStatus;
  /** Additional CSS classes */
  className?: string;
}

export function NewNoteView({
  onNoteCreated,
  onCancel,
  connectionStatus = 'disconnected',
  className = '',
}: NewNoteViewProps) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);

  // Focus title input on mount
  useEffect(() => {
    titleRef.current?.focus();
  }, []);

  const handleCreate = useCallback(async () => {
    if (!title.trim()) return;

    setIsCreating(true);
    try {
      // Generate a path from the title
      const path = `notes/${title.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')}.md`;

      // Note: This would use useCreateNote, but for now we'll pass the data up
      // The parent component should handle the actual creation
      const tempNote: Note = {
        id: `temp-${Date.now()}`,
        title: title.trim(),
        content,
        path,
        frontmatter: {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        user_id: '',
      };

      onNoteCreated(tempNote);
    } catch (error) {
      console.error('Failed to create note:', error);
    } finally {
      setIsCreating(false);
    }
  }, [title, content, onNoteCreated]);

  return (
    <div className={`flex flex-col h-full bg-white dark:bg-gray-900 ${className}`}>
      {/* Header */}
      <div className="flex-shrink-0 px-6 pt-4 pb-2 border-b border-gray-200 dark:border-gray-700">
        {/* Status Bar */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-500 dark:text-gray-400">New Note</span>
          <div className="flex items-center gap-2">
            <button
              onClick={onCancel}
              className="px-3 py-1 text-xs text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={!title.trim() || isCreating}
              className="
                px-3 py-1 text-xs font-medium
                bg-blue-600 text-white rounded
                hover:bg-blue-700
                disabled:opacity-50 disabled:cursor-not-allowed
              "
            >
              {isCreating ? 'Creating...' : 'Create'}
            </button>
            <ConnectionStatusCompact status={connectionStatus} />
          </div>
        </div>

        {/* Title Input */}
        <input
          ref={titleRef}
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Note title..."
          className="
            w-full text-2xl font-bold
            bg-transparent
            text-gray-900 dark:text-white
            placeholder-gray-400 dark:placeholder-gray-500
            border-none outline-none
            focus:ring-0
          "
        />
      </div>

      {/* Editor */}
      <div className="flex-1 overflow-hidden">
        <TipTapEditor
          initialContent=""
          onChange={setContent}
          placeholder="Start writing..."
          className="h-full border-0 rounded-none"
        />
      </div>
    </div>
  );
}
