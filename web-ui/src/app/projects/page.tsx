'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  listProjects,
  getProjectNotes,
  type Project,
  type ProjectNote,
} from '../../lib/api';

export default function ProjectsPage() {
  const searchParams = useSearchParams();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | null>(
    searchParams?.get('project') || null
  );
  const [projectNotes, setProjectNotes] = useState<ProjectNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    if (selectedProject) {
      loadProjectNotes(selectedProject);
    }
  }, [selectedProject]);

  async function loadProjects() {
    try {
      setLoading(true);
      setError(null);
      const response = await listProjects();
      setProjects(response.projects);
      const first = response.projects[0];
      if (first && !selectedProject) {
        setSelectedProject(first.name);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  }

  async function loadProjectNotes(projectName: string) {
    try {
      setError(null);
      const response = await getProjectNotes(projectName);
      setProjectNotes(response.notes);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to load project notes'
      );
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading projects...</div>
      </div>
    );
  }

  if (error && !projects.length) {
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
          Projects
        </h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Projects List */}
          <div className="lg:col-span-1">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
              <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                  All Projects
                </h2>
              </div>
              <div className="p-6">
                {projects.length === 0 ? (
                  <p className="text-gray-500 dark:text-gray-400">
                    No projects yet
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {projects.map((project) => (
                      <li key={project.name}>
                        <button
                          onClick={() => setSelectedProject(project.name)}
                          className={`w-full text-left px-4 py-3 rounded-lg transition ${
                            selectedProject === project.name
                              ? 'bg-blue-100 dark:bg-blue-900 text-blue-900 dark:text-blue-100'
                              : 'hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-900 dark:text-white'
                          }`}
                        >
                          <div className="font-medium">{project.name}</div>
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {project.note_count} notes
                          </div>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>

          {/* Project Notes */}
          <div className="lg:col-span-2">
            {selectedProject ? (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                    {selectedProject}
                  </h2>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    {projectNotes.length} notes
                  </p>
                </div>
                <div className="p-6">
                  {projectNotes.length === 0 ? (
                    <p className="text-gray-500 dark:text-gray-400">
                      No notes in this project
                    </p>
                  ) : (
                    <div className="space-y-4">
                      {projectNotes.map((note) => (
                        <Link
                          key={note.note_id}
                          href={`/notes/${note.note_id}`}
                          className="block p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition"
                        >
                          <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                            {note.title}
                          </h3>
                          <div className="text-sm text-gray-500 dark:text-gray-400">
                            {note.note_type}
                            {note.updated_at && (
                              <span className="ml-2">
                                • Updated:{' '}
                                {new Date(note.updated_at).toLocaleDateString()}
                              </span>
                            )}
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-12 text-center">
                <p className="text-gray-500 dark:text-gray-400">
                  Select a project to view its notes
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
