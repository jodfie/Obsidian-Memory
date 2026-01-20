#!/bin/bash
set -euo pipefail

# Docker entrypoint script for Obsidian-Memory
# Handles environment-specific startup logic

echo "Starting Obsidian-Memory..."

# Create data directory if it doesn't exist
# Note: Directories are created in Dockerfile, but we ensure they exist here
# Volume mounts may override, so we try to create with current user permissions
mkdir -p /data/.obsidian-memory 2>/dev/null || true
mkdir -p /data/.obsidian-memory/logs 2>/dev/null || true

# Export environment variables for Python
export BASIC_MEMORY_HOME="${BASIC_MEMORY_HOME:-/data}"
export BASIC_MEMORY_SYNC_CHANGES="${BASIC_MEMORY_SYNC_CHANGES:-true}"
export BASIC_MEMORY_SYNC_DELAY="${BASIC_MEMORY_SYNC_DELAY:-1000}"

# Log startup info
echo "Environment: ${ENVIRONMENT:-production}"
echo "Log Level: ${LOG_LEVEL:-INFO}"
echo "Data Directory: ${BASIC_MEMORY_HOME:-/data}"

# Health check function
health_check() {
    curl -f http://localhost:8765/health > /dev/null 2>&1
}

# Execute the command in background if we need to wait for health
if [ "${WAIT_FOR_HEALTH:-false}" = "true" ]; then
    # Start the application
    "$@" &
    APP_PID=$!
    
    # Wait for application to be ready
    echo "Waiting for application to be healthy..."
    for i in {1..30}; do
        if health_check; then
            echo "Application is healthy"
            wait $APP_PID
            exit $?
        fi
        sleep 1
    done
    
    # If we get here, health check failed
    echo "Health check failed after 30 seconds"
    kill $APP_PID 2>/dev/null || true
    exit 1
else
    # Execute the command normally
    exec "$@"
fi
