# Changelog

All notable changes to Obsidian-Memory will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive documentation suite (8 new docs, 3,120+ lines)
- Quick Start guide for 5-minute setup
- Architecture deep dive with component diagrams
- Claude.ai integration guide with OAuth credentials
- AI model quick reference card
- Complete troubleshooting guide (9 categories)
- Contributing guide for developers
- Documentation summary and index

### Fixed
- OAuth endpoints in MCP integration guide (authorize endpoint, not login)
- MCP server URL documentation (corrected to `/mcp` from `/mcp/sse`)
- Auth middleware skip paths for OAuth discovery endpoints

### Changed
- Enhanced README documentation section with user-type navigation
- Updated docker-compose.prod.yml with vault mount (rw permissions)

## [0.1.0] - 2026-01-XX

### Added
- Initial release
- Multi-vault support for Obsidian vaults
- Knowledge graph construction from wikilinks
- Full-text search with SQLite FTS5
- AI-powered entity extraction and relation inference
- Session tracking with automatic summarization
- Project management and context switching
- Git-based cross-device synchronization
- Web UI for note browsing and editing
- MCP server with 13 tools:
  * Memory tools (mem_read, mem_write, mem_search, mem_supersede)
  * Graph tools (graph_traverse, graph_similar)
  * Project tools (project_list, project_switch, project_create)
  * Session tools (session_observe, session_summary, session_context)
  * Context tools (build_context)
- Three transport modes:
  * stdio (Claude Code local)
  * SSE (Claude.ai remote)
  * Streamable HTTP (Cursor)
- Multiple authentication methods:
  * Bearer token
  * Cloudflare Access JWT
  * OAuth 2.0 with PKCE
- FastAPI backend with middleware chain:
  * Request validation
  * Rate limiting
  * Cloudflare Access integration
  * Authentication
  * CORS support
- Docker deployment with docker-compose
- Cloudflare Tunnel integration
- Health check and metrics endpoints
- Structured logging with rotation

### Security
- Path traversal protection
- Request size limits
- Non-root Docker containers
- Atomic file writes
- Token-based authentication
- OAuth 2.0 with PKCE support

---

## Release Notes Format

### Version Number Scheme

`MAJOR.MINOR.PATCH` following Semantic Versioning:

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Categories

- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security fixes and improvements

### Examples

#### Major Release (Breaking Changes)
```markdown
## [2.0.0] - 2026-XX-XX

### Changed
- **BREAKING**: Renamed MCP tool `mem_read` to `memory_read`
- **BREAKING**: Changed API endpoint `/api/notes` to `/api/v2/notes`

### Removed
- **BREAKING**: Removed deprecated `session_list` tool

### Migration Guide
See [MIGRATION.md](MIGRATION.md) for upgrade instructions.
```

#### Minor Release (New Features)
```markdown
## [1.1.0] - 2026-XX-XX

### Added
- New MCP tool: `mem_archive` for archiving old notes
- Support for PostgreSQL as alternative to SQLite
- Bulk note import API endpoint
- Graph visualization in Web UI

### Changed
- Improved search ranking algorithm
- Enhanced error messages in API responses

### Fixed
- Memory leak in session tracking
- Graph traversal infinite loop bug
```

#### Patch Release (Bug Fixes)
```markdown
## [1.0.1] - 2026-XX-XX

### Fixed
- Vault permission errors in Docker (UID mismatch)
- OAuth token refresh failing after 24 hours
- Search index not updating for new notes
- MCP server crash on invalid input

### Security
- Updated dependencies to fix CVE-2024-XXXXX
```

---

## Maintenance Notes

### For Maintainers

When preparing a release:

1. **Update this file** with all changes since last release
2. **Choose version number** based on change types
3. **Write release notes** using categories above
4. **Update version** in:
   - `backend/pyproject.toml`
   - `mcp-server/package.json`
   - `web-ui/package.json`
5. **Create git tag**: `git tag -a v1.2.0 -m "Release v1.2.0"`
6. **Push tag**: `git push origin v1.2.0`
7. **Create GitHub release** with changelog excerpt
8. **Build and push Docker images** (automated via CI)

### Versioning Policy

- **Patch releases**: Every 1-2 weeks for bug fixes
- **Minor releases**: Monthly or when significant features added
- **Major releases**: As needed for breaking changes (avoid if possible)

---

## Links

- [GitHub Repository](https://github.com/jodfie/Obsidian-Memory)
- [Documentation](https://github.com/jodfie/Obsidian-Memory/tree/main/docs)
- [Contributing Guide](CONTRIBUTING.md)
- [License](LICENSE)

---

*This changelog is automatically included in GitHub releases.*
