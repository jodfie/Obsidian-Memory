'use client';

import { useState } from 'react';

export default function SettingsPage() {
  const [apiUrl, setApiUrl] = useState(
    typeof window !== 'undefined'
      ? localStorage.getItem('api_url') || 'http://localhost:8000'
      : 'http://localhost:8000'
  );
  const [apiToken, setApiToken] = useState(
    typeof window !== 'undefined'
      ? localStorage.getItem('api_token') || ''
      : ''
  );

  function handleSave() {
    if (typeof window !== 'undefined') {
      localStorage.setItem('api_url', apiUrl);
      localStorage.setItem('api_token', apiToken);
      alert('Settings saved! Refresh the page for changes to take effect.');
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-8 text-gray-900 dark:text-white">
          Settings
        </h1>

        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">
            Configuration
          </h2>

          <div className="space-y-6">
            <div>
              <label
                htmlFor="api-url"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
              >
                API URL
              </label>
              <input
                id="api-url"
                type="text"
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="http://localhost:8000"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Backend API URL for Obsidian-Memory
              </p>
            </div>

            <div>
              <label
                htmlFor="api-token"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
              >
                API Token (Bearer)
              </label>
              <input
                id="api-token"
                type="password"
                value={apiToken}
                onChange={(e) => setApiToken(e.target.value)}
                placeholder="Optional: Bearer token for API authentication"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Bearer token for API authentication (if required by backend)
              </p>
            </div>

            <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
              <button
                onClick={handleSave}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
              >
                Save Settings
              </button>
            </div>
          </div>
        </div>

        <div className="mt-8 bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            About
          </h2>
          <div className="text-sm text-gray-600 dark:text-gray-400 space-y-2">
            <p>
              <strong>Obsidian-Memory</strong> - Unified memory management
              system for Claude Code
            </p>
            <p>Version: 0.1.0</p>
            <p>
              This web UI provides access to your Obsidian-Memory knowledge
              base, allowing you to browse notes, view the knowledge graph, and
              manage projects.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
