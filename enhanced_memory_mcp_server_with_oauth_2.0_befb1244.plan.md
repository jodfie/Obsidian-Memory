---
name: Enhanced Memory MCP Server with Supabase & OAuth 2.0
overview: Enhance the existing cc-obsidian-mem MCP server by integrating basic-memory knowledge graph features (semantic parsing, memory:// URLs, bidirectional sync) using Supabase for cloud sync and multi-device support, with Supabase Auth as primary authentication and custom OAuth 2.0 as fallback, following MCP best practices from awesome-claude-code.
todos:
  - id: supabase-setup
    content: "Phase 1: Set up Supabase - database schema, migrations, Supabase client, Row Level Security policies"
    status: pending
  - id: kg-foundation
    content: "Phase 2: Build knowledge graph foundation - PostgreSQL schema, Markdown parser, entity extraction, real-time sync"
    status: pending
  - id: auth-implementation
    content: "Phase 3: Implement authentication - Supabase Auth integration, custom OAuth 2.0 fallback, token validation"
    status: pending
  - id: new-mcp-tools
    content: "Phase 4: Add new MCP tools - build_context, canvas, recent_activity, enhance mem_search/mem_write with graph support"
    status: pending
  - id: integration-testing
    content: "Phase 5: Integration - hook lifecycle integration, setup wizard updates, migration system, comprehensive testing"
    status: pending
  - id: documentation
    content: "Phase 6: Documentation - Supabase setup guide, knowledge graph guide, authentication setup, deployment updates"
    status: pending
---

