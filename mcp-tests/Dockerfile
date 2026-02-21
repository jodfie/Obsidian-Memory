# MCP Server Testing Harness
# Pre-authenticated testing for CI/CD pipelines

FROM node:22-slim

LABEL maintainer="Obsidian-Memory contributors"
LABEL description="MCP Server E2E Testing Harness with pre-auth support"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install MCP Inspector globally
RUN npm install -g @modelcontextprotocol/inspector mcp-remote

# Create app directory
WORKDIR /app

# Create package.json and install SDK locally for scripts
RUN echo '{"type": "module", "dependencies": {"@modelcontextprotocol/sdk": "^1.0.0"}}' > package.json && npm install

# Copy test scripts and config
COPY scripts/ ./scripts/
COPY tests/ ./tests/
COPY config/ ./config/

# Make scripts executable
RUN chmod +x scripts/*.sh

# Create directory for auth tokens (will be mounted or injected)
RUN mkdir -p /root/.mcp-auth

# Environment variables for configuration
ENV MCP_SERVER_URL=""
ENV MCP_ACCESS_TOKEN=""
ENV MCP_REFRESH_TOKEN=""
ENV TEST_TIMEOUT=30000
ENV TEST_OUTPUT_DIR=/app/results

# Create results directory
RUN mkdir -p /app/results

# Health check - verify MCP Inspector is available
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD npx @modelcontextprotocol/inspector --version || exit 1

# Default command runs the test suite
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["run-tests"]
