'use client';

/**
 * React Query provider for Obsidian-Memory.
 *
 * Wraps the application with QueryClientProvider for data fetching
 * and caching with TanStack Query.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useState, type ReactNode } from 'react';

// ============================================================================
// Query Client Configuration
// ============================================================================

/**
 * Default options for the QueryClient.
 */
const defaultQueryClientOptions = {
  queries: {
    // Don't refetch on window focus by default (can be overridden per-query)
    refetchOnWindowFocus: false,
    // Retry failed requests 1 time
    retry: 1,
    // Consider data stale after 30 seconds
    staleTime: 30 * 1000,
    // Keep unused data in cache for 5 minutes
    gcTime: 5 * 60 * 1000,
  },
  mutations: {
    // Retry failed mutations 0 times
    retry: 0,
  },
};

// ============================================================================
// Provider Component
// ============================================================================

interface ProvidersProps {
  children: ReactNode;
}

/**
 * Application providers wrapper.
 *
 * Includes:
 * - QueryClientProvider for TanStack Query
 * - ReactQueryDevtools (development only)
 *
 * Usage in layout.tsx:
 * ```tsx
 * import { Providers } from '@/lib/providers';
 *
 * export default function RootLayout({ children }) {
 *   return (
 *     <html>
 *       <body>
 *         <Providers>{children}</Providers>
 *       </body>
 *     </html>
 *   );
 * }
 * ```
 */
export function Providers({ children }: ProvidersProps) {
  // Create a new QueryClient instance for each session
  // This prevents data sharing between users/requests
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: defaultQueryClientOptions,
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* Devtools only in development mode */}
      {process.env.NODE_ENV === 'development' && (
        <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
      )}
    </QueryClientProvider>
  );
}

// ============================================================================
// Export QueryClient factory for testing
// ============================================================================

/**
 * Creates a new QueryClient with default options.
 * Useful for testing or creating isolated clients.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: defaultQueryClientOptions,
  });
}
