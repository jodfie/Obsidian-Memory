'use client';

/**
 * Graph panel showing backlinks and outgoing links for a note.
 *
 * Features:
 * - Collapsible panel
 * - Shows backlinks (notes linking to this note)
 * - Shows outgoing links (notes this note links to)
 * - Click to navigate to linked notes
 * - Simple list view (can add graph visualization later)
 */

import { useState } from 'react';
import { useBacklinks, useOutgoingLinks } from '@/lib/hooks/useRelations';
import type { Note } from '@/lib/supabase-client';
import type { LinkedNote } from '@/lib/hooks/useRelations';

// ============================================================================
// Types
// ============================================================================

interface GraphPanelProps {
  /** ID of the currently selected note */
  noteId: string | null | undefined;
  /** Callback when a linked note is clicked */
  onNavigateToNote: (note: Note) => void;
  /** Whether the panel is collapsed */
  isCollapsed?: boolean;
  /** Callback to toggle collapse state */
  onToggleCollapse?: () => void;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Link Item Component
// ============================================================================

interface LinkItemProps {
  linkedNote: LinkedNote;
  onClick: () => void;
}

function LinkItem({ linkedNote, onClick }: LinkItemProps) {
  const { note, relation } = linkedNote;

  return (
    <button
      onClick={onClick}
      className="
        w-full text-left p-2 rounded-lg
        hover:bg-gray-100 dark:hover:bg-gray-700
        transition-colors duration-150
        focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset
      "
    >
      <div className="flex items-center gap-2">
        <svg
          className="w-4 h-4 text-gray-400 flex-shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <span className="text-sm font-medium text-gray-900 dark:text-white truncate">
          {note.title || 'Untitled'}
        </span>
      </div>
      {relation.context && (
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-6 line-clamp-2">
          {relation.context}
        </p>
      )}
    </button>
  );
}

// ============================================================================
// Section Component
// ============================================================================

interface LinkSectionProps {
  title: string;
  icon: React.ReactNode;
  links: LinkedNote[];
  isLoading: boolean;
  error: Error | null;
  onNavigateToNote: (note: Note) => void;
  emptyMessage: string;
}

function LinkSection({
  title,
  icon,
  links,
  isLoading,
  error,
  onNavigateToNote,
  emptyMessage,
}: LinkSectionProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  return (
    <div className="border-b border-gray-200 dark:border-gray-700 last:border-b-0">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="
          w-full flex items-center justify-between
          px-3 py-2
          text-sm font-medium text-gray-700 dark:text-gray-300
          hover:bg-gray-50 dark:hover:bg-gray-800
          transition-colors
        "
      >
        <div className="flex items-center gap-2">
          {icon}
          <span>{title}</span>
          <span className="text-xs text-gray-400 dark:text-gray-500 ml-1">
            ({links.length})
          </span>
        </div>
        <svg
          className={`w-4 h-4 transition-transform ${isExpanded ? '' : '-rotate-90'}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {isExpanded && (
        <div className="px-2 pb-2">
          {isLoading ? (
            <div className="p-2 space-y-2">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-8 bg-gray-100 dark:bg-gray-700 rounded animate-pulse"
                />
              ))}
            </div>
          ) : error ? (
            <p className="text-xs text-red-500 dark:text-red-400 p-2">
              Failed to load links
            </p>
          ) : links.length === 0 ? (
            <p className="text-xs text-gray-400 dark:text-gray-500 p-2 italic">
              {emptyMessage}
            </p>
          ) : (
            <div className="space-y-1">
              {links.map((linkedNote) => (
                <LinkItem
                  key={linkedNote.note.id}
                  linkedNote={linkedNote}
                  onClick={() => onNavigateToNote(linkedNote.note)}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function GraphPanel({
  noteId,
  onNavigateToNote,
  isCollapsed = false,
  onToggleCollapse,
  className = '',
}: GraphPanelProps) {
  // Fetch backlinks and outgoing links
  const {
    data: backlinksData,
    isLoading: backlinksLoading,
    error: backlinksError,
  } = useBacklinks(noteId);

  const {
    data: outgoingData,
    isLoading: outgoingLoading,
    error: outgoingError,
  } = useOutgoingLinks(noteId);

  const backlinks = backlinksData?.notes ?? [];
  const outgoingLinks = outgoingData?.notes ?? [];
  const brokenLinks = outgoingData?.brokenLinks ?? [];

  if (isCollapsed) {
    return (
      <div className={`flex flex-col items-center py-4 ${className}`}>
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          title="Expand graph panel"
        >
          <svg
            className="w-5 h-5 text-gray-500 dark:text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
        </button>
        <div className="mt-4 flex flex-col items-center gap-2">
          <div className="flex flex-col items-center text-xs text-gray-500 dark:text-gray-400">
            <svg
              className="w-5 h-5 mb-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 16l-4-4m0 0l4-4m-4 4h18"
              />
            </svg>
            <span>{backlinks.length}</span>
          </div>
          <div className="flex flex-col items-center text-xs text-gray-500 dark:text-gray-400">
            <svg
              className="w-5 h-5 mb-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17 8l4 4m0 0l-4 4m4-4H3"
              />
            </svg>
            <span>{outgoingLinks.length}</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full bg-white dark:bg-gray-900 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2">
          <svg
            className="w-5 h-5 text-gray-500 dark:text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
            />
          </svg>
          <h2 className="text-sm font-semibold text-gray-900 dark:text-white">
            Links
          </h2>
        </div>
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            title="Collapse panel"
          >
            <svg
              className="w-4 h-4 text-gray-500 dark:text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>
        )}
      </div>

      {/* Content */}
      {!noteId ? (
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-sm text-gray-400 dark:text-gray-500 text-center">
            Select a note to see its links
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          {/* Backlinks Section */}
          <LinkSection
            title="Backlinks"
            icon={
              <svg
                className="w-4 h-4 text-blue-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16l-4-4m0 0l4-4m-4 4h18"
                />
              </svg>
            }
            links={backlinks}
            isLoading={backlinksLoading}
            error={backlinksError as Error | null}
            onNavigateToNote={onNavigateToNote}
            emptyMessage="No notes link to this note"
          />

          {/* Outgoing Links Section */}
          <LinkSection
            title="Outgoing Links"
            icon={
              <svg
                className="w-4 h-4 text-green-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17 8l4 4m0 0l-4 4m4-4H3"
                />
              </svg>
            }
            links={outgoingLinks}
            isLoading={outgoingLoading}
            error={outgoingError as Error | null}
            onNavigateToNote={onNavigateToNote}
            emptyMessage="This note doesn't link to other notes"
          />

          {/* Broken Links Section */}
          {brokenLinks.length > 0 && (
            <div className="border-b border-gray-200 dark:border-gray-700">
              <div className="px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-2">
                <svg
                  className="w-4 h-4 text-yellow-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                <span>Broken Links</span>
                <span className="text-xs text-gray-400 dark:text-gray-500 ml-1">
                  ({brokenLinks.length})
                </span>
              </div>
              <div className="px-3 pb-2">
                {brokenLinks.map((path) => (
                  <div
                    key={path}
                    className="text-xs text-yellow-600 dark:text-yellow-400 p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg mb-1"
                  >
                    {path}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
