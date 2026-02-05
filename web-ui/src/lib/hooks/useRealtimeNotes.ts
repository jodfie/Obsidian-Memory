'use client';

/**
 * React hooks that combine React Query data fetching with Supabase Realtime subscriptions.
 *
 * These hooks automatically subscribe to live updates and sync the React Query cache
 * with real-time changes from other clients/devices.
 */

import { useEffect, useCallback, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useNotes,
  useNote,
  noteKeys,
  type NotesListFilters,
  type NotesListResult,
} from './useNotes';
import { relationKeys } from './useRelations';
import {
  subscribeToNotes,
  subscribeToRelations,
  type ConnectionStatus,
  type NotesSubscriptionCallbacks,
  type RelationsSubscriptionCallbacks,
  type SubscriptionHandle,
} from '../supabase-realtime';
import type { Note, Relation } from '../supabase-client';

// ============================================================================
// Types
// ============================================================================

export interface UseRealtimeNotesOptions extends NotesListFilters {
  /** User ID for filtering subscriptions */
  userId?: string;
  /** Whether to enable realtime subscriptions (default: true) */
  enableRealtime?: boolean;
}

export interface UseRealtimeNotesResult {
  /** Notes data from React Query */
  notes: Note[];
  /** Total count of notes */
  total: number;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: Error | null;
  /** Whether the query is currently fetching */
  isFetching: boolean;
  /** Connection status for realtime */
  connectionStatus: ConnectionStatus;
  /** Refetch the notes manually */
  refetch: () => void;
}

export interface UseRealtimeNoteOptions {
  /** User ID for filtering subscriptions */
  userId?: string;
  /** Whether to enable realtime subscriptions (default: true) */
  enableRealtime?: boolean;
}

export interface UseRealtimeNoteResult {
  /** Single note data from React Query */
  note: Note | null | undefined;
  /** Loading state */
  isLoading: boolean;
  /** Error state */
  error: Error | null;
  /** Whether the query is currently fetching */
  isFetching: boolean;
  /** Connection status for realtime */
  connectionStatus: ConnectionStatus;
  /** Refetch the note manually */
  refetch: () => void;
}

// ============================================================================
// useRealtimeNotes Hook
// ============================================================================

/**
 * Combines useNotes() with Supabase Realtime subscriptions for live updates.
 *
 * This hook:
 * - Fetches notes using React Query (with caching and background refetch)
 * - Subscribes to Supabase Realtime for INSERT/UPDATE/DELETE events
 * - Automatically updates the React Query cache on realtime events
 * - Auto-subscribes on mount and unsubscribes on unmount
 *
 * @param options - Filtering options and realtime configuration
 * @returns Combined result with notes data and connection status
 *
 * @example
 * ```tsx
 * function NotesList() {
 *   const { notes, isLoading, connectionStatus } = useRealtimeNotes({
 *     userId: user.id,
 *     limit: 50,
 *   });
 *
 *   return (
 *     <div>
 *       <ConnectionStatus status={connectionStatus} />
 *       {isLoading ? (
 *         <Loading />
 *       ) : (
 *         <ul>
 *           {notes.map(note => (
 *             <NoteCard key={note.id} note={note} />
 *           ))}
 *         </ul>
 *       )}
 *     </div>
 *   );
 * }
 * ```
 */
export function useRealtimeNotes(options: UseRealtimeNotesOptions = {}): UseRealtimeNotesResult {
  const { userId, enableRealtime = true, ...filters } = options;
  const queryClient = useQueryClient();
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const subscriptionRef = useRef<SubscriptionHandle | null>(null);

  // Use the existing useNotes hook for data fetching
  const {
    data,
    isLoading,
    error,
    isFetching,
    refetch,
  } = useNotes(filters);

  // Memoized callback for handling note insertions
  const handleInsert = useCallback((newNote: Note) => {
    // Add the new note to the list cache
    queryClient.setQueryData<NotesListResult>(
      noteKeys.list(filters),
      (old) => {
        if (!old) return { notes: [newNote], total: 1 };

        // Check if note already exists (avoid duplicates)
        const exists = old.notes.some(n => n.id === newNote.id);
        if (exists) return old;

        return {
          notes: [newNote, ...old.notes],
          total: old.total + 1,
        };
      }
    );

    // Also set the individual note cache
    queryClient.setQueryData(noteKeys.detail(newNote.id), newNote);
  }, [queryClient, filters]);

  // Memoized callback for handling note updates
  const handleUpdate = useCallback((updatedNote: Note) => {
    // Update the note in all list caches
    queryClient.setQueriesData<NotesListResult>(
      { queryKey: noteKeys.lists() },
      (old) => {
        if (!old) return old;
        return {
          ...old,
          notes: old.notes.map(note =>
            note.id === updatedNote.id ? updatedNote : note
          ),
        };
      }
    );

    // Update the individual note cache
    queryClient.setQueryData(noteKeys.detail(updatedNote.id), updatedNote);
  }, [queryClient]);

  // Memoized callback for handling note deletions
  const handleDelete = useCallback((oldNote: Partial<Note>) => {
    if (!oldNote.id) return;

    const deletedId = oldNote.id;

    // Remove from all list caches
    queryClient.setQueriesData<NotesListResult>(
      { queryKey: noteKeys.lists() },
      (old) => {
        if (!old) return old;
        return {
          notes: old.notes.filter(note => note.id !== deletedId),
          total: Math.max(0, old.total - 1),
        };
      }
    );

    // Remove the individual note cache
    queryClient.removeQueries({ queryKey: noteKeys.detail(deletedId) });
  }, [queryClient]);

  // Set up realtime subscription
  useEffect(() => {
    // Don't subscribe if no userId or realtime is disabled
    if (!userId || !enableRealtime) {
      setConnectionStatus('disconnected');
      return;
    }

    // Create subscription
    const callbacks: NotesSubscriptionCallbacks = {
      onInsert: handleInsert,
      onUpdate: handleUpdate,
      onDelete: handleDelete,
      onStatusChange: setConnectionStatus,
    };

    subscriptionRef.current = subscribeToNotes(userId, callbacks);

    // Cleanup on unmount or when dependencies change
    return () => {
      if (subscriptionRef.current) {
        subscriptionRef.current.unsubscribe();
        subscriptionRef.current = null;
      }
    };
  }, [userId, enableRealtime, handleInsert, handleUpdate, handleDelete]);

  return {
    notes: data?.notes ?? [],
    total: data?.total ?? 0,
    isLoading,
    error: error as Error | null,
    isFetching,
    connectionStatus,
    refetch,
  };
}

// ============================================================================
// useRealtimeNote Hook
// ============================================================================

/**
 * Combines useNote() with Supabase Realtime subscriptions for a single note.
 *
 * This hook watches for changes to a specific note and updates the cache
 * when the note is modified or deleted elsewhere.
 *
 * @param noteId - The ID of the note to fetch and watch
 * @param options - Realtime configuration options
 * @returns Combined result with note data and connection status
 *
 * @example
 * ```tsx
 * function NoteEditor({ noteId }: { noteId: string }) {
 *   const { note, isLoading, connectionStatus } = useRealtimeNote(noteId, {
 *     userId: user.id,
 *   });
 *
 *   if (isLoading) return <Loading />;
 *   if (!note) return <NotFound />;
 *
 *   return (
 *     <div>
 *       <ConnectionStatus status={connectionStatus} />
 *       <Editor content={note.content} />
 *     </div>
 *   );
 * }
 * ```
 */
export function useRealtimeNote(
  noteId: string | null | undefined,
  options: UseRealtimeNoteOptions = {}
): UseRealtimeNoteResult {
  const { userId, enableRealtime = true } = options;
  const queryClient = useQueryClient();
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const subscriptionRef = useRef<SubscriptionHandle | null>(null);

  // Use the existing useNote hook for data fetching
  const {
    data: note,
    isLoading,
    error,
    isFetching,
    refetch,
  } = useNote(noteId);

  // Handle updates to this specific note
  const handleUpdate = useCallback((updatedNote: Note) => {
    if (updatedNote.id === noteId) {
      queryClient.setQueryData(noteKeys.detail(noteId), updatedNote);
    }
  }, [queryClient, noteId]);

  // Handle deletion of this specific note
  const handleDelete = useCallback((oldNote: Partial<Note>) => {
    if (oldNote.id === noteId) {
      queryClient.setQueryData(noteKeys.detail(noteId!), null);
    }
  }, [queryClient, noteId]);

  // Set up realtime subscription
  useEffect(() => {
    // Don't subscribe if no userId, no noteId, or realtime is disabled
    if (!userId || !noteId || !enableRealtime) {
      setConnectionStatus('disconnected');
      return;
    }

    // Create subscription (we still need all events for proper cache management)
    const callbacks: NotesSubscriptionCallbacks = {
      onUpdate: handleUpdate,
      onDelete: handleDelete,
      onStatusChange: setConnectionStatus,
    };

    subscriptionRef.current = subscribeToNotes(userId, callbacks);

    // Cleanup on unmount or when dependencies change
    return () => {
      if (subscriptionRef.current) {
        subscriptionRef.current.unsubscribe();
        subscriptionRef.current = null;
      }
    };
  }, [userId, noteId, enableRealtime, handleUpdate, handleDelete]);

  return {
    note,
    isLoading,
    error: error as Error | null,
    isFetching,
    connectionStatus,
    refetch,
  };
}

// ============================================================================
// useRealtimeRelations Hook
// ============================================================================

export interface UseRealtimeRelationsOptions {
  /** User ID for filtering subscriptions */
  userId?: string;
  /** Whether to enable realtime subscriptions (default: true) */
  enableRealtime?: boolean;
}

export interface UseRealtimeRelationsResult {
  /** Connection status for realtime */
  connectionStatus: ConnectionStatus;
  /** Manually trigger refetch of relations */
  invalidateRelations: () => void;
}

/**
 * Subscribes to Supabase Realtime for relations changes and invalidates caches.
 *
 * This hook doesn't return relations data directly - instead it works alongside
 * existing relation hooks (useBacklinks, useOutgoingLinks, useLocalGraph) by
 * invalidating their caches when changes occur.
 *
 * @param options - Realtime configuration options
 * @returns Connection status and invalidation function
 *
 * @example
 * ```tsx
 * function GraphView({ noteId }: { noteId: string }) {
 *   const { connectionStatus } = useRealtimeRelations({ userId: user.id });
 *   const { data: graph } = useLocalGraph(noteId);
 *
 *   return (
 *     <div>
 *       <ConnectionStatus status={connectionStatus} />
 *       <GraphVisualization data={graph} />
 *     </div>
 *   );
 * }
 * ```
 */
export function useRealtimeRelations(
  options: UseRealtimeRelationsOptions = {}
): UseRealtimeRelationsResult {
  const { userId, enableRealtime = true } = options;
  const queryClient = useQueryClient();
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const subscriptionRef = useRef<SubscriptionHandle | null>(null);

  // Invalidate all relation queries when any relation changes
  const invalidateRelations = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: relationKeys.all });
  }, [queryClient]);

  // Set up realtime subscription
  useEffect(() => {
    // Don't subscribe if no userId or realtime is disabled
    if (!userId || !enableRealtime) {
      setConnectionStatus('disconnected');
      return;
    }

    // Create subscription - invalidate caches on any change
    const callbacks: RelationsSubscriptionCallbacks = {
      onInsert: invalidateRelations,
      onUpdate: invalidateRelations,
      onDelete: invalidateRelations,
      onStatusChange: setConnectionStatus,
    };

    subscriptionRef.current = subscribeToRelations(userId, callbacks);

    // Cleanup on unmount or when dependencies change
    return () => {
      if (subscriptionRef.current) {
        subscriptionRef.current.unsubscribe();
        subscriptionRef.current = null;
      }
    };
  }, [userId, enableRealtime, invalidateRelations]);

  return {
    connectionStatus,
    invalidateRelations,
  };
}

// ============================================================================
// useConnectionStatus Hook
// ============================================================================

/**
 * Simple hook for monitoring Supabase Realtime connection status.
 *
 * Use this when you only need to show connection status without
 * subscribing to specific data changes.
 *
 * @param userId - User ID for the connection
 * @returns Current connection status
 *
 * @example
 * ```tsx
 * function Header() {
 *   const status = useConnectionStatus(user.id);
 *
 *   return (
 *     <header>
 *       <ConnectionIndicator status={status} />
 *     </header>
 *   );
 * }
 * ```
 */
export function useConnectionStatus(userId?: string): ConnectionStatus {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const subscriptionRef = useRef<SubscriptionHandle | null>(null);

  useEffect(() => {
    if (!userId) {
      setStatus('disconnected');
      return;
    }

    // Create a lightweight subscription just for status
    const callbacks: NotesSubscriptionCallbacks = {
      onStatusChange: setStatus,
    };

    subscriptionRef.current = subscribeToNotes(userId, callbacks);

    return () => {
      if (subscriptionRef.current) {
        subscriptionRef.current.unsubscribe();
        subscriptionRef.current = null;
      }
    };
  }, [userId]);

  return status;
}
