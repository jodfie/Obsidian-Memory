/**
 * ElectricSQL Client Manager for Obsidian-Memory.
 *
 * Manages multiple ShapeStream instances and provides a unified interface
 * for subscribing to real-time data sync across notes, relations, and sessions.
 *
 * @see https://electric-sql.com/docs/api/clients/typescript
 */

import { ShapeStream, type Message, type Row } from '@electric-sql/client';
import {
  createNotesShape,
  createRelationsShape,
  createSessionsShape,
  isElectricAvailable,
} from './electric-shapes';

// ============================================================================
// Types
// ============================================================================

/**
 * Connection states for the Electric sync service.
 */
export type ConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'error'
  | 'reconnecting';

/**
 * Callback function for data updates.
 */
export type UpdateCallback<T> = (data: T[]) => void;

/**
 * Callback function for error handling.
 */
export type ErrorCallback = (error: Error) => void;

/**
 * Subscription handle returned when subscribing to a shape.
 */
export interface Subscription {
  /** Unique identifier for this subscription */
  id: string;
  /** Unsubscribe and clean up this subscription */
  unsubscribe: () => void;
}

/**
 * Options for ShapeManager initialization.
 */
export interface ShapeManagerOptions {
  /** Electric sync service URL (defaults to NEXT_PUBLIC_ELECTRIC_URL) */
  electricUrl?: string;
  /** Callback when connection state changes */
  onConnectionStateChange?: (state: ConnectionState) => void;
  /** Callback when any error occurs */
  onError?: ErrorCallback;
  /** Whether to automatically reconnect on errors */
  autoReconnect?: boolean;
  /** Delay before reconnecting (ms) */
  reconnectDelay?: number;
}

// ============================================================================
// ShapeManager Class
// ============================================================================

/**
 * Manages multiple ElectricSQL ShapeStream instances with unified
 * connection state management and subscription handling.
 *
 * @example
 * ```typescript
 * const manager = new ShapeManager({
 *   onConnectionStateChange: (state) => console.log('Connection:', state),
 *   onError: (error) => console.error('Sync error:', error),
 * });
 *
 * // Subscribe to notes for a user
 * const sub = manager.subscribeToNotes('user-uuid', (notes) => {
 *   console.log('Notes updated:', notes);
 * });
 *
 * // Later: cleanup
 * sub.unsubscribe();
 * manager.cleanup();
 * ```
 */
export class ShapeManager {
  private options: ShapeManagerOptions;
  private connectionState: ConnectionState = 'disconnected';
  private subscriptions: Map<string, Subscription> = new Map();
  private shapes: Map<string, ShapeStream<Row>> = new Map();
  private dataCache: Map<string, Row[]> = new Map();
  private subscriptionCounter = 0;
  private abortController: AbortController | null = null;

  constructor(options: ShapeManagerOptions = {}) {
    this.options = {
      autoReconnect: true,
      reconnectDelay: 3000,
      ...options,
    };
  }

  // ==========================================================================
  // Connection State Management
  // ==========================================================================

  /**
   * Gets the current connection state.
   */
  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  /**
   * Sets the connection state and notifies listeners.
   */
  private setConnectionState(state: ConnectionState): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.options.onConnectionStateChange?.(state);
    }
  }

  /**
   * Initializes the connection to Electric.
   * Call this before subscribing to any shapes.
   */
  async connect(): Promise<boolean> {
    if (this.connectionState === 'connected') {
      return true;
    }

    this.setConnectionState('connecting');
    this.abortController = new AbortController();

    try {
      const available = await isElectricAvailable();
      if (available) {
        this.setConnectionState('connected');
        return true;
      } else {
        this.setConnectionState('error');
        this.options.onError?.(new Error('Electric service is not available'));
        return false;
      }
    } catch (error) {
      this.setConnectionState('error');
      this.options.onError?.(
        error instanceof Error ? error : new Error('Failed to connect to Electric')
      );
      return false;
    }
  }

  /**
   * Disconnects from Electric and cleans up all subscriptions.
   */
  disconnect(): void {
    this.cleanup();
    this.setConnectionState('disconnected');
  }

  // ==========================================================================
  // Subscription Methods
  // ==========================================================================

  /**
   * Subscribes to notes for a specific user.
   *
   * @param userId - The user's UUID
   * @param onUpdate - Callback when notes data changes
   * @param onError - Optional error callback for this subscription
   * @returns Subscription handle for unsubscribing
   */
  subscribeToNotes(
    userId: string,
    onUpdate: UpdateCallback<Row>,
    onError?: ErrorCallback
  ): Subscription {
    const shapeKey = `notes:${userId}`;

    return this.subscribeToShape(
      shapeKey,
      () => createNotesShape(userId, { signal: this.abortController?.signal }),
      onUpdate,
      onError
    );
  }

  /**
   * Subscribes to relations for a specific user's notes.
   *
   * @param userId - The user's UUID
   * @param onUpdate - Callback when relations data changes
   * @param onError - Optional error callback for this subscription
   * @returns Subscription handle for unsubscribing
   */
  subscribeToRelations(
    userId: string,
    onUpdate: UpdateCallback<Row>,
    onError?: ErrorCallback
  ): Subscription {
    const shapeKey = `relations:${userId}`;

    return this.subscribeToShape(
      shapeKey,
      () => createRelationsShape(userId, { signal: this.abortController?.signal }),
      onUpdate,
      onError
    );
  }

  /**
   * Subscribes to recent sessions.
   *
   * @param onUpdate - Callback when sessions data changes
   * @param onError - Optional error callback for this subscription
   * @returns Subscription handle for unsubscribing
   */
  subscribeToSessions(
    onUpdate: UpdateCallback<Row>,
    onError?: ErrorCallback
  ): Subscription {
    const shapeKey = 'sessions';

    return this.subscribeToShape(
      shapeKey,
      () => createSessionsShape({ signal: this.abortController?.signal }),
      onUpdate,
      onError
    );
  }

  // ==========================================================================
  // Internal Subscription Management
  // ==========================================================================

  /**
   * Generic method to subscribe to any shape stream.
   */
  private subscribeToShape<T extends Row>(
    shapeKey: string,
    createShape: () => ShapeStream<T>,
    onUpdate: UpdateCallback<T>,
    onError?: ErrorCallback
  ): Subscription {
    const subscriptionId = `${shapeKey}:${++this.subscriptionCounter}`;

    // Get or create the shape
    let shape = this.shapes.get(shapeKey) as ShapeStream<T> | undefined;
    if (!shape) {
      shape = createShape();
      this.shapes.set(shapeKey, shape as ShapeStream<Row>);
      this.dataCache.set(shapeKey, []);

      // Set up shape message handling
      this.setupShapeHandlers(shapeKey, shape, onError);
    }

    // Create subscription that listens to cached data updates
    const subscription: Subscription = {
      id: subscriptionId,
      unsubscribe: () => {
        this.subscriptions.delete(subscriptionId);
        // If no more subscriptions for this shape, clean it up
        const hasActiveSubscriptions = Array.from(this.subscriptions.keys()).some(
          (key) => key.startsWith(shapeKey)
        );
        if (!hasActiveSubscriptions) {
          this.shapes.delete(shapeKey);
          this.dataCache.delete(shapeKey);
        }
      },
    };

    this.subscriptions.set(subscriptionId, subscription);

    // Subscribe to the shape stream
    shape.subscribe((messages: Message<T>[]) => {
      this.handleShapeMessages(shapeKey, messages);
      // Notify this subscriber with the updated cache
      const cachedData = this.dataCache.get(shapeKey) as T[] | undefined;
      if (cachedData) {
        onUpdate(cachedData);
      }
    });

    // Send initial data if available
    const cachedData = this.dataCache.get(shapeKey) as T[] | undefined;
    if (cachedData && cachedData.length > 0) {
      onUpdate(cachedData);
    }

    return subscription;
  }

  /**
   * Sets up error and connection handlers for a shape.
   */
  private setupShapeHandlers<T extends Row>(
    shapeKey: string,
    shape: ShapeStream<T>,
    onError?: ErrorCallback
  ): void {
    // Handle errors from the shape stream
    shape.subscribe(
      () => {
        // Data handled in main subscription
      },
      (error: Error) => {
        this.handleShapeError(shapeKey, error, onError);
      }
    );
  }

  /**
   * Handles messages from a shape stream and updates the cache.
   */
  private handleShapeMessages<T extends Row>(
    shapeKey: string,
    messages: Message<T>[]
  ): void {
    const currentData = (this.dataCache.get(shapeKey) || []) as T[];
    const dataMap = new Map(currentData.map((item) => [String(item['id']), item]));

    for (const message of messages) {
      if (!('value' in message)) continue;
      const value = message.value as T;
      if (message.headers.operation === 'insert') {
        dataMap.set(String(value['id']), value);
      } else if (message.headers.operation === 'update') {
        dataMap.set(String(value['id']), value);
      } else if (message.headers.operation === 'delete') {
        dataMap.delete(String(value['id']));
      }
    }

    this.dataCache.set(shapeKey, Array.from(dataMap.values()));
  }

  /**
   * Handles errors from a shape stream.
   */
  private handleShapeError(
    shapeKey: string,
    error: Error,
    onError?: ErrorCallback
  ): void {
    console.error(`Electric shape error (${shapeKey}):`, error);

    // Notify subscription-specific error handler
    onError?.(error);

    // Notify global error handler
    this.options.onError?.(error);

    // Update connection state
    this.setConnectionState('error');

    // Attempt reconnection if enabled
    if (this.options.autoReconnect) {
      this.scheduleReconnect();
    }
  }

  /**
   * Schedules a reconnection attempt.
   */
  private scheduleReconnect(): void {
    if (this.connectionState === 'reconnecting') {
      return;
    }

    this.setConnectionState('reconnecting');

    setTimeout(async () => {
      const connected = await this.connect();
      if (connected) {
        // Reconnect all shapes
        this.reconnectShapes();
      } else if (this.options.autoReconnect) {
        // Schedule another attempt
        this.scheduleReconnect();
      }
    }, this.options.reconnectDelay);
  }

  /**
   * Reconnects all active shapes after a connection recovery.
   */
  private reconnectShapes(): void {
    // The shapes will automatically reconnect via their internal mechanisms
    // This method is a placeholder for any additional reconnection logic needed
    console.log('Reconnecting shapes...');
  }

  // ==========================================================================
  // Cleanup
  // ==========================================================================

  /**
   * Cleans up all subscriptions and shape streams.
   * Call this when the manager is no longer needed.
   */
  cleanup(): void {
    // Abort all ongoing requests
    this.abortController?.abort();
    this.abortController = null;

    // Clear all subscriptions
    for (const subscription of this.subscriptions.values()) {
      subscription.unsubscribe();
    }
    this.subscriptions.clear();

    // Clear shapes and cache
    this.shapes.clear();
    this.dataCache.clear();
  }

  /**
   * Gets the current cached data for a specific shape.
   * Useful for getting data without setting up a subscription.
   */
  getCachedData<T extends Row>(shapeKey: string): T[] {
    return (this.dataCache.get(shapeKey) || []) as T[];
  }

  /**
   * Gets statistics about current subscriptions.
   */
  getStats(): {
    connectionState: ConnectionState;
    activeShapes: number;
    activeSubscriptions: number;
    cachedItems: Record<string, number>;
  } {
    const cachedItems: Record<string, number> = {};
    for (const [key, data] of this.dataCache.entries()) {
      cachedItems[key] = data.length;
    }

    return {
      connectionState: this.connectionState,
      activeShapes: this.shapes.size,
      activeSubscriptions: this.subscriptions.size,
      cachedItems,
    };
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

let shapeManagerInstance: ShapeManager | null = null;

/**
 * Gets the singleton ShapeManager instance.
 * Creates one if it doesn't exist.
 *
 * @param options - Options for creating the manager (only used on first call)
 * @returns The ShapeManager singleton instance
 */
export function getShapeManager(options?: ShapeManagerOptions): ShapeManager {
  if (!shapeManagerInstance) {
    shapeManagerInstance = new ShapeManager(options);
  }
  return shapeManagerInstance;
}

/**
 * Resets the singleton ShapeManager instance.
 * Useful for testing or when reconfiguration is needed.
 */
export function resetShapeManager(): void {
  if (shapeManagerInstance) {
    shapeManagerInstance.cleanup();
    shapeManagerInstance = null;
  }
}
