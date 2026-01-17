'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { listSessions, type Session } from '../../lib/api';

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterProject, setFilterProject] = useState<string>('');

  useEffect(() => {
    loadSessions();
  }, [filterProject]);

  async function loadSessions() {
    try {
      setLoading(true);
      setError(null);
      const response = await listSessions({
        project: filterProject || null,
        limit: 100,
      });
      setSessions(response.sessions);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load sessions');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading sessions...</div>
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
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-8 text-gray-900 dark:text-white">
          Session History
        </h1>

        {/* Filter */}
        <div className="mb-6">
          <input
            type="text"
            value={filterProject}
            onChange={(e) => setFilterProject(e.target.value)}
            placeholder="Filter by project..."
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Timeline View */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
          {sessions.length === 0 ? (
            <div className="p-12 text-center">
              <p className="text-gray-500 dark:text-gray-400">
                No sessions found
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200 dark:divide-gray-700">
              {sessions.map((session) => (
                <div
                  key={session.session_id}
                  className="p-6 hover:bg-gray-50 dark:hover:bg-gray-700 transition"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-semibold text-gray-900 dark:text-white">
                          {session.session_id.substring(0, 8)}...
                        </h3>
                        <span
                          className={`px-2 py-1 rounded text-xs font-medium ${
                            session.status === 'active'
                              ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                              : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                          }`}
                        >
                          {session.status}
                        </span>
                      </div>
                      <div className="text-sm text-gray-500 dark:text-gray-400 space-y-1">
                        {session.project && (
                          <div>Project: {session.project}</div>
                        )}
                        <div>
                          Started:{' '}
                          {new Date(session.started_at).toLocaleString()}
                        </div>
                        {session.ended_at && (
                          <div>
                            Ended:{' '}
                            {new Date(session.ended_at).toLocaleString()}
                          </div>
                        )}
                        <div>{session.event_count} events</div>
                      </div>
                    </div>
                    <div className="ml-4">
                      <Link
                        href={`/sessions/${session.session_id}`}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm"
                      >
                        View Details
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
