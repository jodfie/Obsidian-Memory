'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getNoteById, type Note } from '../../../lib/api';
import MarkdownEditor from '../../../components/MarkdownEditor';

export default function NoteDetailPage() {
  const params = useParams();
  const router = useRouter();
  const noteId = params.id ? parseInt(params.id as string, 10) : null;
  const [note, setNote] = useState<Note | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (noteId) {
      loadNote();
    }
  }, [noteId]);

  async function loadNote() {
    if (!noteId) return;

    try {
      setLoading(true);
      setError(null);
      const loadedNote = await getNoteById(noteId);
      setNote(loadedNote);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load note');
    } finally {
      setLoading(false);
    }
  }

  function handleSave(savedNote: Note) {
    setNote(savedNote);
    // Optionally show success message
  }

  function handleCancel() {
    router.push('/notes');
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading note...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-red-600">Error: {error}</div>
      </div>
    );
  }

  return (
    <MarkdownEditor
      noteId={noteId}
      initialTitle={note?.title || ''}
      initialContent={note?.content || ''}
      onSave={handleSave}
      onCancel={handleCancel}
    />
  );
}
