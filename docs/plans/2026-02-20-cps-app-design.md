# CoparentingSystem App (CPS) — Design Document

**Date:** 2026-02-20
**Status:** Approved
**Origin:** Evolved from BrainWiki PRD into full co-parenting case management platform

---

## 1. Overview

CPS is a self-hosted, templated co-parenting case management platform deployed as a single Docker Compose stack. Each family gets their own isolated instance (e.g., `fielder.coparentingsystem.app`). The app consolidates notes/knowledge (Obsidian-Memory), AI chat (OpenClaw), document management (replacing Paperless-NGX as primary), and role-based access into one authenticated interface.

**Non-goals:** Note editing (mutations go through AI agent or direct vault editing), mobile native app (OpenClaw handles mobile), multi-tenant shared infrastructure.

---

## 2. Architecture

### Compose Stack (7 containers, all pre-built images)

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                       │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ cps-app  │  │  memory   │  │ openclaw  │  │  scanui   │   │
│  │ Next.js  │  │ FastAPI   │  │ Gateway   │  │ Pipeline  │   │
│  │ :3000    │──│ :8765     │  │ :18789    │  │ (worker)  │   │
│  └────┬─────┘  └────┬─────┘  └───────────┘  └─────┬─────┘   │
│       │              │                              │         │
│  ┌────┴──────────────┴──────────────────────────────┴────┐   │
│  │                    postgres :5432                       │   │
│  │            (OM schema + CPS schema)                    │   │
│  └────────────────────────────────────────────────────────┘   │
│       │                                              │         │
│  ┌────┴─────┐                                  ┌─────┴────┐   │
│  │  redis   │                                  │   minio   │   │
│  │  :6379   │                                  │  :9000    │   │
│  └──────────┘                                  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

| Container | Image | Purpose |
|-----------|-------|---------|
| `cps-app` | `ghcr.io/jodfie/cps-app:latest` | Frontend + API routes, all UI |
| `memory` | `ghcr.io/jodfie/obsidian-memory:latest` | Notes, graph, search, entities, sessions |
| `openclaw` | `ghcr.io/openclaw/openclaw:latest` | AI chat gateway, multi-channel messaging |
| `scanui` | `ghcr.io/jodfie/cps-scanui-worker:latest` | Document classification, extraction, routing |
| `postgres` | `postgres:16-alpine` | Shared DB — OM schema + CPS schema |
| `minio` | `minio/minio` | S3-compatible file/media storage |
| `redis` | `redis:7-alpine` | JWT session blacklist, rate limiting, cache |

### Secrets Management

Self-hosted Phase instance at `secrets.coparentingsystem.app` (independent compose stack). Each CPS instance pulls secrets at runtime via Phase CLI. Only `PHASE_SERVICE_TOKEN` stored locally.

```
CPS Ecosystem
├── secrets.coparentingsystem.app    ← Phase (centralized secrets)
├── fielder.coparentingsystem.app    ← CPS instance
├── sandbox.coparentingsystem.app    ← CPS instance (demo)
└── future.coparentingsystem.app     ← CPS instance (new family)
```

### Data Flow

```
Mobile camera / File upload / Scanner
        │
        ▼
    cps-app (Next.js API route)
        │
        ├──► MinIO (store original file)
        │
        ▼
    scanui (classification pipeline)
        │
        ├──► CPS-relevant? → stays in MinIO, metadata → Postgres
        │                     note created → memory API
        │
        └──► Personal? → forward to Paperless-NGX API → delete from MinIO
```

---

## 3. Auth & Permissions

### JWT Auth (built-in, no external identity provider)

- Access token: 1 hour, httpOnly cookie
- Refresh token: 30 days, httpOnly cookie, stored in Redis for blacklisting
- Invite flow: owner generates invite link with role → invitee creates account

### Roles

| Role | Description | Default Access |
|------|-------------|---------------|
| `owner` | Primary parent | Everything |
| `coparent` | Other parent | Only explicitly shared items |
| `legal` | Attorney/advocate | Legal-tagged categories + explicit shares |
| `support` | Therapist, family, mediator | Family-tagged categories + explicit shares |

### Permission Model

Category-based defaults per role, with per-item overrides (grant/revoke). Overrides always beat defaults.

```
item_permissions table:
  item_type (note | media)
  item_id
  user_id
  permission (grant | revoke)
  granted_by, granted_at
```

---

## 4. Database Schema

### Schema Boundaries

```
Postgres
├── om_schema (Obsidian-Memory owns)
│   ├── notes, fts_index
│   ├── graph_nodes, graph_edges
│   ├── entities, patterns
│   ├── sessions, session_events
│   └── vaults, dedup_suggestions
│
└── cps_schema (CPS app owns)
    ├── users, refresh_tokens
    ├── item_permissions
    ├── media_items, media_tags
    ├── ai_config
    ├── scan_queue, scan_history
    └── instance_config
```

### CPS Schema Tables

```sql
-- Auth & Users
users (
  id UUID PRIMARY KEY,
  email VARCHAR UNIQUE NOT NULL,
  password_hash VARCHAR NOT NULL,
  display_name VARCHAR,
  role ENUM('owner','coparent','legal','support') NOT NULL,
  avatar_url VARCHAR,
  invited_by UUID REFERENCES users(id),
  invite_token VARCHAR,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP,
  last_login TIMESTAMP
)

refresh_tokens (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  token_hash VARCHAR NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  revoked BOOLEAN DEFAULT false
)

-- Permissions
item_permissions (
  id SERIAL PRIMARY KEY,
  item_type ENUM('note','media') NOT NULL,
  item_id INTEGER NOT NULL,
  user_id UUID REFERENCES users(id),
  permission ENUM('grant','revoke') NOT NULL,
  granted_by UUID REFERENCES users(id),
  created_at TIMESTAMP
)

-- Media Gallery
media_items (
  id SERIAL PRIMARY KEY,
  title VARCHAR NOT NULL,
  original_filename VARCHAR NOT NULL,
  minio_key VARCHAR NOT NULL,
  thumbnail_key VARCHAR,
  mime_type VARCHAR NOT NULL,
  file_size_bytes BIGINT,
  category ENUM('MEDICAL','CPS_EXPENSE','SCHOOLWORK','GENERAL','PERSONAL'),
  classification_confidence FLOAT,
  uploaded_by UUID REFERENCES users(id),
  is_personal BOOLEAN DEFAULT false,
  paperless_task_id VARCHAR,
  metadata JSONB,
  note_id INTEGER,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)

media_tags (
  media_id INTEGER REFERENCES media_items(id),
  tag VARCHAR NOT NULL,
  PRIMARY KEY (media_id, tag)
)

-- AI Configuration
ai_config (
  id SERIAL PRIMARY KEY,
  provider VARCHAR NOT NULL,
  api_key_encrypted VARCHAR NOT NULL,
  model_alias VARCHAR,
  model_id VARCHAR,
  is_active BOOLEAN DEFAULT true,
  updated_at TIMESTAMP
)

-- ScanUI Processing Queue
scan_queue (
  id SERIAL PRIMARY KEY,
  original_filename VARCHAR NOT NULL,
  minio_key VARCHAR NOT NULL,
  status ENUM('pending','processing','needs_clarification','ready','routing','done','failed'),
  category VARCHAR,
  confidence FLOAT,
  metadata JSONB,
  error_message TEXT,
  processing_time_ms INTEGER,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
)

scan_history (
  id SERIAL PRIMARY KEY,
  filename VARCHAR NOT NULL,
  category VARCHAR NOT NULL,
  metadata JSONB,
  status VARCHAR NOT NULL,
  media_id INTEGER REFERENCES media_items(id),
  paperless_id VARCHAR,
  error_message TEXT,
  processing_time_ms INTEGER,
  created_at TIMESTAMP
)

-- Instance Config
instance_config (
  key VARCHAR PRIMARY KEY,
  value JSONB NOT NULL,
  updated_at TIMESTAMP
)
```

---

## 5. Features & Pages

### Routes

| Route | Purpose | Style | Auth |
|-------|---------|-------|------|
| `/login` | Login / accept invite | Standalone | Public |
| `/setup` | First-run wizard | Standalone | First user only |
| `/` | Dashboard | App | All roles |
| `/notes` | Note browser with filters | App | Filtered by role |
| `/notes/[permalink]` | Note article view | Wikipedia | Filtered by role |
| `/projects` | Project grid | App | Filtered by role |
| `/projects/[name]` | Notes by project | App | Filtered by role |
| `/search?q=...` | Search results | App | Filtered by role |
| `/media` | Media gallery | App | Filtered by role |
| `/media/[id]` | Media detail + sharing | App | Filtered by role |
| `/media/upload` | Upload / camera capture | App | Owner, coparent |
| `/chat` | Full OpenClaw chat | App | Owner only |
| `/sessions` | AI session history | App | Owner only |
| `/sessions/[id]` | Session detail | App | Owner only |
| `/entities` | Entity explorer | App | Filtered by role |
| `/patterns` | Pattern viewer | App | Owner only |
| `/tags` | Tag cloud | App | Filtered by role |
| `/tags/[tag]` | Notes by tag | App | Filtered by role |
| `/graph` | Knowledge graph (Phase 2) | App | Owner only |
| `/settings` | AI keys, users, integrations | App | Owner only |

### Design

- **Hybrid layout**: Wikipedia-style (serif, 720px max-width, ToC) for note article pages; app-style for browse/search/gallery/dashboard
- **Dark mode**: toggle in header, respects system preference, persists in localStorage
- **Responsive**: sidebar collapses on mobile, single-column layout

### Note Viewer (Wikipedia-style)

- `react-markdown` + `remark-gfm` + `rehype-raw` + `rehype-prism-plus`
- Custom remark plugin for `[[wikilink]]` → `/notes/{permalink}` resolution
- Backlinks panel ("What links here")
- Table of contents from headings (sticky sidebar on desktop)
- Metadata bar: type, project, tags, dates
- Breadcrumb: Project > Note Title

### Media Gallery

- Grid/list toggle with thumbnails
- Preview: PDF viewer, image lightbox, video player
- Camera capture: mobile document scanner (crop, enhance, multi-page)
- Batch upload: drag-and-drop
- Auto-classify via ScanUI pipeline, real-time status via WebSocket
- Sharing controls: per-item grant/revoke per user
- Personal docs: forward to Paperless-NGX → delete from MinIO

### OpenClaw Integration

- Dashboard: chat widget via iframe (`?gatewayUrl=ws://openclaw:18789&token=...`)
- `/chat`: full-screen iframe of Control UI
- Settings: manage OpenClaw config via CPS API route

---

## 6. Tech Stack

### Kept from web-ui/

- Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS
- React Query (`@tanstack/react-query`)
- Dashboard, Nav, NotesList, KnowledgeGraph, GraphPanel, ConnectionStatus components
- useNotes, useSearchNotes, useRelations, useSessions hooks
- API client foundation (`lib/api.ts`)

### Stripped

- TipTap (all editor packages), EditorToolbar, MarkdownEditor
- Supabase (auth, client, realtime)
- Electric SQL
- useNoteEditor, useElectricSync, useRealtimeNotes hooks

### Added

- `react-markdown` + `remark-gfm` + `rehype-raw` + `rehype-prism-plus` (markdown rendering)
- Custom remark wikilink plugin
- `bcrypt` + `jose` (JWT auth in API routes)
- `@minio/minio-js` (S3 client)
- Camera capture lib (`react-webcam` + canvas cropping)
- WebSocket client (OpenClaw chat + ScanUI updates)
- `react-force-graph-2d` (Phase 2, dynamic import)

### Next.js API Routes

```
src/app/api/
├── auth/         (login, register, refresh, logout, invite)
├── media/        (list, upload, detail, share, presigned URLs)
├── scan/         (queue status, trigger classification, webhook)
├── settings/     (AI config, integrations, user management)
├── setup/        (first-run wizard)
└── proxy/        (permission-filtered proxy to OM API)
```

### ScanUI Worker Changes

- Drops: Flask web UI (rebuilt in Next.js), SQLite queue (uses Postgres)
- Keeps: classification pipeline, Claude runner, metadata extractor, file namer, pattern detector
- Changes: reads from Postgres `scan_queue`, writes to `scan_history` + `media_items`
- Comms: CPS writes to `scan_queue` on upload → ScanUI polls → processes → webhook to cps-app

### Backend Addition

- `GET /api/notes/by-permalink/{slug}` added to Obsidian-Memory API

---

## 7. Deployment

### All Pre-built Images

No `build:` directives. Entire stack is `docker compose pull && docker compose up -d`.

### Phase Secrets

Self-hosted Phase at `secrets.coparentingsystem.app` (independent compose stack). Each container uses Phase CLI to inject env vars at runtime. Only `PHASE_SERVICE_TOKEN` stored locally.

### Templating for New Deployments

```bash
git clone https://github.com/jodfie/coparenting-system-app cps-jones
cd cps-jones
cp .env.example .env
./scripts/generate-secrets.sh
echo "INSTANCE_DOMAIN=jones.coparentingsystem.app" >> .env
docker compose up -d
# User visits https://jones.coparentingsystem.app → setup wizard
```

### First-Run Setup Wizard

When no owner exists in DB, all routes redirect to `/setup`:
1. Create owner account (email, password, display name)
2. Configure AI keys (Anthropic required, others optional)
3. Instance name and preferences
4. Optional integrations (Paperless-NGX, push notifications)
5. Done → redirect to dashboard

### Database Init

`init-db.sql` creates separate Postgres users and schemas:
- `om` user owns `om_schema` (Obsidian-Memory tables)
- `cps` user owns `cps_schema` (CPS tables) + read access on `om_schema`

---

## 8. AI Configuration

Centralized in Postgres `ai_config` table, managed via CPS settings page. All services read from one source:

- **cps-app**: reads directly from Postgres
- **memory (OM)**: receives config via env vars (synced from CPS on settings change)
- **scanui**: reads directly from Postgres
- **openclaw**: CPS writes to `openclaw.json` config file on settings change

Single settings page, one place to manage API keys, models, and fallbacks.

---

## 9. Phases

### Phase 1 — MVP (Core Platform)

- JWT auth with roles (owner, coparent, legal, support)
- First-run setup wizard + invite flow
- Read-only note viewer (Wikipedia-style, wikilinks, backlinks, search)
- Media gallery (upload, camera capture, ScanUI classification, Paperless forwarding)
- Permission filtering (category defaults + per-item overrides)
- Dashboard with chat widget + recent notes/docs
- Settings (AI keys, user management, integrations)
- Phase deployment for secrets
- Dark mode, responsive layout

### Phase 2 — Exploration & Visualization

- Full interactive knowledge graph (`react-force-graph-2d`)
- Local per-note graph
- Entity explorer
- Pattern viewer
- Session browser with summaries
- Tag cloud
- Related/similar notes

### Phase 3 — Intelligence & Integration

- OpenClaw as universal AI proxy (route all AI calls through gateway)
- Offline / PWA support
- Keyboard navigation
- Audit log for legal proceedings

### Phase 4 — Co-Parenting Collaboration

- OurFamilyWizard-style features (major architecture expansion)
- Shared calendar between parents
- Parent-to-parent messaging (court-admissible)
- Expense tracking and splitting
- Activity log / check-in system
- Child profile pages
- Custody schedule visualization
