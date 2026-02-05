/**
 * Supabase client configuration for Obsidian-Memory.
 *
 * Provides typed clients for both client and server components.
 */

import { createClientComponentClient } from '@supabase/auth-helpers-nextjs';
import { createClient } from '@supabase/supabase-js';
import type { SupabaseClient } from '@supabase/supabase-js';

// ============================================================================
// Database Types
// ============================================================================

/**
 * Database schema types for Supabase.
 * These mirror the Postgres schema defined in the migration design doc.
 */
export interface Database {
  public: {
    Tables: {
      notes: {
        Row: {
          id: string;
          path: string;
          title: string;
          content: string;
          frontmatter: Record<string, unknown>;
          created_at: string;
          updated_at: string;
          user_id: string;
        };
        Insert: {
          id?: string;
          path: string;
          title: string;
          content: string;
          frontmatter?: Record<string, unknown>;
          created_at?: string;
          updated_at?: string;
          user_id?: string;
        };
        Update: {
          id?: string;
          path?: string;
          title?: string;
          content?: string;
          frontmatter?: Record<string, unknown>;
          created_at?: string;
          updated_at?: string;
          user_id?: string;
        };
        Relationships: [];
      };
      relations: {
        Row: {
          id: string;
          source_id: string;
          target_path: string;
          relation_type: string;
          context: string | null;
        };
        Insert: {
          id?: string;
          source_id: string;
          target_path: string;
          relation_type: string;
          context?: string | null;
        };
        Update: {
          id?: string;
          source_id?: string;
          target_path?: string;
          relation_type?: string;
          context?: string | null;
        };
        Relationships: [];
      };
      sessions: {
        Row: {
          id: string;
          project: string | null;
          started_at: string;
          ended_at: string | null;
          summary: string | null;
          events: unknown[];
        };
        Insert: {
          id?: string;
          project?: string | null;
          started_at?: string;
          ended_at?: string | null;
          summary?: string | null;
          events?: unknown[];
        };
        Update: {
          id?: string;
          project?: string | null;
          started_at?: string;
          ended_at?: string | null;
          summary?: string | null;
          events?: unknown[];
        };
        Relationships: [];
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
    CompositeTypes: Record<string, never>;
  };
}

// ============================================================================
// Type Aliases for Convenience
// ============================================================================

export type Note = Database['public']['Tables']['notes']['Row'];
export type NoteInsert = Database['public']['Tables']['notes']['Insert'];
export type NoteUpdate = Database['public']['Tables']['notes']['Update'];

export type Relation = Database['public']['Tables']['relations']['Row'];
export type RelationInsert = Database['public']['Tables']['relations']['Insert'];
export type RelationUpdate = Database['public']['Tables']['relations']['Update'];

export type Session = Database['public']['Tables']['sessions']['Row'];
export type SessionInsert = Database['public']['Tables']['sessions']['Insert'];
export type SessionUpdate = Database['public']['Tables']['sessions']['Update'];

// ============================================================================
// Client Component Client
// ============================================================================

/**
 * Creates a Supabase client for use in Client Components.
 *
 * Usage:
 * ```tsx
 * 'use client';
 * import { createBrowserClient } from '@/lib/supabase-client';
 *
 * export function MyComponent() {
 *   const supabase = createBrowserClient();
 *   // Use supabase...
 * }
 * ```
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function createBrowserClient(): SupabaseClient<any> {
  return createClientComponentClient();
}

// ============================================================================
// Server Component Client
// ============================================================================

/**
 * Creates a Supabase client for use in Server Components.
 *
 * Note: For server components, you need to use the cookies() function
 * from next/headers. This is a simplified version that works for
 * API routes and server actions.
 *
 * Usage in Server Components:
 * ```tsx
 * import { createServerClient } from '@/lib/supabase-client';
 * import { cookies } from 'next/headers';
 *
 * export default async function Page() {
 *   const supabase = createServerClient();
 *   const { data } = await supabase.from('notes').select();
 *   return <div>...</div>;
 * }
 * ```
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function createServerClient(): SupabaseClient<any> {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      'Missing Supabase environment variables. ' +
        'Please set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.'
    );
  }

  return createClient(supabaseUrl, supabaseAnonKey);
}

// ============================================================================
// Singleton Client for Client Components
// ============================================================================

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let browserClient: SupabaseClient<any> | null = null;

/**
 * Returns a singleton Supabase client for browser use.
 * This avoids creating multiple client instances in the same session.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function getSupabaseBrowserClient(): SupabaseClient<any> {
  if (!browserClient) {
    browserClient = createBrowserClient();
  }
  return browserClient;
}

// ============================================================================
// Export default client for convenience
// ============================================================================

/**
 * Default export: Use this in client components.
 * For server components, use createServerClient() instead.
 */
export const supabase = typeof window !== 'undefined' ? createBrowserClient() : null;
