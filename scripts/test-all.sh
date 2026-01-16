#!/usr/bin/env bash
set -e

echo "Running backend tests..."
cd backend && pytest tests/ -v && cd ..

echo "Running MCP server tests..."
cd mcp-server && bun test && cd ..

echo "Running web UI tests..."
cd web-ui && npm test && cd ..

echo "All tests passed!"
