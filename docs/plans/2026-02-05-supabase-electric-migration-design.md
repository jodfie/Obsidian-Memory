# Supabase + ElectricSQL Migration Design

**Date:** 2026-02-05
**Status:** Draft
**Author:** Claude + redleif

---

## Overview

Migrate Obsidian-Memory from local SQLite + file-based storage to Supabase Postgres with ElectricSQL sync for offline-capable clients.

### Goals

1. **Multi-device sync** - Access memories from any device
2. **Web access** - Use from any browser without running local server
3. **Offline support** - Desktop/mobile apps work without connectivity
4. **Obsidian compatibility** - Export to .md files on demand

### Non-Goals

- Real-time collaboration (multi-user editing same note)
- Full offline for web browsers (requires connectivity)

---

## Architecture

### High-Level View

```
┌─────────────────────────────────────────────────────────────────┐
│                        Clients                                  │
├─────────────────┬─────────────────┬─────────────────────────────┤
│   Desktop       │   Mobile        │   Web Browser               │
│  (Electron)     │  (PWA/Native)   │                             │
│                 │                 │                             │
│  ┌───────────┐  │  ┌───────────┐  │  ┌───────────────────────┐  │
│  │  SQLite   │  │  │  SQLite   │  │  │  TanStack Query       │  │
│  │  (local)  │  │  │  (local)  │  │  │  + Supabase Realtime  │  │
│  └─────┬─────┘  │  └─────┬─────┘  │  └───────────┬───────────┘  │
│        │        │        │        │              │              │
│        │ Electric Sync   │        │              │ Direct       │
└────────┼────────┴────────┼────────┴──────────────┼──────────────┘
         │                 │                       │
         └────────┬────────┘                       │
                  ▼                                │
       ┌─────────────────────┐                     │
       │   Electric Sync     │                     │
       │   (Elixir service)  │                     │
       └──────────┬──────────┘                     │
                  │ Logical replication            │
                  ▼                                ▼
       ┌───────────────────────────────────────────────┐
       │              Supabase                         │
       │  ┌─────────────────────────────────────────┐  │
       │  │  Postgres (source of truth)             │  │
       │  ├─────────────────────────────────────────┤  │
       │  │  Auth (OAuth - already implemented)     │  │
       │  ├─────────────────────────────────────────┤  │
       │  │  Realtime (WebSocket subscriptions)     │  │
       │  └─────────────────────────────────────────┘  │
       └───────────────────────────────────────────────┘
```

### Client Strategy

| Client | Local Database | Sync Method | Offline Support |
|--------|---------------|-------------|-----------------|
| Web UI (browser) | None | Supabase direct + Realtime | No (requires internet) |
| Desktop (Electron) | SQLite | ElectricSQL | Yes |
| Mobile (PWA/Native) | SQLite/PGlite | ElectricSQL | Yes |

---

## Data Model

### Postgres Schema

```sql
-- Core notes table (replaces .md files)
CREATE TABLE notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    path TEXT NOT NULL UNIQUE,        -- e.g., "projects/obsidian-memory/design.md"
    title TEXT NOT NULL,
    content TEXT NOT NULL,            -- markdown body
    frontmatter JSONB DEFAULT '{}',   -- YAML metadata as JSON
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    user_id UUID REFERENCES auth.users(id)
);

-- Extracted relations (wikilinks, tags)
CREATE TABLE relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES notes(id) ON DELETE CASCADE,
    target_path TEXT NOT NULL,        -- path of linked note
    relation_type TEXT NOT NULL,      -- 'wikilink', 'tag', 'observation'
    context TEXT                      -- surrounding text for context
);

-- Sessions (Claude Code interactions)
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    ended_at TIMESTAMPTZ,
    summary TEXT,
    events JSONB DEFAULT '[]'
);

-- Full-text search index
CREATE INDEX notes_fts ON notes
    USING gin(to_tsvector('english', title || ' ' || content));

-- Performance indexes
CREATE INDEX notes_user_id ON notes(user_id);
CREATE INDEX notes_path ON notes(path);
CREATE INDEX notes_updated_at ON notes(updated_at DESC);
CREATE INDEX relations_source_id ON relations(source_id);
CREATE INDEX relations_target_path ON relations(target_path);
```

### Key Changes from Current SQLite

| Aspect | Current (SQLite) | New (Postgres) |
|--------|-----------------|----------------|
| Note content | .md files on disk | `notes.content` column |
| Frontmatter | Parsed on read | `notes.frontmatter` JSONB |
| Search | SQLite FTS5 | Postgres `to_tsvector` |
| User isolation | Single user | `user_id` foreign key |
| IDs | Integer autoincrement | UUID |

---

## Electric Sync Configuration

Electric uses "shapes" to define what data syncs to each client.

```typescript
// lib/electric-shapes.ts

import { ShapeStream } from '@electric-sql/client'

const ELECTRIC_URL = process.env.ELECTRIC_URL

export function createNotesShape(userId: string) {
  return new ShapeStream({
    url: `${ELECTRIC_URL}/v1/shape`,
    params: {
      table: 'notes',
      where: `user_id = '${userId}'`,
    }
  })
}

export function createRelationsShape(userId: string) {
  return new ShapeStream({
    url: `${ELECTRIC_URL}/v1/shape`,
    params: {
      table: 'relations',
      where: `source_id IN (SELECT id FROM notes WHERE user_id = '${userId}')`
    }
  })
}

export function createSessionsShape(userId: string) {
  return new ShapeStream({
    url: `${ELECTRIC_URL}/v1/shape`,
    params: {
      table: 'sessions',
      where: `started_at > now() - interval '30 days'`
    }
  })
}
```

### Sync Behavior

| Scenario | Behavior |
|----------|----------|
| Edit note offline | Saved to local SQLite, syncs on reconnect |
| Same note edited on two devices | Electric merges via CRDT, no data loss |
| New note created offline | Gets server UUID on sync |
| Delete note | Propagates to all devices |
| Conflict detected | Auto-merged if possible, flagged if not |

---

## Backend Changes

### New Dependencies

```toml
# pyproject.toml additions
[project]
dependencies = [
    # ... existing ...
    "asyncpg>=0.29.0",           # Async Postgres driver
    "sqlalchemy[asyncio]>=2.0",  # ORM with async support
]
```

### Service Layer Changes

| Service | Current | New |
|---------|---------|-----|
| `vault_manager.py` | Reads .md files from disk | Reads from `notes` table |
| `search_index.py` | SQLite FTS5 | Postgres `to_tsvector` |
| `graph_engine.py` | Parses files for links | Reads `relations` table |
| **NEW** `obsidian_exporter.py` | - | Exports DB → .md files on demand |
| **NEW** `db.py` | - | SQLAlchemy async session management |

### Dual-Mode Support (Migration Period)

```python
# app/config.py
from enum import Enum

class DatabaseMode(str, Enum):
    SQLITE = "sqlite"
    POSTGRES = "postgres"

class Settings(BaseSettings):
    db_mode: DatabaseMode = DatabaseMode.SQLITE
    database_url: str = ""  # Postgres connection string
    # ... existing settings ...
```

---

## Web UI Changes

### Data Layer Replacement

```
CURRENT                              NEW
─────────────────────────────────────────────────────────────────
lib/api.ts                           lib/supabase-client.ts
  → fetch('/api/notes')                → supabase.from('notes')
  → HTTP to FastAPI                    → Direct to Supabase
  → Manual refetch                     → Realtime subscriptions
```

### New Hooks

```typescript
// lib/hooks/useNotes.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../supabase-client'

export function useNotes() {
  return useQuery({
    queryKey: ['notes'],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('notes')
        .select('id, path, title, updated_at')
        .order('updated_at', { ascending: false })
      if (error) throw error
      return data
    }
  })
}

export function useNote(id: string) {
  return useQuery({
    queryKey: ['notes', id],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('notes')
        .select('*')
        .eq('id', id)
        .single()
      if (error) throw error
      return data
    }
  })
}

export function useSaveNote() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (note: { id?: string; title: string; content: string; path: string }) => {
      if (note.id) {
        const { data, error } = await supabase
          .from('notes')
          .update({ title: note.title, content: note.content, updated_at: new Date() })
          .eq('id', note.id)
          .select()
          .single()
        if (error) throw error
        return data
      } else {
        const { data, error } = await supabase
          .from('notes')
          .insert({ title: note.title, content: note.content, path: note.path })
          .select()
          .single()
        if (error) throw error
        return data
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notes'] })
    }
  })
}
```

### Realtime Subscriptions

```typescript
// lib/supabase-realtime.ts
import { supabase } from './supabase-client'

export function subscribeToNotes(onUpdate: (payload: any) => void) {
  return supabase
    .channel('notes-changes')
    .on(
      'postgres_changes',
      { event: '*', schema: 'public', table: 'notes' },
      onUpdate
    )
    .subscribe()
}
```

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Cloudflare                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ memory.redleif  │  │ api.memory.     │  │ sync.memory.   │  │
│  │ .dev (Web UI)   │  │ redleif.dev     │  │ redleif.dev    │  │
│  └────────┬────────┘  └────────┬────────┘  └───────┬────────┘  │
└───────────┼────────────────────┼───────────────────┼────────────┘
            │                    │                   │
            ▼                    ▼                   ▼
┌───────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Cloudflare      │  │   Fly.io        │  │   Electric      │
│   Pages           │  │                 │  │   Cloud (free)  │
│                   │  │   FastAPI       │  │   or Fly.io     │
│   Next.js export  │  │   (optional)    │  │                 │
└───────────────────┘  └────────┬────────┘  └────────┬────────┘
                                │                    │
                                └─────────┬──────────┘
                                          │
                                          ▼
                               ┌─────────────────────┐
                               │  Supabase           │
                               │  ├─ Postgres        │
                               │  ├─ Auth            │
                               │  ├─ Realtime        │
                               │  └─ Storage (opt)   │
                               └─────────────────────┘
```

### Estimated Monthly Costs

| Tier | Components | Cost |
|------|------------|------|
| **Free** | Supabase Free + Electric Cloud Beta + Cloudflare Pages | $0 |
| **Minimal** | Above + Fly.io hobby (FastAPI) | ~$5/mo |
| **Production** | Supabase Pro (IPv4) + Fly.io | ~$30/mo |

---

## Migration Plan

### Phase 1: Supabase Setup (2-3 days)

- [ ] Create Supabase project
- [ ] Run schema migrations
- [ ] Configure Auth (connect existing OAuth)
- [ ] Write migration script: SQLite → Postgres
- [ ] Verify data in Supabase dashboard

**Rollback:** Delete Supabase project

### Phase 2: Backend Dual-Mode (3-4 days)

- [ ] Add asyncpg + SQLAlchemy dependencies
- [ ] Create `db.py` session management
- [ ] Implement Postgres versions of services
- [ ] Add `DB_MODE` environment variable
- [ ] Test API works with both backends

**Rollback:** Set `DB_MODE=sqlite`

### Phase 3: Electric Sync Layer (3-4 days)

- [ ] Deploy Electric (Cloud or Fly.io)
- [ ] Configure Supabase connection (IPv6 or Pro IPv4)
- [ ] Define sync shapes
- [ ] Test sync with CLI/curl
- [ ] Document Electric setup

**Rollback:** Disable Electric, web UI still works via Supabase direct

### Phase 4: Web UI Integration (3-4 days)

- [ ] Add `@supabase/supabase-js` and `@tanstack/react-query`
- [ ] Create Supabase client and hooks
- [ ] Replace `lib/api.ts` calls in components
- [ ] Add Realtime subscriptions
- [ ] Add sync status indicator
- [ ] Test multi-tab editing

**Rollback:** Revert to `lib/api.ts`

### Phase 5: Obsidian Export (2-3 days)

- [ ] Create `obsidian_exporter.py` service
- [ ] Add export API endpoint
- [ ] Add "Export to Vault" button in UI
- [ ] Test exported vault opens in Obsidian

**Rollback:** Feature flag off

### Phase 6: Desktop/Mobile Apps (Future)

- [ ] Electron wrapper with local SQLite
- [ ] Electric client integration
- [ ] PWA or React Native mobile app

---

## Conflict Resolution Strategy

Electric uses CRDTs for automatic conflict resolution:

| Conflict Type | Resolution |
|---------------|------------|
| Same field edited | Last-write-wins by timestamp |
| Different fields | Both changes merged |
| Delete vs Edit | Delete wins (configurable) |
| Create same path | First writer wins, second gets error |

For rare manual conflicts, the UI will show:
1. Banner: "This note was edited elsewhere"
2. Option to view diff
3. Option to keep local / keep remote / merge manually

---

## Security Considerations

- Row Level Security (RLS) on all tables via `user_id`
- Supabase Auth JWT validation
- Electric shapes filtered by user
- No direct Postgres exposure (Supabase manages)

### RLS Policies

```sql
-- Enable RLS
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE relations ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

-- Notes: users can only access their own
CREATE POLICY "Users can view own notes" ON notes
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own notes" ON notes
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own notes" ON notes
    FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own notes" ON notes
    FOR DELETE USING (auth.uid() = user_id);

-- Similar policies for relations and sessions...
```

---

## Decisions (Resolved)

| Question | Decision |
|----------|----------|
| **Supabase region** | US East / Southeast |
| **Electric hosting** | Self-hosted on Fly.io |
| **IPv4 vs IPv6** | IPv6 (free tier) |
| **Markdown editor** | TipTap (Notion-like WYSIWYG) |
| **Content storage** | Markdown in DB, convert to/from TipTap JSON on load/save |

---

## TipTap Integration

### Dependencies

```bash
npm install @tiptap/react @tiptap/starter-kit @tiptap/extension-link \
  @tiptap/extension-placeholder @tiptap/extension-typography \
  @tiptap/pm tiptap-markdown
```

### Content Flow

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Supabase      │      │   TipTap        │      │   User          │
│   (Markdown)    │ ───► │   (JSON DOM)    │ ───► │   (WYSIWYG)     │
│                 │ load │                 │      │                 │
│                 │ ◄─── │                 │ ◄─── │                 │
│                 │ save │                 │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

### Example Hook

```typescript
// lib/hooks/useNoteEditor.ts
import { useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import { Markdown } from 'tiptap-markdown'

export function useNoteEditor(initialMarkdown: string) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Markdown.configure({
        transformPastedText: true,
        transformCopiedText: true,
      }),
    ],
    content: initialMarkdown, // Auto-converts MD → JSON
  })

  const getMarkdown = () => {
    return editor?.storage.markdown.getMarkdown() ?? ''
  }

  return { editor, getMarkdown }
}
```

---

## References

- [ElectricSQL Docs](https://electric-sql.com/docs)
- [ElectricSQL + Supabase Integration](https://electric-sql.com/docs/integrations/supabase)
- [Supabase Realtime](https://supabase.com/docs/guides/realtime)
- [TanStack Query](https://tanstack.com/query)
