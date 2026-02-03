'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getSessionContext, type SessionContext } from '../../../lib/api';

export default function SessionDetailPage() {
  const params = useParams();
  const sessionId = params.id as string;
  const [session, setSession] = useState<SessionContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (sessionId) {
      loadSession();
    }
  }, [sessionId]);

  async function loadSession() {
    try {
      setLoading(true);
      setError(null);
      const data = await getSessionContext({
        session_id: sessionId,
        include_events: true,
        include_summary: true,
        limit: 100,
      });
      setSession(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading session...</div>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-red-600">Error: {error || 'Session not found'}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <Link
            href="/sessions"
            className="text-blue-600 dark:text-blue-400 hover:underline mb-4 inline-block"
          >
            ← Back to Sessions
          </Link>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Session: {session.session_id.substring(0, 12)}...
          </h1>
        </div>

        {/* Session Info */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                Status
              </div>
              <span
                className={`px-2 py-1 rounded text-sm font-medium ${
                  session.status === 'active'
                    ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                    : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                }`}
              >
                {session.status}
              </span>
            </div>
            <div>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                Project
              </div>
              <div className="text-gray-900 dark:text-white">
                {session.project || 'None'}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                Started
              </div>
              <div className="text-gray-900 dark:text-white">
                {new Date(session.started_at).toLocaleString()}
              </div>
            </div>
            {session.ended_at && (
              <div>
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  Ended
                </div>
                <div className="text-gray-900 dark:text-white">
                  {new Date(session.ended_at).toLocaleString()}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Summary */}
        {session.summary && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Summary
            </h2>
            <div className="prose dark:prose-invert max-w-none">
              <p className="text-gray-700 dark:text-gray-300 mb-4">
                {session.summary.summary_text}
              </p>
              {session.summary?.key_learnings?.length ? (
                <div className="mb-4">
                  <h3 className="font-semibold mb-2">Key Learnings</h3>
                  <ul className="list-disc list-inside">
                    {session.summary.key_learnings.map((learning, idx) => (
                      <li key={idx}>{learning}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {session.summary?.decisions?.length ? (
                <div className="mb-4">
                  <h3 className="font-semibold mb-2">Decisions</h3>
                  <ul className="list-disc list-inside">
                    {session.summary.decisions.map((decision, idx) => (
                      <li key={idx}>{decision}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          </div>
        )}

        {/* Events Timeline */}
        {session.events && session.events.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Events ({session.events.length})
            </h2>
            <div className="space-y-4">
              {session.events.map((event, idx) => (
                <div
                  key={idx}
                  className="border-l-4 border-blue-500 pl-4 py-2"
                >
                  <div className="flex justify-between items-start mb-1">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {event.event_type}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {new Date(event.timestamp).toLocaleString()}
                    </span>
                  </div>
                  <div className="text-sm text-gray-700 dark:text-gray-300">
                    {event.content}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
