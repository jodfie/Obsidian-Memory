'use client';

import { useRouter } from 'next/navigation';
import MarkdownEditor from '../../../components/MarkdownEditor';
import { type Note } from '../../../lib/api';

export default function NewNotePage() {
  const router = useRouter();

  function handleSave(note: Note) {
    // Redirect to the note detail page after saving
    router.push(`/notes/${note.id}`);
  }

  function handleCancel() {
    router.push('/notes');
  }

  return (
    <MarkdownEditor
      onSave={handleSave}
      onCancel={handleCancel}
    />
  );
}
