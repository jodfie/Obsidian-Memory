'use client';

/**
 * Supabase Realtime subscriptions for live updates.
 *
 * Provides functions to subscribe to postgres_changes events on
 * notes and relations tables for real-time synchronization.
 */

import { RealtimeChannel, RealtimePostgresChangesPayload } from '@supabase/supabase-js';
import { getSupabaseBrowserClient, type Note, type Relation, type Database } from './supabase-client';

// ============================================================================
// Types
// ============================================================================

/**
 * Connection status for realtime subscriptions.
 */
export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'error';

/**
 * Callback type for note changes.
 */
export type NoteChangeCallback = (payload: RealtimePostgresChangesPayload<Note>) => void;

/**
 * Callback type for relation changes.
 */
export type RelationChangeCallback = (payload: RealtimePostgresChangesPayload<Relation>) => void;

/**
 * Callbacks for notes subscription events.
 */
export interface NotesSubscriptionCallbacks {
  onInsert?: (note: Note) => void;
  onUpdate?: (note: Note, oldNote: Partial<Note>) => void;
  onDelete?: (oldNote: Partial<Note>) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
}

/**
 * Callbacks for relations subscription events.
 */
export interface RelationsSubscriptionCallbacks {
  onInsert?: (relation: Relation) => void;
  onUpdate?: (relation: Relation, oldRelation: Partial<Relation>) => void;
  onDelete?: (oldRelation: Partial<Relation>) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
}

/**
 * Return type for subscription functions.
 */
export interface SubscriptionHandle {
  /** Unsubscribe and clean up the channel */
  unsubscribe: () => Promise<void>;
  /** Get current connection status */
  getStatus: () => ConnectionStatus;
  /** The underlying Supabase channel */
  channel: RealtimeChannel;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Maps Supabase channel state to our ConnectionStatus type.
 */
function mapChannelStatus(state: string): ConnectionStatus {
  switch (state) {
    case 'SUBSCRIBED':
      return 'connected';
    case 'CHANNEL_ERROR':
      return 'error';
    case 'TIMED_OUT':
      return 'disconnected';
    case 'CLOSED':
      return 'disconnected';
    default:
      return 'connecting';
  }
}

// ============================================================================
// Notes Subscription
// ============================================================================

/**
 * Subscribes to real-time changes on the notes table for a specific user.
 *
 * @param userId - The user ID to filter notes by
 * @param callbacks - Object containing callback functions for different events
 * @returns SubscriptionHandle with unsubscribe function and status getter
 *
 * @example
 * ```tsx
 * const { unsubscribe } = subscribeToNotes(user.id, {
 *   onInsert: (note) => {
 *     console.log('New note:', note.title);
 *     queryClient.setQueryData(['notes'], (old) => [...old, note]);
 *   },
 *   onUpdate: (note, oldNote) => {
 *     console.log('Updated note:', note.title);
 *     queryClient.setQueryData(['notes', note.id], note);
 *   },
 *   onDelete: (oldNote) => {
 *     console.log('Deleted note:', oldNote.id);
 *     queryClient.invalidateQueries(['notes']);
 *   },
 *   onStatusChange: (status) => {
 *     console.log('Connection status:', status);
 *   },
 * });
 *
 * // Later: cleanup
 * await unsubscribe();
 * ```
 */
export function subscribeToNotes(
  userId: string,
  callbacks: NotesSubscriptionCallbacks
): SubscriptionHandle {
  const supabase = getSupabaseBrowserClient();
  let currentStatus: ConnectionStatus = 'connecting';

  const channel = supabase
    .channel(`notes-changes-${userId}`)
    .on<Note>(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'notes',
        filter: `user_id=eq.${userId}`,
      },
      (payload) => {
        if (callbacks.onInsert && payload.new) {
          callbacks.onInsert(payload.new as Note);
        }
      }
    )
    .on<Note>(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public',
        table: 'notes',
        filter: `user_id=eq.${userId}`,
      },
      (payload) => {
        if (callbacks.onUpdate && payload.new) {
          callbacks.onUpdate(payload.new as Note, payload.old as Partial<Note>);
        }
      }
    )
    .on<Note>(
      'postgres_changes',
      {
        event: 'DELETE',
        schema: 'public',
        table: 'notes',
        filter: `user_id=eq.${userId}`,
      },
      (payload) => {
        if (callbacks.onDelete && payload.old) {
          callbacks.onDelete(payload.old as Partial<Note>);
        }
      }
    )
    .subscribe((status) => {
      currentStatus = mapChannelStatus(status);
      if (callbacks.onStatusChange) {
        callbacks.onStatusChange(currentStatus);
      }
    });

  return {
    unsubscribe: async () => {
      await supabase.removeChannel(channel);
    },
    getStatus: () => currentStatus,
    channel,
  };
}

/**
 * Overload for subscribeToNotes with individual callback parameters.
 * This signature matches the task specification.
 *
 * @param userId - The user ID to filter notes by
 * @param onInsert - Callback for INSERT events
 * @param onUpdate - Callback for UPDATE events
 * @param onDelete - Callback for DELETE events
 * @returns Unsubscribe function
 */
export function subscribeToNotesSimple(
  userId: string,
  onInsert?: (note: Note) => void,
  onUpdate?: (note: Note) => void,
  onDelete?: (oldNote: Partial<Note>) => void
): () => Promise<void> {
  const handle = subscribeToNotes(userId, {
    onInsert,
    onUpdate: onUpdate ? (note) => onUpdate(note) : undefined,
    onDelete,
  });

  return handle.unsubscribe;
}

// ============================================================================
// Relations Subscription
// ============================================================================

/**
 * Subscribes to real-time changes on the relations table.
 *
 * Note: Relations don't have a direct user_id, so we subscribe to all changes
 * and filter client-side based on the user's notes. For better performance
 * in production, consider adding a user_id column to relations.
 *
 * @param userId - The user ID (used for channel naming, future filtering)
 * @param callbacks - Object containing callback functions for different events
 * @returns SubscriptionHandle with unsubscribe function and status getter
 *
 * @example
 * ```tsx
 * const { unsubscribe } = subscribeToRelations(user.id, {
 *   onInsert: (relation) => {
 *     queryClient.invalidateQueries(['relations']);
 *   },
 *   onUpdate: (relation) => {
 *     queryClient.invalidateQueries(['relations']);
 *   },
 *   onDelete: (oldRelation) => {
 *     queryClient.invalidateQueries(['relations']);
 *   },
 * });
 * ```
 */
export function subscribeToRelations(
  userId: string,
  callbacks: RelationsSubscriptionCallbacks
): SubscriptionHandle {
  const supabase = getSupabaseBrowserClient();
  let currentStatus: ConnectionStatus = 'connecting';

  const channel = supabase
    .channel(`relations-changes-${userId}`)
    .on<Relation>(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'relations',
      },
      (payload) => {
        if (callbacks.onInsert && payload.new) {
          callbacks.onInsert(payload.new as Relation);
        }
      }
    )
    .on<Relation>(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public',
        table: 'relations',
      },
      (payload) => {
        if (callbacks.onUpdate && payload.new) {
          callbacks.onUpdate(payload.new as Relation, payload.old as Partial<Relation>);
        }
      }
    )
    .on<Relation>(
      'postgres_changes',
      {
        event: 'DELETE',
        schema: 'public',
        table: 'relations',
      },
      (payload) => {
        if (callbacks.onDelete && payload.old) {
          callbacks.onDelete(payload.old as Partial<Relation>);
        }
      }
    )
    .subscribe((status) => {
      currentStatus = mapChannelStatus(status);
      if (callbacks.onStatusChange) {
        callbacks.onStatusChange(currentStatus);
      }
    });

  return {
    unsubscribe: async () => {
      await supabase.removeChannel(channel);
    },
    getStatus: () => currentStatus,
    channel,
  };
}

// ============================================================================
// Combined Subscription
// ============================================================================

/**
 * Subscribes to both notes and relations changes.
 *
 * This is a convenience function that combines both subscriptions
 * and returns a single unsubscribe function.
 *
 * @param userId - The user ID to filter by
 * @param notesCallbacks - Callbacks for notes changes
 * @param relationsCallbacks - Callbacks for relations changes
 * @returns Combined unsubscribe function
 */
export function subscribeToAll(
  userId: string,
  notesCallbacks: NotesSubscriptionCallbacks,
  relationsCallbacks: RelationsSubscriptionCallbacks
): {
  unsubscribe: () => Promise<void>;
  getNotesStatus: () => ConnectionStatus;
  getRelationsStatus: () => ConnectionStatus;
} {
  const notesHandle = subscribeToNotes(userId, notesCallbacks);
  const relationsHandle = subscribeToRelations(userId, relationsCallbacks);

  return {
    unsubscribe: async () => {
      await Promise.all([
        notesHandle.unsubscribe(),
        relationsHandle.unsubscribe(),
      ]);
    },
    getNotesStatus: notesHandle.getStatus,
    getRelationsStatus: relationsHandle.getStatus,
  };
}

// ============================================================================
// Utility: Connection Status Hook Helper
// ============================================================================

/**
 * Creates a channel for monitoring connection status only.
 *
 * Useful for displaying a global connection indicator without
 * subscribing to specific table changes.
 *
 * @param onStatusChange - Callback for status changes
 * @returns SubscriptionHandle
 */
export function createStatusChannel(
  onStatusChange: (status: ConnectionStatus) => void
): SubscriptionHandle {
  const supabase = getSupabaseBrowserClient();
  let currentStatus: ConnectionStatus = 'connecting';

  const channel = supabase
    .channel('connection-status')
    .subscribe((status) => {
      currentStatus = mapChannelStatus(status);
      onStatusChange(currentStatus);
    });

  return {
    unsubscribe: async () => {
      await supabase.removeChannel(channel);
    },
    getStatus: () => currentStatus,
    channel,
  };
}
