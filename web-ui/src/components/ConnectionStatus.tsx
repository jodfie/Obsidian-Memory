'use client';

/**
 * Connection status indicator component for Supabase Realtime.
 *
 * Shows a visual indicator of the sync/connection status:
 * - Green: Connected and syncing
 * - Yellow: Reconnecting
 * - Red: Disconnected or error
 * - Gray: Connecting
 */

import { useEffect, useState } from 'react';
import { type ConnectionStatus as ConnectionStatusType } from '../lib/supabase-realtime';

// ============================================================================
// Types
// ============================================================================

export interface ConnectionStatusProps {
  /** Current connection status */
  status: ConnectionStatusType;
  /** Whether to show the status label text (default: true) */
  showLabel?: boolean;
  /** Size variant (default: 'md') */
  size?: 'sm' | 'md' | 'lg';
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Status Configuration
// ============================================================================

interface StatusConfig {
  color: string;
  pulseColor: string;
  label: string;
  description: string;
}

const statusConfig: Record<ConnectionStatusType, StatusConfig> = {
  connected: {
    color: 'bg-green-500',
    pulseColor: 'bg-green-400',
    label: 'Synced',
    description: 'Connected and receiving live updates',
  },
  connecting: {
    color: 'bg-gray-400',
    pulseColor: 'bg-gray-300',
    label: 'Connecting',
    description: 'Establishing connection...',
  },
  reconnecting: {
    color: 'bg-yellow-500',
    pulseColor: 'bg-yellow-400',
    label: 'Reconnecting',
    description: 'Connection lost, attempting to reconnect...',
  },
  disconnected: {
    color: 'bg-red-500',
    pulseColor: 'bg-red-400',
    label: 'Offline',
    description: 'Not connected to sync service',
  },
  error: {
    color: 'bg-red-600',
    pulseColor: 'bg-red-500',
    label: 'Error',
    description: 'Connection error occurred',
  },
};

const sizeConfig = {
  sm: {
    dot: 'h-2 w-2',
    pulse: 'h-2 w-2',
    text: 'text-xs',
    gap: 'gap-1.5',
  },
  md: {
    dot: 'h-2.5 w-2.5',
    pulse: 'h-2.5 w-2.5',
    text: 'text-sm',
    gap: 'gap-2',
  },
  lg: {
    dot: 'h-3 w-3',
    pulse: 'h-3 w-3',
    text: 'text-base',
    gap: 'gap-2.5',
  },
};

// ============================================================================
// Component
// ============================================================================

/**
 * Displays a connection status indicator with optional label.
 *
 * @example
 * ```tsx
 * // Basic usage
 * <ConnectionStatus status="connected" />
 *
 * // Without label (just the dot)
 * <ConnectionStatus status={connectionStatus} showLabel={false} />
 *
 * // Small size in a header
 * <ConnectionStatus status={connectionStatus} size="sm" />
 *
 * // Large size with custom class
 * <ConnectionStatus
 *   status={connectionStatus}
 *   size="lg"
 *   className="ml-4"
 * />
 * ```
 */
export default function ConnectionStatus({
  status,
  showLabel = true,
  size = 'md',
  className = '',
}: ConnectionStatusProps) {
  const config = statusConfig[status];
  const sizes = sizeConfig[size];

  // Show pulse animation for connecting/reconnecting states
  const shouldPulse = status === 'connecting' || status === 'reconnecting';

  return (
    <div
      className={`inline-flex items-center ${sizes.gap} ${className}`}
      title={config.description}
      role="status"
      aria-label={`Sync status: ${config.label}`}
    >
      <span className="relative flex">
        {/* Pulse animation ring */}
        {shouldPulse && (
          <span
            className={`absolute inline-flex h-full w-full rounded-full ${config.pulseColor} opacity-75 animate-ping`}
          />
        )}
        {/* Status dot */}
        <span
          className={`relative inline-flex rounded-full ${sizes.dot} ${config.color}`}
        />
      </span>
      {showLabel && (
        <span className={`${sizes.text} font-medium text-gray-600 dark:text-gray-300`}>
          {config.label}
        </span>
      )}
    </div>
  );
}

// ============================================================================
// Compact Variant
// ============================================================================

export interface ConnectionStatusCompactProps {
  /** Current connection status */
  status: ConnectionStatusType;
  /** Additional CSS classes */
  className?: string;
}

/**
 * A compact connection status indicator (dot only) for tight spaces.
 *
 * @example
 * ```tsx
 * // In a toolbar or header
 * <ConnectionStatusCompact status={connectionStatus} />
 * ```
 */
export function ConnectionStatusCompact({
  status,
  className = '',
}: ConnectionStatusCompactProps) {
  return (
    <ConnectionStatus
      status={status}
      showLabel={false}
      size="sm"
      className={className}
    />
  );
}

// ============================================================================
// Badge Variant
// ============================================================================

export interface ConnectionStatusBadgeProps {
  /** Current connection status */
  status: ConnectionStatusType;
  /** Additional CSS classes */
  className?: string;
}

/**
 * A badge-style connection status indicator.
 *
 * @example
 * ```tsx
 * // As a badge in a card header
 * <ConnectionStatusBadge status={connectionStatus} />
 * ```
 */
export function ConnectionStatusBadge({
  status,
  className = '',
}: ConnectionStatusBadgeProps) {
  const config = statusConfig[status];

  const bgColors: Record<ConnectionStatusType, string> = {
    connected: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
    connecting: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300',
    reconnecting: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400',
    disconnected: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
    error: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${bgColors[status]} ${className}`}
      title={config.description}
      role="status"
      aria-label={`Sync status: ${config.label}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${config.color}`} />
      {config.label}
    </span>
  );
}

// ============================================================================
// With Auto-hide (for Connected state)
// ============================================================================

export interface ConnectionStatusAutoHideProps extends ConnectionStatusProps {
  /** Delay in ms before hiding when connected (default: 3000) */
  hideDelay?: number;
}

/**
 * Connection status indicator that auto-hides after connection is established.
 *
 * Useful when you only want to show status during connection issues.
 *
 * @example
 * ```tsx
 * // Will hide 3 seconds after connecting
 * <ConnectionStatusAutoHide status={connectionStatus} />
 *
 * // Custom hide delay
 * <ConnectionStatusAutoHide status={connectionStatus} hideDelay={5000} />
 * ```
 */
export function ConnectionStatusAutoHide({
  status,
  hideDelay = 3000,
  ...props
}: ConnectionStatusAutoHideProps) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (status === 'connected') {
      const timer = setTimeout(() => {
        setVisible(false);
      }, hideDelay);

      return () => clearTimeout(timer);
    } else {
      // Show again when not connected
      setVisible(true);
      return;
    }
  }, [status, hideDelay]);

  if (!visible) {
    return null;
  }

  return <ConnectionStatus status={status} {...props} />;
}
