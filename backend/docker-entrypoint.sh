#!/bin/bash
set -euo pipefail

# Docker entrypoint script for Obsidian-Memory
# Handles environment-specific startup logic

echo "Starting Obsidian-Memory..."

# Create data directory if it doesn't exist
mkdir -p /data/.obsidian-memory
mkdir -p /data/.obsidian-memory/logs

# Set permissions
chown -R appuser:appuser /data/.obsidian-memory 2>/dev/null || true

# Export environment variables for Python
export BASIC_MEMORY_HOME="${BASIC_MEMORY_HOME:-/data}"
export BASIC_MEMORY_SYNC_CHANGES="${BASIC_MEMORY_SYNC_CHANGES:-true}"
export BASIC_MEMORY_SYNC_DELAY="${BASIC_MEMORY_SYNC_DELAY:-1000}"

# Log startup info
echo "Environment: ${ENVIRONMENT:-production}"
echo "Log Level: ${LOG_LEVEL:-INFO}"
echo "Data Directory: ${BASIC_MEMORY_HOME"

# Health check function
health_check() {
    curl -f http://localhost:8765/health > /dev/null 2>&1
}

# Wait for application to be ready
if [ "${WAIT_FOR_HEALTH:-false}" = "true" ]; then
    echo "Waiting for application to be healthy..."
    for i in {1..30}; do
        if health_check; then
            echo "Application is healthy"
            break
        fi
        sleep 1
    done
fi

# Execute the command
exec "$@"
