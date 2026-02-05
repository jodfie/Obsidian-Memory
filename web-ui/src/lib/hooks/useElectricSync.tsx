/**
 * React Hook for ElectricSQL Sync in Obsidian-Memory.
 *
 * Provides a convenient React interface for managing Electric sync
 * connections and subscribing to real-time data updates.
 *
 * @see https://electric-sql.com/docs/api/clients/typescript
 */

'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  ShapeManager,
  getShapeManager,
  type ConnectionState,
  type Subscription,
} from '../electric-client';
import type {
  ElectricNote,
  ElectricRelation,
  ElectricSession,
} from '../electric-shapes';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for the useElectricSync hook.
 */
export interface UseElectricSyncOptions {
  /** User ID for filtering synced data */
  userId?: string;
  /** Whether to automatically connect on mount */
  autoConnect?: boolean;
  /** Custom Electric URL (overrides NEXT_PUBLIC_ELECTRIC_URL) */
  electricUrl?: string;
  /** Whether to sync notes */
  syncNotes?: boolean;
  /** Whether to sync relations */
  syncRelations?: boolean;
  /** Whether to sync sessions */
  syncSessions?: boolean;
}

/**
 * Return type for the useElectricSync hook.
 */
export interface UseElectricSyncReturn {
  /** Current connection state */
  connectionState: ConnectionState;
  /** Whether currently connected */
  isConnected: boolean;
  /** Whether currently connecting */
  isConnecting: boolean;
  /** Any error that occurred */
  error: Error | null;
  /** Synced notes data */
  notes: ElectricNote[];
  /** Synced relations data */
  relations: ElectricRelation[];
  /** Synced sessions data */
  sessions: ElectricSession[];
  /** Manually connect to Electric */
  connect: () => Promise<boolean>;
  /** Disconnect from Electric */
  disconnect: () => void;
  /** Refresh all subscriptions */
  refresh: () => void;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * React hook for managing ElectricSQL sync connections and data.
 *
 * @param options - Configuration options for the sync
 * @returns Object containing connection state and synced data
 *
 * @example
 * ```tsx
 * 'use client';
 *
 * import { useElectricSync } from '@/lib/hooks/useElectricSync';
 *
 * export function NotesPage() {
 *   const {
 *     connectionState,
 *     isConnected,
 *     notes,
 *     relations,
 *     connect,
 *   } = useElectricSync({
 *     userId: 'user-uuid',
 *     syncNotes: true,
 *     syncRelations: true,
 *   });
 *
 *   if (!isConnected) {
 *     return <button onClick={connect}>Connect to sync</button>;
 *   }
 *
 *   return (
 *     <div>
 *       <p>Status: {connectionState}</p>
 *       <ul>
 *         {notes.map(note => (
 *           <li key={note.id}>{note.title}</li>
 *         ))}
 *       </ul>
 *     </div>
 *   );
 * }
 * ```
 */
export function useElectricSync(
  options: UseElectricSyncOptions = {}
): UseElectricSyncReturn {
  const {
    userId,
    autoConnect = true,
    electricUrl,
    syncNotes = true,
    syncRelations = true,
    syncSessions = false,
  } = options;

  // State
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const [error, setError] = useState<Error | null>(null);
  const [notes, setNotes] = useState<ElectricNote[]>([]);
  const [relations, setRelations] = useState<ElectricRelation[]>([]);
  const [sessions, setSessions] = useState<ElectricSession[]>([]);

  // Refs to track subscriptions and manager
  const managerRef = useRef<ShapeManager | null>(null);
  const subscriptionsRef = useRef<Subscription[]>([]);
  const mountedRef = useRef(true);

  // Derived state
  const isConnected = connectionState === 'connected';
  const isConnecting = connectionState === 'connecting' || connectionState === 'reconnecting';

  // Get or create the shape manager
  const getManager = useCallback(() => {
    if (!managerRef.current) {
      managerRef.current = getShapeManager({
        electricUrl,
        onConnectionStateChange: (state) => {
          if (mountedRef.current) {
            setConnectionState(state);
          }
        },
        onError: (err) => {
          if (mountedRef.current) {
            setError(err);
          }
        },
      });
    }
    return managerRef.current;
  }, [electricUrl]);

  // Connect to Electric
  const connect = useCallback(async (): Promise<boolean> => {
    setError(null);
    const manager = getManager();
    return manager.connect();
  }, [getManager]);

  // Disconnect from Electric
  const disconnect = useCallback(() => {
    const manager = managerRef.current;
    if (manager) {
      manager.disconnect();
    }
  }, []);

  // Set up subscriptions
  const setupSubscriptions = useCallback(() => {
    if (!userId) {
      return;
    }

    const manager = getManager();

    // Clean up existing subscriptions
    for (const sub of subscriptionsRef.current) {
      sub.unsubscribe();
    }
    subscriptionsRef.current = [];

    // Subscribe to notes
    if (syncNotes) {
      const notesSub = manager.subscribeToNotes(
        userId,
        (data) => {
          if (mountedRef.current) {
            setNotes(data as unknown as ElectricNote[]);
          }
        },
        (err) => {
          if (mountedRef.current) {
            setError(err);
          }
        }
      );
      subscriptionsRef.current.push(notesSub);
    }

    // Subscribe to relations
    if (syncRelations) {
      const relationsSub = manager.subscribeToRelations(
        userId,
        (data) => {
          if (mountedRef.current) {
            setRelations(data as unknown as ElectricRelation[]);
          }
        },
        (err) => {
          if (mountedRef.current) {
            setError(err);
          }
        }
      );
      subscriptionsRef.current.push(relationsSub);
    }

    // Subscribe to sessions
    if (syncSessions) {
      const sessionsSub = manager.subscribeToSessions(
        (data) => {
          if (mountedRef.current) {
            setSessions(data as unknown as ElectricSession[]);
          }
        },
        (err) => {
          if (mountedRef.current) {
            setError(err);
          }
        }
      );
      subscriptionsRef.current.push(sessionsSub);
    }
  }, [userId, syncNotes, syncRelations, syncSessions, getManager]);

  // Refresh subscriptions
  const refresh = useCallback(() => {
    setupSubscriptions();
  }, [setupSubscriptions]);

  // Auto-connect and set up subscriptions on mount
  useEffect(() => {
    mountedRef.current = true;

    const initialize = async () => {
      if (autoConnect) {
        const connected = await connect();
        if (connected && userId) {
          setupSubscriptions();
        }
      }
    };

    initialize();

    return () => {
      mountedRef.current = false;
      // Clean up subscriptions but don't destroy the manager
      // (it's a singleton that may be used elsewhere)
      for (const sub of subscriptionsRef.current) {
        sub.unsubscribe();
      }
      subscriptionsRef.current = [];
    };
  }, [autoConnect, connect, userId, setupSubscriptions]);

  // Re-subscribe when userId changes
  useEffect(() => {
    if (isConnected && userId) {
      setupSubscriptions();
    }
  }, [isConnected, userId, setupSubscriptions]);

  // Return memoized result
  return useMemo(
    () => ({
      connectionState,
      isConnected,
      isConnecting,
      error,
      notes,
      relations,
      sessions,
      connect,
      disconnect,
      refresh,
    }),
    [
      connectionState,
      isConnected,
      isConnecting,
      error,
      notes,
      relations,
      sessions,
      connect,
      disconnect,
      refresh,
    ]
  );
}

// ============================================================================
// Additional Hooks
// ============================================================================

/**
 * Hook for just the Electric connection state without data subscriptions.
 * Useful for status indicators that don't need the actual data.
 */
export function useElectricConnectionState(): {
  connectionState: ConnectionState;
  isConnected: boolean;
  isConnecting: boolean;
  connect: () => Promise<boolean>;
  disconnect: () => void;
} {
  const { connectionState, isConnected, isConnecting, connect, disconnect } =
    useElectricSync({
      autoConnect: false,
      syncNotes: false,
      syncRelations: false,
      syncSessions: false,
    });

  return { connectionState, isConnected, isConnecting, connect, disconnect };
}

/**
 * Hook specifically for syncing notes.
 */
export function useElectricNotes(userId: string): {
  notes: ElectricNote[];
  isLoading: boolean;
  error: Error | null;
} {
  const { notes, isConnecting, error } = useElectricSync({
    userId,
    syncNotes: true,
    syncRelations: false,
    syncSessions: false,
  });

  return {
    notes,
    isLoading: isConnecting,
    error,
  };
}

/**
 * Hook specifically for syncing relations.
 */
export function useElectricRelations(userId: string): {
  relations: ElectricRelation[];
  isLoading: boolean;
  error: Error | null;
} {
  const { relations, isConnecting, error } = useElectricSync({
    userId,
    syncNotes: false,
    syncRelations: true,
    syncSessions: false,
  });

  return {
    relations,
    isLoading: isConnecting,
    error,
  };
}

/**
 * Hook specifically for syncing sessions.
 */
export function useElectricSessions(): {
  sessions: ElectricSession[];
  isLoading: boolean;
  error: Error | null;
} {
  const { sessions, isConnecting, error } = useElectricSync({
    syncNotes: false,
    syncRelations: false,
    syncSessions: true,
  });

  return {
    sessions,
    isLoading: isConnecting,
    error,
  };
}

// ============================================================================
// Context Provider (Optional)
// ============================================================================

import { createContext, useContext, type ReactNode } from 'react';

const ElectricSyncContext = createContext<UseElectricSyncReturn | null>(null);

/**
 * Props for the ElectricSyncProvider component.
 */
export interface ElectricSyncProviderProps {
  children: ReactNode;
  userId?: string;
  autoConnect?: boolean;
}

/**
 * Provider component for sharing Electric sync state across the app.
 *
 * @example
 * ```tsx
 * // In your layout or app component
 * <ElectricSyncProvider userId={user.id}>
 *   <YourApp />
 * </ElectricSyncProvider>
 *
 * // In child components
 * const { notes, relations } = useElectricSyncContext();
 * ```
 */
export function ElectricSyncProvider({
  children,
  userId,
  autoConnect = true,
}: ElectricSyncProviderProps) {
  const sync = useElectricSync({
    userId,
    autoConnect,
    syncNotes: true,
    syncRelations: true,
    syncSessions: true,
  });

  return (
    <ElectricSyncContext.Provider value={sync}>
      {children}
    </ElectricSyncContext.Provider>
  );
}

/**
 * Hook to access the Electric sync context.
 * Must be used within an ElectricSyncProvider.
 */
export function useElectricSyncContext(): UseElectricSyncReturn {
  const context = useContext(ElectricSyncContext);
  if (!context) {
    throw new Error(
      'useElectricSyncContext must be used within an ElectricSyncProvider'
    );
  }
  return context;
}
