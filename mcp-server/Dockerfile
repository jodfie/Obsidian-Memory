# MCP Server Dockerfile for Obsidian-Memory
FROM oven/bun:1 AS base

WORKDIR /app

# Install dependencies
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

# Copy source code
COPY . .

# Build
RUN bun run build

# Production stage
FROM oven/bun:1-slim AS prod

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy built files and dependencies
COPY --from=base /app/dist ./dist
COPY --from=base /app/node_modules ./node_modules
COPY --from=base /app/package.json ./

# Expose MCP SSE port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Run MCP server with Streamable HTTP transport
ENV MCP_TRANSPORT=sse
ENV MCP_SSE_PORT=3000
ENV MCP_PATH=/mcp
ENV OBSIDIAN_MEMORY_API_URL=http://memory:8765
ENV NODE_ENV=production

CMD ["bun", "run", "dist/index.js"]
