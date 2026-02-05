'use client';

/**
 * React Query hooks for note relations (backlinks and outgoing links).
 *
 * These hooks enable graph-like navigation between notes by querying
 * the relations table which tracks wikilinks, tags, and other connections.
 */

import { useQuery } from '@tanstack/react-query';
import {
  getSupabaseBrowserClient,
  type Note,
  type Relation,
} from '../supabase-client';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for relations.
 * Using a factory pattern ensures consistent keys across the app.
 */
export const relationKeys = {
  all: ['relations'] as const,
  backlinks: () => [...relationKeys.all, 'backlinks'] as const,
  backlinksFor: (noteId: string) => [...relationKeys.backlinks(), noteId] as const,
  outgoing: () => [...relationKeys.all, 'outgoing'] as const,
  outgoingFor: (noteId: string) => [...relationKeys.outgoing(), noteId] as const,
  graph: () => [...relationKeys.all, 'graph'] as const,
  graphFor: (noteId: string) => [...relationKeys.graph(), noteId] as const,
};

// ============================================================================
// Types
// ============================================================================

/**
 * A note with the relation context that links it.
 */
export interface LinkedNote {
  note: Note;
  relation: Relation;
}

/**
 * Result type for backlinks query.
 */
export interface BacklinksResult {
  /** Notes that link to the target note */
  notes: LinkedNote[];
  /** Total number of backlinks */
  total: number;
}

/**
 * Result type for outgoing links query.
 */
export interface OutgoingLinksResult {
  /** Notes that the source note links to */
  notes: LinkedNote[];
  /** Total number of outgoing links */
  total: number;
  /** Paths that don't have corresponding notes (broken links) */
  brokenLinks: string[];
}

/**
 * Result type for the local graph around a note.
 */
export interface LocalGraphResult {
  /** The center note */
  centerNote: Note;
  /** Notes linking to the center note */
  backlinks: LinkedNote[];
  /** Notes the center note links to */
  outgoingLinks: LinkedNote[];
  /** All unique notes in the graph (for rendering) */
  allNotes: Note[];
  /** All edges in the graph */
  edges: Array<{
    source: string;
    target: string;
    type: string;
    context?: string | null;
  }>;
}

// ============================================================================
// useBacklinks Hook
// ============================================================================

/**
 * Fetches notes that link to a specific note (backlinks).
 *
 * This enables bidirectional linking - you can see all notes
 * that reference the current note even if it doesn't link back.
 *
 * @param noteId - The ID of the note to find backlinks for
 * @param options - Optional configuration
 * @returns Query result with backlink notes and their relation context
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useBacklinks(note.id);
 *
 * if (isLoading) return <Loading />;
 *
 * return (
 *   <div>
 *     <h3>Linked from {data?.total} notes</h3>
 *     {data?.notes.map(({ note, relation }) => (
 *       <div key={note.id}>
 *         <Link href={`/notes/${note.id}`}>{note.title}</Link>
 *         {relation.context && <p>{relation.context}</p>}
 *       </div>
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useBacklinks(
  noteId: string | null | undefined,
  options?: { enabled?: boolean }
) {
  const supabase = getSupabaseBrowserClient();
  const { enabled = true } = options ?? {};

  return useQuery({
    queryKey: relationKeys.backlinksFor(noteId ?? ''),
    queryFn: async (): Promise<BacklinksResult> => {
      if (!noteId) {
        return { notes: [], total: 0 };
      }

      // First, get the target note to find its path
      const { data: targetNote, error: noteError } = await supabase
        .from('notes')
        .select('path')
        .eq('id', noteId)
        .single();

      if (noteError) {
        throw new Error(`Failed to fetch note: ${noteError.message}`);
      }

      // Find all relations where target_path matches this note's path
      const { data: relations, error: relError } = await supabase
        .from('relations')
        .select('*')
        .eq('target_path', targetNote.path);

      if (relError) {
        throw new Error(`Failed to fetch backlinks: ${relError.message}`);
      }

      if (!relations || relations.length === 0) {
        return { notes: [], total: 0 };
      }

      // Get the source notes for these relations
      const sourceIds = relations.map((r) => r.source_id);
      const { data: sourceNotes, error: sourcesError } = await supabase
        .from('notes')
        .select('*')
        .in('id', sourceIds);

      if (sourcesError) {
        throw new Error(`Failed to fetch source notes: ${sourcesError.message}`);
      }

      // Map relations to their source notes
      const linkedNotes: LinkedNote[] = relations
        .map((relation) => {
          const note = sourceNotes?.find((n) => n.id === relation.source_id);
          if (!note) return null;
          return { note, relation };
        })
        .filter((item): item is LinkedNote => item !== null);

      return {
        notes: linkedNotes,
        total: linkedNotes.length,
      };
    },
    enabled: enabled && !!noteId,
    staleTime: 60 * 1000, // 1 minute - relations don't change often
  });
}

// ============================================================================
// useOutgoingLinks Hook
// ============================================================================

/**
 * Fetches notes that a specific note links to (outgoing links).
 *
 * This shows what the current note references, including
 * detection of broken links (references to non-existent notes).
 *
 * @param noteId - The ID of the note to find outgoing links for
 * @param options - Optional configuration
 * @returns Query result with linked notes and broken link paths
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useOutgoingLinks(note.id);
 *
 * if (isLoading) return <Loading />;
 *
 * return (
 *   <div>
 *     <h3>Links to {data?.total} notes</h3>
 *     {data?.notes.map(({ note, relation }) => (
 *       <Link key={note.id} href={`/notes/${note.id}`}>
 *         {note.title}
 *       </Link>
 *     ))}
 *     {data?.brokenLinks.length > 0 && (
 *       <div>
 *         <h4>Broken links:</h4>
 *         {data.brokenLinks.map(path => (
 *           <span key={path}>{path}</span>
 *         ))}
 *       </div>
 *     )}
 *   </div>
 * );
 * ```
 */
export function useOutgoingLinks(
  noteId: string | null | undefined,
  options?: { enabled?: boolean }
) {
  const supabase = getSupabaseBrowserClient();
  const { enabled = true } = options ?? {};

  return useQuery({
    queryKey: relationKeys.outgoingFor(noteId ?? ''),
    queryFn: async (): Promise<OutgoingLinksResult> => {
      if (!noteId) {
        return { notes: [], total: 0, brokenLinks: [] };
      }

      // Find all relations where this note is the source
      const { data: relations, error: relError } = await supabase
        .from('relations')
        .select('*')
        .eq('source_id', noteId);

      if (relError) {
        throw new Error(`Failed to fetch outgoing links: ${relError.message}`);
      }

      if (!relations || relations.length === 0) {
        return { notes: [], total: 0, brokenLinks: [] };
      }

      // Get unique target paths
      const targetPaths = [...new Set(relations.map((r) => r.target_path))];

      // Find the target notes by their paths
      const { data: targetNotes, error: targetsError } = await supabase
        .from('notes')
        .select('*')
        .in('path', targetPaths);

      if (targetsError) {
        throw new Error(`Failed to fetch target notes: ${targetsError.message}`);
      }

      // Create a map of path -> note for quick lookup
      const notesByPath = new Map(targetNotes?.map((n) => [n.path, n]) ?? []);

      // Find broken links (paths without corresponding notes)
      const brokenLinks = targetPaths.filter((path) => !notesByPath.has(path));

      // Map relations to their target notes
      const linkedNotes: LinkedNote[] = relations
        .map((relation) => {
          const note = notesByPath.get(relation.target_path);
          if (!note) return null;
          return { note, relation };
        })
        .filter((item): item is LinkedNote => item !== null);

      // Deduplicate by note ID (a note might be linked multiple times)
      const uniqueNotes = linkedNotes.reduce<LinkedNote[]>((acc, current) => {
        const exists = acc.find((item) => item.note.id === current.note.id);
        if (!exists) {
          acc.push(current);
        }
        return acc;
      }, []);

      return {
        notes: uniqueNotes,
        total: uniqueNotes.length,
        brokenLinks,
      };
    },
    enabled: enabled && !!noteId,
    staleTime: 60 * 1000, // 1 minute - relations don't change often
  });
}

// ============================================================================
// useLocalGraph Hook
// ============================================================================

/**
 * Fetches the local graph around a specific note.
 *
 * This combines backlinks and outgoing links to create a mini-graph
 * centered on the specified note, useful for graph visualization.
 *
 * @param noteId - The ID of the center note
 * @param options - Optional configuration
 * @returns Query result with the local graph data
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useLocalGraph(note.id);
 *
 * if (isLoading) return <Loading />;
 *
 * return (
 *   <GraphVisualization
 *     nodes={data?.allNotes ?? []}
 *     edges={data?.edges ?? []}
 *     centerNodeId={note.id}
 *   />
 * );
 * ```
 */
export function useLocalGraph(
  noteId: string | null | undefined,
  options?: { enabled?: boolean }
) {
  const supabase = getSupabaseBrowserClient();
  const { enabled = true } = options ?? {};

  return useQuery({
    queryKey: relationKeys.graphFor(noteId ?? ''),
    queryFn: async (): Promise<LocalGraphResult | null> => {
      if (!noteId) {
        return null;
      }

      // Fetch the center note
      const { data: centerNote, error: centerError } = await supabase
        .from('notes')
        .select('*')
        .eq('id', noteId)
        .single();

      if (centerError) {
        throw new Error(`Failed to fetch center note: ${centerError.message}`);
      }

      // Fetch outgoing relations (from this note)
      const { data: outgoingRelations, error: outError } = await supabase
        .from('relations')
        .select('*')
        .eq('source_id', noteId);

      if (outError) {
        throw new Error(`Failed to fetch outgoing links: ${outError.message}`);
      }

      // Fetch backlink relations (to this note's path)
      const { data: backlinkRelations, error: backError } = await supabase
        .from('relations')
        .select('*')
        .eq('target_path', centerNote.path);

      if (backError) {
        throw new Error(`Failed to fetch backlinks: ${backError.message}`);
      }

      // Collect all note IDs and paths we need to fetch
      const sourceIds = backlinkRelations?.map((r) => r.source_id) ?? [];
      const targetPaths = outgoingRelations?.map((r) => r.target_path) ?? [];

      // Fetch source notes (for backlinks)
      let sourceNotes: Note[] = [];
      if (sourceIds.length > 0) {
        const { data, error } = await supabase
          .from('notes')
          .select('*')
          .in('id', sourceIds);
        if (error) {
          throw new Error(`Failed to fetch source notes: ${error.message}`);
        }
        sourceNotes = data ?? [];
      }

      // Fetch target notes (for outgoing links)
      let targetNotes: Note[] = [];
      if (targetPaths.length > 0) {
        const { data, error } = await supabase
          .from('notes')
          .select('*')
          .in('path', targetPaths);
        if (error) {
          throw new Error(`Failed to fetch target notes: ${error.message}`);
        }
        targetNotes = data ?? [];
      }

      // Create maps for quick lookup
      const sourceNotesById = new Map(sourceNotes.map((n) => [n.id, n]));
      const targetNotesByPath = new Map(targetNotes.map((n) => [n.path, n]));

      // Build backlinks list
      const backlinks: LinkedNote[] = (backlinkRelations ?? [])
        .map((relation) => {
          const note = sourceNotesById.get(relation.source_id);
          if (!note) return null;
          return { note, relation };
        })
        .filter((item): item is LinkedNote => item !== null);

      // Build outgoing links list
      const outgoingLinks: LinkedNote[] = (outgoingRelations ?? [])
        .map((relation) => {
          const note = targetNotesByPath.get(relation.target_path);
          if (!note) return null;
          return { note, relation };
        })
        .filter((item): item is LinkedNote => item !== null);

      // Collect all unique notes
      const allNotesMap = new Map<string, Note>();
      allNotesMap.set(centerNote.id, centerNote);
      sourceNotes.forEach((n) => allNotesMap.set(n.id, n));
      targetNotes.forEach((n) => allNotesMap.set(n.id, n));

      // Build edges
      const edges: LocalGraphResult['edges'] = [];

      // Backlink edges (other notes -> center)
      backlinkRelations?.forEach((relation) => {
        if (sourceNotesById.has(relation.source_id)) {
          edges.push({
            source: relation.source_id,
            target: centerNote.id,
            type: relation.relation_type,
            context: relation.context,
          });
        }
      });

      // Outgoing edges (center -> other notes)
      outgoingRelations?.forEach((relation) => {
        const targetNote = targetNotesByPath.get(relation.target_path);
        if (targetNote) {
          edges.push({
            source: centerNote.id,
            target: targetNote.id,
            type: relation.relation_type,
            context: relation.context,
          });
        }
      });

      return {
        centerNote,
        backlinks,
        outgoingLinks,
        allNotes: Array.from(allNotesMap.values()),
        edges,
      };
    },
    enabled: enabled && !!noteId,
    staleTime: 60 * 1000, // 1 minute
  });
}
