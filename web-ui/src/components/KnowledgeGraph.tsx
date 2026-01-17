'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getGraph, type GraphNode } from '../lib/api';

// Simple SVG-based graph visualization
// In production, would use a library like react-force-graph-2d or D3.js

export default function KnowledgeGraph() {
  const [graphData, setGraphData] = useState<{
    nodes: GraphNode[];
    links: Array<{ source: number; target: number; type: string }>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  useEffect(() => {
    loadGraph();
  }, []);

  async function loadGraph() {
    try {
      setLoading(true);
      setError(null);
      const graph = await getGraph();

      // Transform edges to links format
      const links = graph.edges.map((edge) => ({
        source: edge.source,
        target: edge.target,
        type: edge.type,
      }));

      setGraphData({
        nodes: graph.nodes,
        links: links,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }

  function handleNodeClick(node: GraphNode) {
    setSelectedNode(node);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading graph...</div>
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

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-500">No graph data available</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Knowledge Graph
          </h1>
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {graphData.nodes.length} nodes, {graphData.links.length} edges
          </div>
        </div>
      </div>

      {/* Graph Visualization */}
      <div className="flex-1 relative bg-white dark:bg-gray-800 overflow-auto">
        {graphData && (
          <div className="p-8">
            <div className="text-center mb-8">
              <p className="text-gray-500 dark:text-gray-400 mb-4">
                Graph visualization with {graphData.nodes.length} nodes and{' '}
                {graphData.links.length} edges
              </p>
              <p className="text-sm text-gray-400 dark:text-gray-500">
                Full interactive visualization requires graph library (e.g.,
                react-force-graph-2d, D3.js, or vis.js)
              </p>
            </div>

            {/* Simple node list view */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {graphData.nodes.map((node) => (
                <div
                  key={node.id}
                  onClick={() => handleNodeClick(node)}
                  className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer transition"
                >
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                    {node.title}
                  </h3>
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    Type: {node.note_type}
                  </div>
                  {node.project && (
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      Project: {node.project}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Sidebar with selected node info */}
      {selectedNode && (
        <div className="absolute right-0 top-0 bottom-0 w-80 bg-white dark:bg-gray-800 border-l border-gray-200 dark:border-gray-700 p-6 overflow-y-auto">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              {selectedNode.title}
            </h2>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              ×
            </button>
          </div>
          <div className="space-y-4">
            <div>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                Type
              </div>
              <div className="text-gray-900 dark:text-white">
                {selectedNode.note_type}
              </div>
            </div>
            {selectedNode.project && (
              <div>
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  Project
                </div>
                <div className="text-gray-900 dark:text-white">
                  {selectedNode.project}
                </div>
              </div>
            )}
            {selectedNode.tags.length > 0 && (
              <div>
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  Tags
                </div>
                <div className="flex flex-wrap gap-2 mt-1">
                  {selectedNode.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded text-sm"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <div>
              <Link
                href={`/notes/${selectedNode.id}`}
                className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
              >
                View Note
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
