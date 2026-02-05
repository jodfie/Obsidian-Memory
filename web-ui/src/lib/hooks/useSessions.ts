'use client';

/**
 * React Query hooks for Claude Code session data.
 *
 * These hooks enable fetching and displaying Claude Code interaction
 * sessions, which track projects, events, and summaries.
 */

import { useQuery } from '@tanstack/react-query';
import { getSupabaseBrowserClient, type Session } from '../supabase-client';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for sessions.
 * Using a factory pattern ensures consistent keys across the app.
 */
export const sessionKeys = {
  all: ['sessions'] as const,
  lists: () => [...sessionKeys.all, 'list'] as const,
  list: (filters?: SessionsListFilters) =>
    [...sessionKeys.lists(), filters] as const,
  details: () => [...sessionKeys.all, 'detail'] as const,
  detail: (id: string) => [...sessionKeys.details(), id] as const,
  recent: () => [...sessionKeys.all, 'recent'] as const,
  recentList: (limit?: number) => [...sessionKeys.recent(), limit] as const,
};

// ============================================================================
// Types
// ============================================================================

export interface SessionsListFilters {
  /** Filter by project name */
  project?: string;
  /** Maximum number of sessions to return */
  limit?: number;
  /** Offset for pagination */
  offset?: number;
  /** Order by field */
  orderBy?: 'started_at' | 'ended_at';
  /** Order direction */
  orderDirection?: 'asc' | 'desc';
  /** Only include sessions within the last N days */
  daysAgo?: number;
}

export interface SessionsListResult {
  sessions: Session[];
  total: number;
}

/**
 * Parsed event from a session.
 * Events are stored as JSONB and can have various types.
 */
export interface SessionEvent {
  timestamp: string;
  type: string;
  data?: Record<string, unknown>;
}

/**
 * Session with parsed events.
 */
export interface SessionWithEvents extends Session {
  parsedEvents: SessionEvent[];
}

// ============================================================================
// useSessions Hook
// ============================================================================

/**
 * Fetches a list of sessions with optional filtering and pagination.
 *
 * @param filters - Optional filters for the sessions list
 * @returns Query result with sessions array and total count
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useSessions({ project: 'obsidian-memory' });
 *
 * if (isLoading) return <Loading />;
 *
 * return (
 *   <ul>
 *     {data?.sessions.map(session => (
 *       <li key={session.id}>
 *         {session.project} - {session.summary}
 *       </li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useSessions(filters?: SessionsListFilters) {
  const supabase = getSupabaseBrowserClient();

  return useQuery({
    queryKey: sessionKeys.list(filters),
    queryFn: async (): Promise<SessionsListResult> => {
      const {
        project,
        limit = 50,
        offset = 0,
        orderBy = 'started_at',
        orderDirection = 'desc',
        daysAgo,
      } = filters ?? {};

      // Build the query
      let query = supabase.from('sessions').select('*', { count: 'exact' });

      // Apply project filter if provided
      if (project) {
        query = query.eq('project', project);
      }

      // Apply date filter if provided
      if (daysAgo !== undefined) {
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - daysAgo);
        query = query.gte('started_at', cutoffDate.toISOString());
      }

      // Apply ordering
      query = query.order(orderBy, { ascending: orderDirection === 'asc' });

      // Apply pagination
      query = query.range(offset, offset + limit - 1);

      const { data, error, count } = await query;

      if (error) {
        throw new Error(`Failed to fetch sessions: ${error.message}`);
      }

      return {
        sessions: data ?? [],
        total: count ?? 0,
      };
    },
  });
}

// ============================================================================
// useRecentSessions Hook
// ============================================================================

/**
 * Fetches the most recent sessions (last 30 days by default).
 *
 * Convenience wrapper around useSessions for the common case
 * of showing recent activity.
 *
 * @param limit - Maximum number of sessions to return (default: 10)
 * @returns Query result with recent sessions
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useRecentSessions(5);
 *
 * if (isLoading) return <Loading />;
 *
 * return (
 *   <div>
 *     <h3>Recent Sessions</h3>
 *     {data?.sessions.map(session => (
 *       <SessionCard key={session.id} session={session} />
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useRecentSessions(limit: number = 10) {
  const supabase = getSupabaseBrowserClient();

  return useQuery({
    queryKey: sessionKeys.recentList(limit),
    queryFn: async (): Promise<SessionsListResult> => {
      // Calculate date 30 days ago
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - 30);

      const { data, error, count } = await supabase
        .from('sessions')
        .select('*', { count: 'exact' })
        .gte('started_at', cutoffDate.toISOString())
        .order('started_at', { ascending: false })
        .limit(limit);

      if (error) {
        throw new Error(`Failed to fetch recent sessions: ${error.message}`);
      }

      return {
        sessions: data ?? [],
        total: count ?? 0,
      };
    },
    staleTime: 60 * 1000, // 1 minute - recent sessions don't change often
  });
}

// ============================================================================
// useSession Hook
// ============================================================================

/**
 * Fetches a single session by ID with parsed events.
 *
 * @param id - The session ID to fetch
 * @returns Query result with the session data and parsed events
 *
 * @example
 * ```tsx
 * const { data: session, isLoading } = useSession('abc-123');
 *
 * if (isLoading) return <Loading />;
 * if (!session) return <NotFound />;
 *
 * return (
 *   <div>
 *     <h2>{session.project}</h2>
 *     <p>{session.summary}</p>
 *     <h3>Events</h3>
 *     {session.parsedEvents.map((event, i) => (
 *       <EventCard key={i} event={event} />
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useSession(id: string | null | undefined) {
  const supabase = getSupabaseBrowserClient();

  return useQuery({
    queryKey: sessionKeys.detail(id ?? ''),
    queryFn: async (): Promise<SessionWithEvents> => {
      if (!id) {
        throw new Error('Session ID is required');
      }

      const { data, error } = await supabase
        .from('sessions')
        .select('*')
        .eq('id', id)
        .single();

      if (error) {
        throw new Error(`Failed to fetch session: ${error.message}`);
      }

      // Parse the events array
      const parsedEvents: SessionEvent[] = Array.isArray(data.events)
        ? data.events.map((event: unknown) => {
            if (typeof event === 'object' && event !== null) {
              const e = event as Record<string, unknown>;
              return {
                timestamp: String(e.timestamp ?? ''),
                type: String(e.type ?? 'unknown'),
                data: typeof e.data === 'object' ? (e.data as Record<string, unknown>) : undefined,
              };
            }
            return {
              timestamp: '',
              type: 'unknown',
            };
          })
        : [];

      return {
        ...data,
        parsedEvents,
      };
    },
    enabled: !!id, // Only run query if ID is provided
  });
}

// ============================================================================
// useSessionsByProject Hook
// ============================================================================

/**
 * Fetches sessions grouped by project.
 *
 * Useful for displaying a project-centric view of session history.
 *
 * @param options - Optional configuration
 * @returns Query result with sessions grouped by project
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useSessionsByProject();
 *
 * if (isLoading) return <Loading />;
 *
 * return (
 *   <div>
 *     {Object.entries(data ?? {}).map(([project, sessions]) => (
 *       <div key={project}>
 *         <h3>{project}</h3>
 *         {sessions.map(session => (
 *           <SessionCard key={session.id} session={session} />
 *         ))}
 *       </div>
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useSessionsByProject(options?: {
  daysAgo?: number;
  enabled?: boolean;
}) {
  const supabase = getSupabaseBrowserClient();
  const { daysAgo = 30, enabled = true } = options ?? {};

  return useQuery({
    queryKey: [...sessionKeys.lists(), 'byProject', daysAgo] as const,
    queryFn: async (): Promise<Record<string, Session[]>> => {
      // Calculate cutoff date
      const cutoffDate = new Date();
      cutoffDate.setDate(cutoffDate.getDate() - daysAgo);

      const { data, error } = await supabase
        .from('sessions')
        .select('*')
        .gte('started_at', cutoffDate.toISOString())
        .order('started_at', { ascending: false });

      if (error) {
        throw new Error(`Failed to fetch sessions: ${error.message}`);
      }

      // Group sessions by project
      const grouped: Record<string, Session[]> = {};
      for (const session of data ?? []) {
        const project = session.project ?? 'Unknown';
        if (!grouped[project]) {
          grouped[project] = [];
        }
        grouped[project].push(session);
      }

      return grouped;
    },
    enabled,
    staleTime: 60 * 1000, // 1 minute
  });
}

// ============================================================================
// useProjectNames Hook
// ============================================================================

/**
 * Fetches unique project names from sessions.
 *
 * Useful for building project filter dropdowns.
 *
 * @returns Query result with unique project names
 *
 * @example
 * ```tsx
 * const { data: projects } = useProjectNames();
 *
 * return (
 *   <select>
 *     <option value="">All Projects</option>
 *     {projects?.map(project => (
 *       <option key={project} value={project}>{project}</option>
 *     ))}
 *   </select>
 * );
 * ```
 */
export function useProjectNames() {
  const supabase = getSupabaseBrowserClient();

  return useQuery({
    queryKey: [...sessionKeys.all, 'projectNames'] as const,
    queryFn: async (): Promise<string[]> => {
      const { data, error } = await supabase
        .from('sessions')
        .select('project')
        .not('project', 'is', null);

      if (error) {
        throw new Error(`Failed to fetch project names: ${error.message}`);
      }

      // Extract unique project names
      const projectSet = new Set<string>();
      for (const row of data ?? []) {
        if (row.project) {
          projectSet.add(row.project);
        }
      }

      return Array.from(projectSet).sort();
    },
    staleTime: 5 * 60 * 1000, // 5 minutes - project names rarely change
  });
}
