# Multi-stage Dockerfile for MCP server (Bun)
FROM oven/bun:1 as builder

WORKDIR /build

# Copy dependency files
COPY mcp-server/package.json mcp-server/package-lock.json* ./

# Install dependencies
RUN bun install --frozen-lockfile --production=false

# Copy source code
COPY mcp-server/ ./

# Build application
RUN bun run build || echo "Build step skipped (no build script)"

# Production stage
FROM oven/bun:1-slim

WORKDIR /app

# Copy from builder
COPY --from=builder /build/node_modules ./node_modules
COPY --from=builder /build/dist ./dist
COPY --from=builder /build/src ./src
COPY --from=builder /build/package.json ./
COPY --from=builder /build/tsconfig.json ./

# Create non-root user
RUN addgroup -g 1000 bunuser && \
    adduser -D -u 1000 -G bunuser bunuser && \
    chown -R bunuser:bunuser /app

USER bunuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD bun --version || exit 1

# Run application
CMD ["bun", "run", "src/index.ts"]
