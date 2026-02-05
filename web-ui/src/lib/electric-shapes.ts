/**
 * ElectricSQL Shape Definitions for Obsidian-Memory.
 *
 * Shapes define what data syncs to each client. Each shape represents
 * a filtered view of a database table that ElectricSQL will keep in sync.
 *
 * @see https://electric-sql.com/docs/api/clients/typescript#shapestream
 */

import { ShapeStream, type Row } from '@electric-sql/client';

// ============================================================================
// Configuration
// ============================================================================

/**
 * Electric sync service URL from environment.
 * This should point to your Electric sync service instance.
 */
const ELECTRIC_URL = process.env.NEXT_PUBLIC_ELECTRIC_URL || 'http://localhost:3000';

/**
 * Base URL for shape API endpoints.
 */
const SHAPE_API_URL = `${ELECTRIC_URL}/v1/shape`;

// ============================================================================
// Shape Types
// ============================================================================

/**
 * Note record as returned from ElectricSQL sync.
 */
export interface ElectricNote {
  id: string;
  path: string;
  title: string;
  content: string;
  frontmatter: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  user_id: string;
}

/**
 * Relation record as returned from ElectricSQL sync.
 */
export interface ElectricRelation {
  id: string;
  source_id: string;
  target_path: string;
  relation_type: string;
  context: string | null;
}

/**
 * Session record as returned from ElectricSQL sync.
 */
export interface ElectricSession {
  id: string;
  project: string | null;
  started_at: string;
  ended_at: string | null;
  summary: string | null;
  events: unknown[];
}

// ============================================================================
// Shape Factory Functions
// ============================================================================

/**
 * Creates a shape stream for syncing notes belonging to a specific user.
 *
 * This shape filters notes by user_id, ensuring each client only syncs
 * their own notes. Row-level security (RLS) in Postgres provides additional
 * server-side filtering.
 *
 * @param userId - The UUID of the user whose notes to sync
 * @param options - Additional ShapeStream options
 * @returns A ShapeStream instance for the user's notes
 *
 * @example
 * ```typescript
 * const notesShape = createNotesShape('user-uuid');
 * notesShape.subscribe((messages) => {
 *   // Handle sync updates
 * });
 * ```
 */
export function createNotesShape(
  userId: string,
  options?: { signal?: AbortSignal; headers?: Record<string, string> }
): ShapeStream<Row> {
  if (!userId) {
    throw new Error('userId is required to create notes shape');
  }

  return new ShapeStream<Row>({
    url: SHAPE_API_URL,
    params: {
      table: 'notes',
      where: `user_id = '${userId}'`,
    },
    signal: options?.signal,
    headers: options?.headers,
  });
}

/**
 * Creates a shape stream for syncing relations associated with a user's notes.
 *
 * Relations are linked to notes via source_id. This shape uses a subquery
 * to filter relations where the source note belongs to the specified user.
 *
 * @param userId - The UUID of the user whose note relations to sync
 * @param options - Additional ShapeStream options
 * @returns A ShapeStream instance for the user's relations
 *
 * @example
 * ```typescript
 * const relationsShape = createRelationsShape('user-uuid');
 * relationsShape.subscribe((messages) => {
 *   // Handle sync updates
 * });
 * ```
 */
export function createRelationsShape(
  userId: string,
  options?: { signal?: AbortSignal; headers?: Record<string, string> }
): ShapeStream<Row> {
  if (!userId) {
    throw new Error('userId is required to create relations shape');
  }

  return new ShapeStream<Row>({
    url: SHAPE_API_URL,
    params: {
      table: 'relations',
      where: `source_id IN (SELECT id FROM notes WHERE user_id = '${userId}')`,
    },
    signal: options?.signal,
    headers: options?.headers,
  });
}

/**
 * Creates a shape stream for syncing recent sessions.
 *
 * Sessions are filtered to only include those from the last 30 days.
 * This prevents syncing historical session data that is unlikely to be
 * needed for real-time collaboration.
 *
 * @param options - Additional ShapeStream options
 * @returns A ShapeStream instance for recent sessions
 *
 * @example
 * ```typescript
 * const sessionsShape = createSessionsShape();
 * sessionsShape.subscribe((messages) => {
 *   // Handle sync updates
 * });
 * ```
 */
export function createSessionsShape(
  options?: { signal?: AbortSignal; headers?: Record<string, string> }
): ShapeStream<Row> {
  return new ShapeStream<Row>({
    url: SHAPE_API_URL,
    params: {
      table: 'sessions',
      where: `started_at > now() - interval '30 days'`,
    },
    signal: options?.signal,
    headers: options?.headers,
  });
}

// ============================================================================
// Shape Configuration Helpers
// ============================================================================

/**
 * Shape configuration for creating shapes with custom options.
 */
export interface ShapeConfig {
  /** The Electric sync service URL */
  electricUrl?: string;
  /** Additional headers to include in requests */
  headers?: Record<string, string>;
  /** Signal for aborting the shape stream */
  signal?: AbortSignal;
}

/**
 * Creates all shapes for a user with shared configuration.
 *
 * @param userId - The UUID of the user
 * @param config - Shared configuration for all shapes
 * @returns Object containing all shape streams for the user
 *
 * @example
 * ```typescript
 * const shapes = createUserShapes('user-uuid', {
 *   headers: { Authorization: `Bearer ${token}` }
 * });
 *
 * // Access individual shapes
 * shapes.notes.subscribe(...);
 * shapes.relations.subscribe(...);
 * shapes.sessions.subscribe(...);
 * ```
 */
export function createUserShapes(userId: string, config?: ShapeConfig) {
  const baseOptions = {
    headers: config?.headers,
    signal: config?.signal,
  };

  return {
    notes: createNotesShape(userId, baseOptions),
    relations: createRelationsShape(userId, baseOptions),
    sessions: createSessionsShape(baseOptions),
  };
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Gets the Electric URL from environment or throws an error if not configured.
 */
export function getElectricUrl(): string {
  const url = process.env.NEXT_PUBLIC_ELECTRIC_URL;
  if (!url) {
    console.warn(
      'NEXT_PUBLIC_ELECTRIC_URL is not set. Using default: http://localhost:3000'
    );
    return 'http://localhost:3000';
  }
  return url;
}

/**
 * Checks if Electric sync is available by pinging the service.
 *
 * @returns Promise resolving to true if Electric is reachable
 */
export async function isElectricAvailable(): Promise<boolean> {
  try {
    const response = await fetch(`${getElectricUrl()}/v1/health`, {
      method: 'GET',
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch {
    return false;
  }
}
