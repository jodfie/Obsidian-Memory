'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  listNotes,
  listProjects,
  listSessions,
  type Note,
  type Project,
  type Session,
} from '../lib/api';

export default function Dashboard() {
  const [recentNotes, setRecentNotes] = useState<Note[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [stats, setStats] = useState({
    totalNotes: 0,
    totalProjects: 0,
    activeSessions: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadDashboard() {
      try {
        setLoading(true);
        setError(null);

        // Load recent notes
        const notesResponse = await listNotes({ limit: 10 });
        setRecentNotes(notesResponse.notes);
        setStats((prev) => ({ ...prev, totalNotes: notesResponse.total }));

        // Load projects
        const projectsResponse = await listProjects();
        setProjects(projectsResponse.projects);
        setStats((prev) => ({
          ...prev,
          totalProjects: projectsResponse.projects.length,
        }));

        // Load recent sessions
        const sessionsResponse = await listSessions({ limit: 5 });
        setSessions(sessionsResponse.sessions);
        setStats((prev) => ({
          ...prev,
          activeSessions: sessionsResponse.sessions.filter(
            (s) => s.status === 'active'
          ).length,
        }));
      } catch (err) {
        setError(
          err instanceof Error ? err.message : 'Failed to load dashboard'
        );
      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading dashboard...</div>
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
          Dashboard
        </h1>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Total Notes
            </h3>
            <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
              {stats.totalNotes}
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Projects
            </h3>
            <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
              {stats.totalProjects}
            </p>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Active Sessions
            </h3>
            <p className="text-3xl font-bold text-gray-900 dark:text-white mt-2">
              {stats.activeSessions}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Recent Notes */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Recent Notes
              </h2>
            </div>
            <div className="p-6">
              {recentNotes.length === 0 ? (
                <p className="text-gray-500 dark:text-gray-400">
                  No notes yet
                </p>
              ) : (
                <ul className="space-y-4">
                  {recentNotes.map((note) => (
                    <li key={note.id}>
                      <Link
                        href={`/notes/${note.id}`}
                        className="block hover:bg-gray-50 dark:hover:bg-gray-700 p-3 rounded transition"
                      >
                        <h3 className="font-medium text-gray-900 dark:text-white">
                          {note.title}
                        </h3>
                        <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                          {note.project && (
                            <span className="mr-2">Project: {note.project}</span>
                          )}
                          {note.updated_at && (
                            <span>
                              Updated:{' '}
                              {new Date(note.updated_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-4">
                <Link
                  href="/notes"
                  className="text-blue-600 dark:text-blue-400 hover:underline"
                >
                  View all notes →
                </Link>
              </div>
            </div>
          </div>

          {/* Projects */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Projects
              </h2>
            </div>
            <div className="p-6">
              {projects.length === 0 ? (
                <p className="text-gray-500 dark:text-gray-400">
                  No projects yet
                </p>
              ) : (
                <ul className="space-y-3">
                  {projects.map((project) => (
                    <li key={project.name}>
                      <Link
                        href={`/projects/${project.name}`}
                        className="flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-700 p-3 rounded transition"
                      >
                        <span className="font-medium text-gray-900 dark:text-white">
                          {project.name}
                        </span>
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                          {project.note_count} notes
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Recent Sessions */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow lg:col-span-2">
            <div className="p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                Recent Sessions
              </h2>
            </div>
            <div className="p-6">
              {sessions.length === 0 ? (
                <p className="text-gray-500 dark:text-gray-400">
                  No sessions yet
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead>
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Session ID
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Project
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Status
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Events
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                          Started
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                      {sessions.map((session) => (
                        <tr key={session.session_id}>
                          <td className="px-4 py-3 text-sm text-gray-900 dark:text-white">
                            {session.session_id.substring(0, 8)}...
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                            {session.project || 'None'}
                          </td>
                          <td className="px-4 py-3 text-sm">
                            <span
                              className={`px-2 py-1 rounded text-xs font-medium ${
                                session.status === 'active'
                                  ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                                  : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                              }`}
                            >
                              {session.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                            {session.event_count}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                            {new Date(session.started_at).toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
