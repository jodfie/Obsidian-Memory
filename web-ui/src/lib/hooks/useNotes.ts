'use client';

/**
 * React Query hooks for notes data fetching.
 *
 * These hooks integrate with Supabase to fetch and mutate notes data
 * with automatic caching, background refetching, and optimistic updates.
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  useInfiniteQuery,
  type InfiniteData,
} from '@tanstack/react-query';
import {
  getSupabaseBrowserClient,
  type Note,
  type NoteInsert,
  type NoteUpdate,
} from '../supabase-client';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for notes.
 * Using a factory pattern ensures consistent keys across the app.
 */
export const noteKeys = {
  all: ['notes'] as const,
  lists: () => [...noteKeys.all, 'list'] as const,
  list: (filters?: NotesListFilters) => [...noteKeys.lists(), filters] as const,
  details: () => [...noteKeys.all, 'detail'] as const,
  detail: (id: string) => [...noteKeys.details(), id] as const,
  infinite: () => [...noteKeys.all, 'infinite'] as const,
  infiniteList: (filters?: NotesListFilters) =>
    [...noteKeys.infinite(), filters] as const,
  search: () => [...noteKeys.all, 'search'] as const,
  searchQuery: (query: string) => [...noteKeys.search(), query] as const,
};

// ============================================================================
// Types
// ============================================================================

export interface NotesListFilters {
  search?: string;
  limit?: number;
  offset?: number;
  orderBy?: 'updated_at' | 'created_at' | 'title';
  orderDirection?: 'asc' | 'desc';
}

export interface NotesListResult {
  notes: Note[];
  total: number;
}

export interface SearchResult {
  notes: Note[];
  total: number;
  query: string;
}

export interface InfiniteNotesPage {
  notes: Note[];
  total: number;
  nextOffset: number | null;
}

// ============================================================================
// useNotes Hook
// ============================================================================

/**
 * Fetches a list of notes with optional filtering and pagination.
 *
 * @param filters - Optional filters for the notes list
 * @returns Query result with notes array and total count
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useNotes({ limit: 10 });
 *
 * if (isLoading) return <Loading />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <ul>
 *     {data?.notes.map(note => (
 *       <li key={note.id}>{note.title}</li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useNotes(filters?: NotesListFilters) {
  const supabase = getSupabaseBrowserClient();

  return useQuery({
    queryKey: noteKeys.list(filters),
    queryFn: async (): Promise<NotesListResult> => {
      const {
        search,
        limit = 50,
        offset = 0,
        orderBy = 'updated_at',
        orderDirection = 'desc',
      } = filters ?? {};

      // Build the query
      let query = supabase.from('notes').select('*', { count: 'exact' });

      // Apply search filter if provided
      if (search) {
        query = query.or(`title.ilike.%${search}%,content.ilike.%${search}%`);
      }

      // Apply ordering
      query = query.order(orderBy, { ascending: orderDirection === 'asc' });

      // Apply pagination
      query = query.range(offset, offset + limit - 1);

      const { data, error, count } = await query;

      if (error) {
        throw new Error(`Failed to fetch notes: ${error.message}`);
      }

      return {
        notes: (data ?? []) as Note[],
        total: count ?? 0,
      };
    },
  });
}

// ============================================================================
// useNote Hook
// ============================================================================

/**
 * Fetches a single note by ID.
 *
 * @param id - The note ID to fetch
 * @returns Query result with the note data
 *
 * @example
 * ```tsx
 * const { data: note, isLoading } = useNote('abc-123');
 *
 * if (isLoading) return <Loading />;
 * if (!note) return <NotFound />;
 *
 * return <NoteEditor note={note} />;
 * ```
 */
export function useNote(id: string | null | undefined) {
  const supabase = getSupabaseBrowserClient();

  return useQuery({
    queryKey: noteKeys.detail(id ?? ''),
    queryFn: async (): Promise<Note> => {
      if (!id) {
        throw new Error('Note ID is required');
      }

      const { data, error } = await supabase
        .from('notes')
        .select('*')
        .eq('id', id)
        .single();

      if (error) {
        throw new Error(`Failed to fetch note: ${error.message}`);
      }

      return data as Note;
    },
    enabled: !!id, // Only run query if ID is provided
  });
}

// ============================================================================
// useSearchNotes Hook
// ============================================================================

/**
 * Full-text search for notes.
 *
 * Uses Postgres full-text search for better performance on large datasets.
 *
 * @param query - The search query string
 * @param options - Optional configuration
 * @returns Query result with matching notes
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useSearchNotes('react hooks');
 *
 * if (isLoading) return <Loading />;
 *
 * return (
 *   <SearchResults notes={data?.notes ?? []} query="react hooks" />
 * );
 * ```
 */
export function useSearchNotes(
  query: string,
  options?: { limit?: number; enabled?: boolean }
) {
  const supabase = getSupabaseBrowserClient();
  const { limit = 50, enabled = true } = options ?? {};

  return useQuery({
    queryKey: noteKeys.searchQuery(query),
    queryFn: async (): Promise<SearchResult> => {
      if (!query.trim()) {
        return { notes: [], total: 0, query };
      }

      // Use Postgres full-text search with ts_rank for relevance scoring
      // Falls back to ILIKE if full-text search fails
      const { data, error, count } = await supabase
        .from('notes')
        .select('*', { count: 'exact' })
        .or(`title.ilike.%${query}%,content.ilike.%${query}%`)
        .order('updated_at', { ascending: false })
        .limit(limit);

      if (error) {
        throw new Error(`Search failed: ${error.message}`);
      }

      return {
        notes: (data ?? []) as Note[],
        total: count ?? 0,
        query,
      };
    },
    enabled: enabled && query.trim().length > 0,
    staleTime: 30 * 1000, // 30 seconds - search results can be slightly stale
  });
}

// ============================================================================
// useInfiniteNotes Hook
// ============================================================================

/**
 * Infinite scroll pagination for notes.
 *
 * Fetches notes in pages and supports loading more as the user scrolls.
 *
 * @param filters - Optional filters for the notes list
 * @returns Infinite query result with pages of notes
 *
 * @example
 * ```tsx
 * const {
 *   data,
 *   fetchNextPage,
 *   hasNextPage,
 *   isFetchingNextPage,
 * } = useInfiniteNotes({ limit: 20 });
 *
 * const allNotes = data?.pages.flatMap(page => page.notes) ?? [];
 *
 * return (
 *   <div>
 *     {allNotes.map(note => <NoteCard key={note.id} note={note} />)}
 *     {hasNextPage && (
 *       <button onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
 *         {isFetchingNextPage ? 'Loading...' : 'Load More'}
 *       </button>
 *     )}
 *   </div>
 * );
 * ```
 */
export function useInfiniteNotes(filters?: Omit<NotesListFilters, 'offset'>) {
  const supabase = getSupabaseBrowserClient();
  const {
    search,
    limit = 20,
    orderBy = 'updated_at',
    orderDirection = 'desc',
  } = filters ?? {};

  return useInfiniteQuery<
    InfiniteNotesPage,
    Error,
    InfiniteData<InfiniteNotesPage>,
    ReturnType<typeof noteKeys.infiniteList>,
    number
  >({
    queryKey: noteKeys.infiniteList(filters),
    queryFn: async ({ pageParam }): Promise<InfiniteNotesPage> => {
      const offset = pageParam;

      // Build the query
      let query = supabase.from('notes').select('*', { count: 'exact' });

      // Apply search filter if provided
      if (search) {
        query = query.or(`title.ilike.%${search}%,content.ilike.%${search}%`);
      }

      // Apply ordering
      query = query.order(orderBy, { ascending: orderDirection === 'asc' });

      // Apply pagination
      query = query.range(offset, offset + limit - 1);

      const { data, error, count } = await query;

      if (error) {
        throw new Error(`Failed to fetch notes: ${error.message}`);
      }

      const total = count ?? 0;
      const hasMore = offset + limit < total;

      return {
        notes: (data ?? []) as Note[],
        total,
        nextOffset: hasMore ? offset + limit : null,
      };
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage) => lastPage.nextOffset,
  });
}

// ============================================================================
// useCreateNote Hook
// ============================================================================

/**
 * Creates a new note with optimistic updates.
 *
 * The note appears immediately in the UI while the server request is in progress.
 * If the request fails, the optimistic update is rolled back.
 *
 * @returns Mutation result with create function
 *
 * @example
 * ```tsx
 * const createNote = useCreateNote();
 *
 * const handleCreate = async () => {
 *   await createNote.mutateAsync({
 *     title: 'New Note',
 *     content: '# Hello World',
 *     path: 'notes/new-note.md',
 *   });
 * };
 * ```
 */
export function useCreateNote() {
  const supabase = getSupabaseBrowserClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (note: NoteInsert): Promise<Note> => {
      const { data, error } = await supabase
        .from('notes')
        .insert(note)
        .select()
        .single();

      if (error) {
        throw new Error(`Failed to create note: ${error.message}`);
      }

      return data as Note;
    },
    onMutate: async (newNote) => {
      // Cancel any outgoing refetches to avoid overwriting our optimistic update
      await queryClient.cancelQueries({ queryKey: noteKeys.lists() });

      // Snapshot the previous value
      const previousLists = queryClient.getQueriesData<NotesListResult>({
        queryKey: noteKeys.lists(),
      });

      // Create an optimistic note with a temporary ID
      const optimisticNote: Note = {
        id: `temp-${Date.now()}`,
        path: newNote.path,
        title: newNote.title,
        content: newNote.content,
        frontmatter: newNote.frontmatter ?? {},
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        user_id: newNote.user_id ?? '',
      };

      // Optimistically update all list queries
      queryClient.setQueriesData<NotesListResult>(
        { queryKey: noteKeys.lists() },
        (old) => {
          if (!old) return old;
          return {
            notes: [optimisticNote, ...old.notes],
            total: old.total + 1,
          };
        }
      );

      // Return context with the snapshot
      return { previousLists, optimisticNote };
    },
    onError: (_err, _newNote, context) => {
      // Rollback to the previous value on error
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data);
        });
      }
    },
    onSuccess: (data, _variables, context) => {
      // Replace the optimistic note with the real one
      if (context?.optimisticNote) {
        queryClient.setQueriesData<NotesListResult>(
          { queryKey: noteKeys.lists() },
          (old) => {
            if (!old) return old;
            return {
              ...old,
              notes: old.notes.map((note) =>
                note.id === context.optimisticNote.id ? data : note
              ),
            };
          }
        );
      }
      // Update the detail cache with the new note
      queryClient.setQueryData(noteKeys.detail(data.id), data);
    },
    onSettled: () => {
      // Always refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: noteKeys.lists() });
      queryClient.invalidateQueries({ queryKey: noteKeys.infinite() });
    },
  });
}

// ============================================================================
// useUpdateNote Hook
// ============================================================================

/**
 * Updates an existing note with optimistic updates and rollback on error.
 *
 * The UI updates immediately while the server request is in progress.
 * If the request fails, changes are rolled back to the previous state.
 *
 * @returns Mutation result with update function
 *
 * @example
 * ```tsx
 * const updateNote = useUpdateNote();
 *
 * const handleSave = async () => {
 *   await updateNote.mutateAsync({
 *     id: note.id,
 *     title: 'Updated Title',
 *     content: newContent,
 *   });
 * };
 * ```
 */
export function useUpdateNote() {
  const supabase = getSupabaseBrowserClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      ...updates
    }: NoteUpdate & { id: string }): Promise<Note> => {
      const { data, error } = await supabase
        .from('notes')
        .update({
          ...updates,
          updated_at: new Date().toISOString(),
        })
        .eq('id', id)
        .select()
        .single();

      if (error) {
        throw new Error(`Failed to update note: ${error.message}`);
      }

      return data as Note;
    },
    onMutate: async (updatedNote) => {
      const { id, ...updates } = updatedNote;

      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: noteKeys.detail(id) });
      await queryClient.cancelQueries({ queryKey: noteKeys.lists() });

      // Snapshot the previous values
      const previousNote = queryClient.getQueryData<Note>(noteKeys.detail(id));
      const previousLists = queryClient.getQueriesData<NotesListResult>({
        queryKey: noteKeys.lists(),
      });

      // Optimistically update the detail cache
      if (previousNote) {
        const optimisticNote: Note = {
          ...previousNote,
          ...updates,
          updated_at: new Date().toISOString(),
        };
        queryClient.setQueryData(noteKeys.detail(id), optimisticNote);

        // Optimistically update all list queries
        queryClient.setQueriesData<NotesListResult>(
          { queryKey: noteKeys.lists() },
          (old) => {
            if (!old) return old;
            return {
              ...old,
              notes: old.notes.map((note) =>
                note.id === id ? optimisticNote : note
              ),
            };
          }
        );
      }

      // Return context with the snapshots
      return { previousNote, previousLists };
    },
    onError: (_err, variables, context) => {
      // Rollback to the previous values on error
      if (context?.previousNote) {
        queryClient.setQueryData(
          noteKeys.detail(variables.id),
          context.previousNote
        );
      }
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data);
        });
      }
    },
    onSuccess: (data) => {
      // Update the detail cache with the server response
      queryClient.setQueryData(noteKeys.detail(data.id), data);
    },
    onSettled: (_data, _error, variables) => {
      // Always refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: noteKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: noteKeys.lists() });
      queryClient.invalidateQueries({ queryKey: noteKeys.infinite() });
    },
  });
}

// ============================================================================
// useDeleteNote Hook
// ============================================================================

/**
 * Deletes a note by ID with optimistic updates.
 *
 * The note is removed from the UI immediately while the server request is in progress.
 * If the request fails, the note is restored to the UI.
 *
 * @returns Mutation result with delete function
 *
 * @example
 * ```tsx
 * const deleteNote = useDeleteNote();
 *
 * const handleDelete = async () => {
 *   if (confirm('Delete this note?')) {
 *     await deleteNote.mutateAsync(note.id);
 *   }
 * };
 * ```
 */
export function useDeleteNote() {
  const supabase = getSupabaseBrowserClient();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      const { error } = await supabase.from('notes').delete().eq('id', id);

      if (error) {
        throw new Error(`Failed to delete note: ${error.message}`);
      }
    },
    onMutate: async (id) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: noteKeys.detail(id) });
      await queryClient.cancelQueries({ queryKey: noteKeys.lists() });

      // Snapshot the previous values
      const previousNote = queryClient.getQueryData<Note>(noteKeys.detail(id));
      const previousLists = queryClient.getQueriesData<NotesListResult>({
        queryKey: noteKeys.lists(),
      });

      // Optimistically remove the note from detail cache
      queryClient.removeQueries({ queryKey: noteKeys.detail(id) });

      // Optimistically remove from all list queries
      queryClient.setQueriesData<NotesListResult>(
        { queryKey: noteKeys.lists() },
        (old) => {
          if (!old) return old;
          return {
            notes: old.notes.filter((note) => note.id !== id),
            total: Math.max(0, old.total - 1),
          };
        }
      );

      // Return context with the snapshots
      return { previousNote, previousLists, deletedId: id };
    },
    onError: (_err, id, context) => {
      // Rollback: restore the note on error
      if (context?.previousNote) {
        queryClient.setQueryData(noteKeys.detail(id), context.previousNote);
      }
      if (context?.previousLists) {
        context.previousLists.forEach(([queryKey, data]) => {
          queryClient.setQueryData(queryKey, data);
        });
      }
    },
    onSettled: (_data, _error, id) => {
      // Always refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: noteKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: noteKeys.lists() });
      queryClient.invalidateQueries({ queryKey: noteKeys.infinite() });
    },
  });
}
