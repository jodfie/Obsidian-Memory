'use client';

/**
 * Main notes page with three-panel layout.
 *
 * Layout:
 * - Left sidebar (20%): searchable notes list
 * - Main area (50%): TipTap editor with title
 * - Right panel (30%): graph visualization (collapsible)
 *
 * Features:
 * - Three-panel responsive layout
 * - Keyboard shortcuts: Cmd+K (search), Cmd+N (new note)
 * - Real-time sync with Supabase
 * - Mobile responsive (stacked layout)
 */

import { useState, useEffect, useCallback, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import NotesList from '@/components/NotesList';
import NoteView, { NewNoteView } from '@/components/NoteView';
import GraphPanel from '@/components/GraphPanel';
import ConnectionStatus from '@/components/ConnectionStatus';
import { useConnectionStatus } from '@/lib/hooks/useRealtimeNotes';
import { useNote, useCreateNote, useSearchNotes } from '@/lib/hooks/useNotes';
import { useAuth } from '@/components/AuthProvider';
import type { Note } from '@/lib/supabase-client';

// ============================================================================
// Types
// ============================================================================

type ViewMode = 'view' | 'new';

// ============================================================================
// Command Palette (Search Modal)
// ============================================================================

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectNote: (note: Note) => void;
  onCreateNote: () => void;
}

function CommandPalette({
  isOpen,
  onClose,
  onSelectNote,
  onCreateNote,
}: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: searchResults, isLoading } = useSearchNotes(query, {
    limit: 10,
    enabled: isOpen && query.length > 0,
  });

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'Enter' && !query.trim()) {
        onCreateNote();
        onClose();
      }
    },
    [onClose, onCreateNote, query]
  );

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg bg-white dark:bg-gray-800 rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input */}
        <div className="flex items-center px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <svg
            className="w-5 h-5 text-gray-400 mr-3"
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
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search notes or create new..."
            className="
              flex-1 bg-transparent
              text-gray-900 dark:text-white
              placeholder-gray-400 dark:placeholder-gray-500
              border-none outline-none text-base
            "
          />
          <kbd className="hidden sm:inline-block px-2 py-1 text-xs font-medium text-gray-400 bg-gray-100 dark:bg-gray-700 rounded">
            Esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 text-center text-gray-500 dark:text-gray-400">
              Searching...
            </div>
          ) : searchResults?.notes && searchResults.notes.length > 0 ? (
            <div className="py-2">
              {searchResults.notes.map((note) => (
                <button
                  key={note.id}
                  onClick={() => {
                    onSelectNote(note);
                    onClose();
                  }}
                  className="
                    w-full px-4 py-2 text-left
                    hover:bg-gray-100 dark:hover:bg-gray-700
                    focus:bg-gray-100 dark:focus:bg-gray-700
                    focus:outline-none
                  "
                >
                  <div className="font-medium text-gray-900 dark:text-white text-sm">
                    {note.title || 'Untitled'}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                    {note.path}
                  </div>
                </button>
              ))}
            </div>
          ) : query.length > 0 ? (
            <div className="p-4 text-center">
              <p className="text-gray-500 dark:text-gray-400 text-sm mb-2">
                No notes found for "{query}"
              </p>
              <button
                onClick={() => {
                  onCreateNote();
                  onClose();
                }}
                className="text-blue-600 dark:text-blue-400 text-sm hover:underline"
              >
                Create a new note
              </button>
            </div>
          ) : (
            <div className="p-4">
              <button
                onClick={() => {
                  onCreateNote();
                  onClose();
                }}
                className="
                  w-full flex items-center gap-3 px-3 py-2
                  text-gray-600 dark:text-gray-300
                  hover:bg-gray-100 dark:hover:bg-gray-700
                  rounded-lg
                "
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 4v16m8-8H4"
                  />
                </svg>
                <span>Create new note</span>
                <kbd className="ml-auto px-2 py-1 text-xs text-gray-400 bg-gray-100 dark:bg-gray-700 rounded">
                  Enter
                </kbd>
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
          <div className="flex items-center justify-between text-xs text-gray-400">
            <span>Type to search</span>
            <div className="flex items-center gap-2">
              <kbd className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">Enter</kbd>
              <span>to create</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Main Page Component
// ============================================================================

export default function NotesPageWrapper() {
  return (
    <Suspense fallback={
      <div className="h-[calc(100vh-56px)] flex items-center justify-center bg-gray-100 dark:bg-gray-950">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    }>
      <NotesPage />
    </Suspense>
  );
}

function NotesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isLoading: authLoading } = useAuth();

  // State
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('view');
  const [isGraphCollapsed, setIsGraphCollapsed] = useState(false);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  // Get user ID from auth
  const userId = user?.id ?? '';

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
    }
  }, [user, authLoading, router]);

  // Show loading while checking auth
  if (authLoading) {
    return (
      <div className="h-[calc(100vh-56px)] flex items-center justify-center bg-gray-100 dark:bg-gray-950">
        <div className="text-gray-500 dark:text-gray-400">Loading...</div>
      </div>
    );
  }

  // Don't render if not authenticated
  if (!user) {
    return null;
  }

  // Hooks
  const connectionStatus = useConnectionStatus(userId);
  const createNote = useCreateNote();

  // Fetch selected note
  const {
    data: selectedNote,
    isLoading: noteLoading,
  } = useNote(selectedNoteId);

  // Get note ID from URL on mount
  useEffect(() => {
    const noteId = searchParams?.get('id');
    if (noteId) {
      setSelectedNoteId(noteId);
    }
  }, [searchParams]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Cmd+K or Ctrl+K - Open command palette / search
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen(true);
      }

      // Cmd+N or Ctrl+N - New note
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault();
        handleCreateNote();
      }

      // Escape - Close command palette
      if (e.key === 'Escape') {
        setIsCommandPaletteOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Handlers
  const handleSelectNote = useCallback((note: Note) => {
    setSelectedNoteId(note.id);
    setViewMode('view');
    // Update URL without full navigation
    window.history.replaceState(null, '', `/app/notes?id=${note.id}`);
  }, []);

  const handleCreateNote = useCallback(() => {
    setSelectedNoteId(null);
    setViewMode('new');
  }, []);

  const handleNoteCreated = useCallback(
    async (tempNote: Note) => {
      try {
        const newNote = await createNote.mutateAsync({
          title: tempNote.title,
          content: tempNote.content,
          path: tempNote.path,
          user_id: userId,
        });

        setSelectedNoteId(newNote.id);
        setViewMode('view');
        window.history.replaceState(null, '', `/app/notes?id=${newNote.id}`);
      } catch (error) {
        console.error('Failed to create note:', error);
      }
    },
    [createNote, userId]
  );

  const handleCancelCreate = useCallback(() => {
    setViewMode('view');
  }, []);

  const handleWikilinkClick = useCallback(
    (target: string) => {
      // Navigate to the linked note
      // For now, we'll search by title/path
      console.log('Wikilink clicked:', target);
      // You could implement a lookup here
    },
    []
  );

  const handleNavigateToNote = useCallback((note: Note) => {
    handleSelectNote(note);
  }, [handleSelectNote]);

  return (
    <div className="h-[calc(100vh-56px)] flex overflow-hidden bg-gray-100 dark:bg-gray-950">
      {/* Left Sidebar - Notes List */}
      <div
        className={`
          flex-shrink-0 border-r border-gray-200 dark:border-gray-800
          transition-all duration-300
          ${isSidebarCollapsed ? 'w-0 overflow-hidden' : 'w-64 lg:w-72 xl:w-80'}
        `}
      >
        <div className="h-full flex flex-col">
          {/* Sidebar Header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
              Notes
            </h2>
            <div className="flex items-center gap-1">
              <ConnectionStatus status={connectionStatus} size="sm" showLabel={false} />
              <button
                onClick={() => setIsSidebarCollapsed(true)}
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 lg:hidden"
                title="Collapse sidebar"
              >
                <svg
                  className="w-4 h-4 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 19l-7-7 7-7"
                  />
                </svg>
              </button>
            </div>
          </div>

          {/* Notes List */}
          <NotesList
            selectedNoteId={selectedNoteId}
            onSelectNote={handleSelectNote}
            onCreateNote={handleCreateNote}
            className="flex-1"
          />
        </div>
      </div>

      {/* Mobile Sidebar Toggle */}
      {isSidebarCollapsed && (
        <button
          onClick={() => setIsSidebarCollapsed(false)}
          className="
            absolute left-2 top-20 z-10
            p-2 rounded-lg bg-white dark:bg-gray-800 shadow-lg
            hover:bg-gray-100 dark:hover:bg-gray-700
            lg:hidden
          "
        >
          <svg
            className="w-5 h-5 text-gray-600 dark:text-gray-300"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
      )}

      {/* Main Editor Area */}
      <div className="flex-1 min-w-0 flex flex-col">
        {viewMode === 'new' ? (
          <NewNoteView
            onNoteCreated={handleNoteCreated}
            onCancel={handleCancelCreate}
            connectionStatus={connectionStatus}
            className="flex-1"
          />
        ) : (
          <NoteView
            note={selectedNote}
            isLoading={noteLoading}
            connectionStatus={connectionStatus}
            onWikilinkClick={handleWikilinkClick}
            className="flex-1"
          />
        )}
      </div>

      {/* Right Panel - Graph */}
      <div
        className={`
          flex-shrink-0 border-l border-gray-200 dark:border-gray-800
          transition-all duration-300
          hidden md:block
          ${isGraphCollapsed ? 'w-12' : 'w-64 lg:w-72 xl:w-80'}
        `}
      >
        <GraphPanel
          noteId={selectedNoteId}
          onNavigateToNote={handleNavigateToNote}
          isCollapsed={isGraphCollapsed}
          onToggleCollapse={() => setIsGraphCollapsed(!isGraphCollapsed)}
        />
      </div>

      {/* Command Palette */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onSelectNote={handleSelectNote}
        onCreateNote={handleCreateNote}
      />

      {/* Keyboard Shortcuts Hint */}
      <div className="fixed bottom-4 right-4 hidden lg:flex items-center gap-4 text-xs text-gray-400 dark:text-gray-500">
        <span className="flex items-center gap-1">
          <kbd className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">Cmd+K</kbd>
          Search
        </span>
        <span className="flex items-center gap-1">
          <kbd className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">Cmd+N</kbd>
          New
        </span>
      </div>
    </div>
  );
}
