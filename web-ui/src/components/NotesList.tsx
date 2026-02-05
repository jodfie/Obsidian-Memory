'use client';

/**
 * Notes list component with search functionality.
 *
 * Features:
 * - Search bar at top
 * - List of notes with title, date, and snippet preview
 * - Selected state styling
 * - Click to select note
 */

import { useState, useCallback, useMemo } from 'react';
import { useSearchNotes, useNotes } from '@/lib/hooks/useNotes';
import type { Note } from '@/lib/supabase-client';

// ============================================================================
// Types
// ============================================================================

interface NotesListProps {
  /** Currently selected note ID */
  selectedNoteId?: string | null;
  /** Callback when a note is selected */
  onSelectNote: (note: Note) => void;
  /** Callback to create a new note */
  onCreateNote?: () => void;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Formats a date as a relative time string.
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    if (diffHours === 0) {
      const diffMinutes = Math.floor(diffMs / (1000 * 60));
      if (diffMinutes === 0) return 'Just now';
      return `${diffMinutes}m ago`;
    }
    return `${diffHours}h ago`;
  }
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
  return `${Math.floor(diffDays / 365)}y ago`;
}

/**
 * Extracts a snippet from markdown content.
 */
function getSnippet(content: string, maxLength: number = 100): string {
  // Remove markdown syntax
  const plainText = content
    .replace(/^#+\s*/gm, '') // Headers
    .replace(/\*\*([^*]+)\*\*/g, '$1') // Bold
    .replace(/\*([^*]+)\*/g, '$1') // Italic
    .replace(/`([^`]+)`/g, '$1') // Inline code
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // Links
    .replace(/\[\[([^\]]+)\]\]/g, '$1') // Wikilinks
    .replace(/^[-*]\s+/gm, '') // List items
    .replace(/^\d+\.\s+/gm, '') // Numbered lists
    .replace(/\n+/g, ' ') // Newlines to spaces
    .trim();

  if (plainText.length <= maxLength) return plainText;
  return plainText.substring(0, maxLength).trim() + '...';
}

// ============================================================================
// Note Item Component
// ============================================================================

interface NoteItemProps {
  note: Note;
  isSelected: boolean;
  onClick: () => void;
}

function NoteItem({ note, isSelected, onClick }: NoteItemProps) {
  const snippet = useMemo(() => getSnippet(note.content), [note.content]);

  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left p-3 border-b border-gray-200 dark:border-gray-700
        transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500
        ${
          isSelected
            ? 'bg-blue-50 dark:bg-blue-900/30 border-l-4 border-l-blue-500'
            : 'hover:bg-gray-50 dark:hover:bg-gray-800 border-l-4 border-l-transparent'
        }
      `}
    >
      <div className="flex items-start justify-between gap-2">
        <h3
          className={`
            font-medium text-sm truncate flex-1
            ${isSelected ? 'text-blue-700 dark:text-blue-300' : 'text-gray-900 dark:text-white'}
          `}
        >
          {note.title || 'Untitled'}
        </h3>
        <span className="text-xs text-gray-400 dark:text-gray-500 whitespace-nowrap">
          {formatDate(note.updated_at)}
        </span>
      </div>
      {snippet && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
          {snippet}
        </p>
      )}
    </button>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function NotesList({
  selectedNoteId,
  onSelectNote,
  onCreateNote,
  className = '',
}: NotesListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');

  // Debounce search input
  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value);
    // Simple debounce using setTimeout
    const timeoutId = setTimeout(() => {
      setDebouncedQuery(value);
    }, 300);
    return () => clearTimeout(timeoutId);
  }, []);

  // Fetch notes - use search or list based on query
  const {
    data: searchResults,
    isLoading: searchLoading,
    error: searchError,
  } = useSearchNotes(debouncedQuery, { enabled: debouncedQuery.length > 0 });

  const {
    data: listResults,
    isLoading: listLoading,
    error: listError,
  } = useNotes({ limit: 100, orderBy: 'updated_at', orderDirection: 'desc' });

  // Determine which data to display
  const isSearching = debouncedQuery.length > 0;
  const notes = isSearching ? searchResults?.notes : listResults?.notes;
  const isLoading = isSearching ? searchLoading : listLoading;
  const error = isSearching ? searchError : listError;

  return (
    <div className={`flex flex-col h-full bg-white dark:bg-gray-900 ${className}`}>
      {/* Search Bar */}
      <div className="p-3 border-b border-gray-200 dark:border-gray-700">
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <svg
              className="h-4 w-4 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search notes..."
            className="
              w-full pl-10 pr-4 py-2 text-sm
              bg-gray-100 dark:bg-gray-800
              border border-transparent
              rounded-lg
              text-gray-900 dark:text-white
              placeholder-gray-500 dark:placeholder-gray-400
              focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
              transition-colors
            "
          />
          {searchQuery && (
            <button
              onClick={() => {
                setSearchQuery('');
                setDebouncedQuery('');
              }}
              className="absolute inset-y-0 right-0 pr-3 flex items-center"
            >
              <svg
                className="h-4 w-4 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}
        </div>

        {/* New Note Button */}
        {onCreateNote && (
          <button
            onClick={onCreateNote}
            className="
              w-full mt-2 px-4 py-2 text-sm font-medium
              bg-blue-600 hover:bg-blue-700
              text-white rounded-lg
              flex items-center justify-center gap-2
              transition-colors
            "
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4v16m8-8H4"
              />
            </svg>
            New Note
          </button>
        )}
      </div>

      {/* Notes List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-center">
            <div className="animate-pulse space-y-3">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded" />
              ))}
            </div>
          </div>
        ) : error ? (
          <div className="p-4 text-center text-red-500 dark:text-red-400">
            <p className="text-sm">Failed to load notes</p>
            <p className="text-xs mt-1">{error.message}</p>
          </div>
        ) : !notes || notes.length === 0 ? (
          <div className="p-4 text-center text-gray-500 dark:text-gray-400">
            <svg
              className="w-12 h-12 mx-auto mb-2 text-gray-300 dark:text-gray-600"
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
            <p className="text-sm">
              {isSearching ? 'No notes found' : 'No notes yet'}
            </p>
            {!isSearching && onCreateNote && (
              <button
                onClick={onCreateNote}
                className="text-blue-600 dark:text-blue-400 text-sm mt-1 hover:underline"
              >
                Create your first note
              </button>
            )}
          </div>
        ) : (
          <div>
            {isSearching && (
              <div className="px-3 py-2 text-xs text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                {notes.length} result{notes.length !== 1 ? 's' : ''} for "{debouncedQuery}"
              </div>
            )}
            {notes.map((note) => (
              <NoteItem
                key={note.id}
                note={note}
                isSelected={note.id === selectedNoteId}
                onClick={() => onSelectNote(note)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
