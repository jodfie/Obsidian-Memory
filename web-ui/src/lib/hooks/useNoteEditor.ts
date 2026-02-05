'use client';

/**
 * Hook for managing note editing with TipTap and autosave.
 *
 * Integrates TipTap editor with the notes API for:
 * - Loading note content
 * - Autosaving changes
 * - Tracking dirty state
 * - Handling save errors
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { useNote, useUpdateNote, useCreateNote } from './useNotes';
import type { Note, NoteInsert } from '../supabase-client';

interface UseNoteEditorOptions {
  /** Autosave delay in milliseconds (default: 2000) */
  autoSaveDelay?: number;
  /** Callback when note is saved successfully */
  onSaveSuccess?: (note: Note) => void;
  /** Callback when save fails */
  onSaveError?: (error: Error) => void;
}

interface UseNoteEditorReturn {
  /** Current note data (null if creating new) */
  note: Note | null | undefined;
  /** Whether the note is loading */
  isLoading: boolean;
  /** Whether the note is saving */
  isSaving: boolean;
  /** Whether there are unsaved changes */
  isDirty: boolean;
  /** Error if loading failed */
  loadError: Error | null;
  /** Error if saving failed */
  saveError: Error | null;
  /** Current title */
  title: string;
  /** Current content (markdown) */
  content: string;
  /** Update the title */
  setTitle: (title: string) => void;
  /** Update the content (markdown) */
  setContent: (content: string) => void;
  /** Manually trigger save */
  save: () => Promise<void>;
  /** Handle autosave (called by TipTap editor) */
  handleAutoSave: (markdown: string) => void;
  /** Reset to last saved state */
  reset: () => void;
}

/**
 * Hook for editing a note with autosave support.
 *
 * @param noteId - The note ID to edit (null for creating new)
 * @param options - Configuration options
 *
 * @example
 * ```tsx
 * function NoteEditorPage({ noteId }: { noteId: string }) {
 *   const {
 *     note,
 *     isLoading,
 *     isSaving,
 *     isDirty,
 *     title,
 *     content,
 *     setTitle,
 *     handleAutoSave,
 *   } = useNoteEditor(noteId);
 *
 *   if (isLoading) return <Loading />;
 *
 *   return (
 *     <div>
 *       <input value={title} onChange={e => setTitle(e.target.value)} />
 *       <TipTapEditor
 *         initialContent={content}
 *         onAutoSave={handleAutoSave}
 *       />
 *       {isDirty && <span>Unsaved changes</span>}
 *       {isSaving && <span>Saving...</span>}
 *     </div>
 *   );
 * }
 * ```
 */
export function useNoteEditor(
  noteId: string | null | undefined,
  options: UseNoteEditorOptions = {}
): UseNoteEditorReturn {
  const { autoSaveDelay = 2000, onSaveSuccess, onSaveError } = options;

  // Fetch existing note if editing
  const {
    data: note,
    isLoading: isLoadingNote,
    error: loadError,
  } = useNote(noteId);

  // Mutations
  const updateNote = useUpdateNote();
  const createNote = useCreateNote();

  // Local state
  const [title, setTitleState] = useState('');
  const [content, setContentState] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  const [saveError, setSaveError] = useState<Error | null>(null);

  // Refs for tracking
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastSavedTitleRef = useRef<string>('');
  const lastSavedContentRef = useRef<string>('');

  // Sync state when note loads
  useEffect(() => {
    if (note) {
      setTitleState(note.title);
      setContentState(note.content);
      lastSavedTitleRef.current = note.title;
      lastSavedContentRef.current = note.content;
      setIsDirty(false);
    }
  }, [note]);

  // Set title with dirty tracking
  const setTitle = useCallback((newTitle: string) => {
    setTitleState(newTitle);
    setIsDirty(newTitle !== lastSavedTitleRef.current || content !== lastSavedContentRef.current);

    // Schedule autosave
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    saveTimeoutRef.current = setTimeout(() => {
      performSave(newTitle, content);
    }, autoSaveDelay);
  }, [content, autoSaveDelay]);

  // Set content with dirty tracking (used internally)
  const setContent = useCallback((newContent: string) => {
    setContentState(newContent);
    setIsDirty(title !== lastSavedTitleRef.current || newContent !== lastSavedContentRef.current);
  }, [title]);

  // Perform the actual save
  const performSave = useCallback(async (titleToSave: string, contentToSave: string) => {
    // Don't save if nothing changed
    if (
      titleToSave === lastSavedTitleRef.current &&
      contentToSave === lastSavedContentRef.current
    ) {
      return;
    }

    setSaveError(null);

    try {
      let savedNote: Note;

      if (noteId) {
        // Update existing note
        savedNote = await updateNote.mutateAsync({
          id: noteId,
          title: titleToSave,
          content: contentToSave,
        });
      } else {
        // Create new note
        const noteData: NoteInsert = {
          title: titleToSave || 'Untitled',
          content: contentToSave,
          path: `${(titleToSave || 'untitled').toLowerCase().replace(/\s+/g, '-')}.md`,
        };
        savedNote = await createNote.mutateAsync(noteData);
      }

      lastSavedTitleRef.current = savedNote.title;
      lastSavedContentRef.current = savedNote.content;
      setIsDirty(false);

      if (onSaveSuccess) {
        onSaveSuccess(savedNote);
      }
    } catch (error) {
      const err = error instanceof Error ? error : new Error('Failed to save');
      setSaveError(err);
      if (onSaveError) {
        onSaveError(err);
      }
    }
  }, [noteId, updateNote, createNote, onSaveSuccess, onSaveError]);

  // Manual save
  const save = useCallback(async () => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
    await performSave(title, content);
  }, [title, content, performSave]);

  // Handle autosave from TipTap editor
  const handleAutoSave = useCallback((markdown: string) => {
    setContentState(markdown);
    setIsDirty(title !== lastSavedTitleRef.current || markdown !== lastSavedContentRef.current);

    // Clear existing timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Schedule save
    saveTimeoutRef.current = setTimeout(() => {
      performSave(title, markdown);
    }, autoSaveDelay);
  }, [title, autoSaveDelay, performSave]);

  // Reset to last saved state
  const reset = useCallback(() => {
    setTitleState(lastSavedTitleRef.current);
    setContentState(lastSavedContentRef.current);
    setIsDirty(false);
    setSaveError(null);

    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  return {
    note,
    isLoading: isLoadingNote,
    isSaving: updateNote.isPending || createNote.isPending,
    isDirty,
    loadError: loadError as Error | null,
    saveError,
    title,
    content,
    setTitle,
    setContent,
    save,
    handleAutoSave,
    reset,
  };
}

export default useNoteEditor;
