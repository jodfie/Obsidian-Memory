'use client';

/**
 * TipTap WYSIWYG Editor with Markdown support.
 *
 * Features:
 * - WYSIWYG editing with Notion-like aesthetic
 * - Markdown input/output (content stored as markdown in DB)
 * - Wikilink [[link]] syntax support
 * - Autosave with 2-second debounce
 * - Formatting toolbar
 */

import { useEditor, EditorContent, Extension } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import Typography from '@tiptap/extension-typography';
import { Markdown } from 'tiptap-markdown';
import { useState, useEffect, useCallback, useRef } from 'react';
import { Mark, mergeAttributes } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';
import EditorToolbar from './EditorToolbar';

// ============================================================================
// Wikilink Extension
// ============================================================================

/**
 * Custom extension to handle Obsidian-style [[wikilinks]].
 * Renders wikilinks as styled spans that can be clicked to navigate.
 */
const WikilinkMark = Mark.create({
  name: 'wikilink',
  priority: 1000,

  addAttributes() {
    return {
      target: {
        default: null,
      },
    };
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-wikilink]',
      },
    ];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-wikilink': HTMLAttributes.target,
        class:
          'wikilink bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-1 rounded cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors',
      }),
      0,
    ];
  },
});

/**
 * Extension that decorates [[wikilinks]] in the editor view.
 * This uses decorations rather than marks to preserve the raw markdown syntax.
 */
const WikilinkDecorator = Extension.create({
  name: 'wikilinkDecorator',

  addProseMirrorPlugins() {
    const wikilinkRegex = /\[\[([^\]]+)\]\]/g;

    return [
      new Plugin({
        key: new PluginKey('wikilinkDecorator'),
        props: {
          decorations: (state) => {
            const { doc } = state;
            const decorations: Decoration[] = [];

            doc.descendants((node, pos) => {
              if (!node.isText || !node.text) return;

              const text = node.text;
              let match;

              while ((match = wikilinkRegex.exec(text)) !== null) {
                const start = pos + match.index;
                const end = start + match[0].length;

                decorations.push(
                  Decoration.inline(start, end, {
                    class:
                      'wikilink-decoration bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/50 transition-colors',
                    'data-wikilink-target': match[1],
                  })
                );
              }
            });

            return DecorationSet.create(doc, decorations);
          },
        },
      }),
    ];
  },
});

// ============================================================================
// Types
// ============================================================================

interface TipTapEditorProps {
  /** Initial markdown content */
  initialContent?: string;
  /** Callback when content changes (returns markdown) */
  onChange?: (markdown: string) => void;
  /** Callback for autosave (returns markdown) */
  onAutoSave?: (markdown: string) => void;
  /** Autosave debounce delay in ms (default: 2000) */
  autoSaveDelay?: number;
  /** Placeholder text when editor is empty */
  placeholder?: string;
  /** Whether the editor is read-only */
  readOnly?: boolean;
  /** Additional class names for the container */
  className?: string;
  /** Callback when a wikilink is clicked */
  onWikilinkClick?: (target: string) => void;
}

// ============================================================================
// Component
// ============================================================================

export default function TipTapEditor({
  initialContent = '',
  onChange,
  onAutoSave,
  autoSaveDelay = 2000,
  placeholder = 'Start writing...',
  readOnly = false,
  className = '',
  onWikilinkClick,
}: TipTapEditorProps) {
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastContentRef = useRef<string>(initialContent);

  // Initialize the editor
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Configure heading levels
        heading: {
          levels: [1, 2, 3, 4, 5, 6],
        },
        // Enable code blocks with syntax highlighting placeholder
        codeBlock: {
          HTMLAttributes: {
            class: 'bg-gray-100 dark:bg-gray-800 rounded-lg p-4 font-mono text-sm overflow-x-auto',
          },
        },
        // Configure blockquote styling
        blockquote: {
          HTMLAttributes: {
            class: 'border-l-4 border-gray-300 dark:border-gray-600 pl-4 italic text-gray-600 dark:text-gray-400',
          },
        },
        // Configure code styling
        code: {
          HTMLAttributes: {
            class: 'bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded font-mono text-sm',
          },
        },
      }),
      Link.configure({
        openOnClick: false,
        HTMLAttributes: {
          class: 'text-blue-600 dark:text-blue-400 underline hover:text-blue-800 dark:hover:text-blue-300',
        },
      }),
      Placeholder.configure({
        placeholder,
        emptyEditorClass: 'is-editor-empty',
      }),
      Typography,
      Markdown.configure({
        html: false,
        transformPastedText: true,
        transformCopiedText: true,
      }),
      WikilinkDecorator,
    ],
    content: initialContent,
    editable: !readOnly,
    editorProps: {
      attributes: {
        class: 'prose prose-gray dark:prose-invert max-w-none focus:outline-none min-h-[200px]',
      },
      handleClick: (_view, _pos, event) => {
        // Handle wikilink clicks
        const target = event.target as HTMLElement;
        const wikilinkTarget = target.getAttribute('data-wikilink-target');
        if (wikilinkTarget && onWikilinkClick) {
          onWikilinkClick(wikilinkTarget);
          return true;
        }
        return false;
      },
    },
    onUpdate: ({ editor }) => {
      const markdown = editor.storage.markdown.getMarkdown();

      // Call onChange immediately
      if (onChange) {
        onChange(markdown);
      }

      // Schedule autosave with debounce
      if (onAutoSave && markdown !== lastContentRef.current) {
        if (saveTimeoutRef.current) {
          clearTimeout(saveTimeoutRef.current);
        }

        saveTimeoutRef.current = setTimeout(() => {
          setIsSaving(true);
          onAutoSave(markdown);
          lastContentRef.current = markdown;
          setLastSaved(new Date());
          setIsSaving(false);
        }, autoSaveDelay);
      }
    },
  });

  // Update editor content when initialContent changes
  useEffect(() => {
    if (editor && initialContent !== lastContentRef.current) {
      editor.commands.setContent(initialContent);
      lastContentRef.current = initialContent;
    }
  }, [editor, initialContent]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, []);

  /**
   * Gets the current content as markdown.
   * Can be called by parent components via ref or callback.
   */
  const getMarkdown = useCallback((): string => {
    if (!editor) return '';
    return editor.storage.markdown.getMarkdown();
  }, [editor]);

  /**
   * Manually trigger a save.
   */
  const save = useCallback(() => {
    if (!editor || !onAutoSave) return;
    const markdown = editor.storage.markdown.getMarkdown();
    setIsSaving(true);
    onAutoSave(markdown);
    lastContentRef.current = markdown;
    setLastSaved(new Date());
    setIsSaving(false);
  }, [editor, onAutoSave]);

  /**
   * Focus the editor.
   */
  const focus = useCallback(() => {
    editor?.commands.focus();
  }, [editor]);

  return (
    <div className={`flex flex-col bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden ${className}`}>
      {/* Toolbar */}
      {!readOnly && <EditorToolbar editor={editor} />}

      {/* Editor content */}
      <div className="flex-1 overflow-y-auto">
        <EditorContent
          editor={editor}
          className="p-6 [&_.is-editor-empty:first-child::before]:content-[attr(data-placeholder)] [&_.is-editor-empty:first-child::before]:text-gray-400 [&_.is-editor-empty:first-child::before]:dark:text-gray-500 [&_.is-editor-empty:first-child::before]:float-left [&_.is-editor-empty:first-child::before]:h-0 [&_.is-editor-empty:first-child::before]:pointer-events-none"
        />
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-xs text-gray-500 dark:text-gray-400">
        <div className="flex items-center gap-4">
          {isSaving && (
            <span className="flex items-center gap-1">
              <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Saving...
            </span>
          )}
          {!isSaving && lastSaved && (
            <span>Last saved {formatTimeAgo(lastSaved)}</span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <span>{editor?.storage.characterCount?.characters?.() ?? 0} characters</span>
          <span>{editor?.storage.characterCount?.words?.() ?? 0} words</span>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

/**
 * Formats a date as a relative time string (e.g., "2 minutes ago").
 */
function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);

  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds} seconds ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes === 1) return '1 minute ago';
  if (minutes < 60) return `${minutes} minutes ago`;

  const hours = Math.floor(minutes / 60);
  if (hours === 1) return '1 hour ago';
  if (hours < 24) return `${hours} hours ago`;

  const days = Math.floor(hours / 24);
  if (days === 1) return 'yesterday';
  return `${days} days ago`;
}

// ============================================================================
// Export hook for advanced usage
// ============================================================================

export { useEditor } from '@tiptap/react';
export type { Editor } from '@tiptap/react';
