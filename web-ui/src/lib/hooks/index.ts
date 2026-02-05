/**
 * React Query hooks for Obsidian-Memory.
 *
 * This module exports all data fetching hooks for notes, relations, and sessions.
 */

// Notes hooks
export {
  useNotes,
  useNote,
  useSearchNotes,
  useInfiniteNotes,
  useCreateNote,
  useUpdateNote,
  useDeleteNote,
  noteKeys,
  type NotesListFilters,
  type NotesListResult,
  type SearchResult,
  type InfiniteNotesPage,
} from './useNotes';

// Relations hooks
export {
  useBacklinks,
  useOutgoingLinks,
  useLocalGraph,
  relationKeys,
  type LinkedNote,
  type BacklinksResult,
  type OutgoingLinksResult,
  type LocalGraphResult,
} from './useRelations';

// Sessions hooks
export {
  useSessions,
  useRecentSessions,
  useSession,
  useSessionsByProject,
  useProjectNames,
  sessionKeys,
  type SessionsListFilters,
  type SessionsListResult,
  type SessionEvent,
  type SessionWithEvents,
} from './useSessions';

// Note editor hook (TipTap integration)
export { useNoteEditor } from './useNoteEditor';

// Realtime hooks
export {
  useRealtimeNotes,
  useRealtimeNote,
  useRealtimeRelations,
  useConnectionStatus,
  type UseRealtimeNotesOptions,
  type UseRealtimeNotesResult,
  type UseRealtimeNoteOptions,
  type UseRealtimeNoteResult,
  type UseRealtimeRelationsOptions,
  type UseRealtimeRelationsResult,
} from './useRealtimeNotes';
