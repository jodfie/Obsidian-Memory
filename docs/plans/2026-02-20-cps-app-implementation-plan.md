# CPS App Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-hosted co-parenting case management platform as a templated Docker Compose stack with JWT auth, wiki notes, media gallery, AI chat, and document scanning.

**Architecture:** Next.js 14 frontend (repurposed from `web-ui/`) + CPS API routes proxy to Obsidian-Memory backend. ScanUI worker for document processing. OpenClaw for AI chat. PostgreSQL shared DB (OM + CPS schemas). MinIO for media. Phase for secrets.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, React Query, PostgreSQL 16, MinIO, Redis 7, react-markdown, bcrypt, jose (JWT), Phase CLI

**Design Doc:** `docs/plans/2026-02-20-cps-app-design.md`

---

## Critical Path

```
INFRA → DB → AUTH → STRIP → MD-RENDER → NOTE-VIEWER → DASHBOARD → DEPLOY
```

## Parallel Streams (after AUTH completes)

| Stream | Tasks |
|--------|-------|
| A (Critical) | INFRA → DB → AUTH → STRIP → MD-RENDER → NOTE-VIEWER → DASHBOARD |
| B (API) | PROXY → NOTE-BROWSER → Search pages |
| C (Media) | MEDIA-GALLERY → SCANUI |
| D (Integrations) | OPENCLAW + SETTINGS |
| E (DevOps) | DEPLOY (start early, finalize last) |

---

## Task 1: Infrastructure Setup

**Goal:** VPS ready, Phase deployed, CPS repo initialized, compose template created.

**Files:**
- Create: `coparenting-system-app/docker-compose.yml`
- Create: `coparenting-system-app/.env.example`
- Create: `coparenting-system-app/scripts/generate-secrets.sh`
- Create: `coparenting-system-app/init-db.sql`
- Create: `phase-deploy/docker-compose.yml` (Phase stack)

### Step 1: Create CPS app repository on GitHub

```bash
gh repo create jodfie/coparenting-system-app --private
```

### Step 2: Deploy Phase on VPS

Deploy self-hosted Phase at `secrets.coparentingsystem.app`. Follow Phase self-hosting docs. Separate compose stack.

### Step 3: Write `docker-compose.yml` template

All 7 containers with pre-built images. Phase CLI as entrypoint for secret injection. See design doc Section 6 for full compose spec.

```yaml
services:
  cps-app:
    image: ghcr.io/jodfie/cps-app:latest
    entrypoint: ["phase", "run", "--"]
    command: ["node", "server.js"]
    environment:
      - PHASE_HOST=https://secrets.coparentingsystem.app
      - PHASE_SERVICE_TOKEN=${PHASE_TOKEN}
    ports: ["3000:3000"]
    depends_on: [postgres, minio, redis, memory]

  memory:
    image: ghcr.io/jodfie/obsidian-memory:latest
    environment:
      - DB_MODE=postgres
    depends_on: [postgres]

  openclaw:
    image: ghcr.io/openclaw/openclaw:latest
    volumes:
      - openclaw-data:/root/.openclaw
    ports: ["18789:18789"]

  scanui:
    image: ghcr.io/jodfie/cps-scanui-worker:latest
    depends_on: [postgres, minio]

  postgres:
    image: postgres:16-alpine
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports: ["5432:5432"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    volumes:
      - minio-data:/data
    ports: ["9000:9000", "9001:9001"]

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data

volumes:
  pgdata:
  minio-data:
  openclaw-data:
  redis-data:
```

### Step 4: Write `init-db.sql`

```sql
-- Create schemas
CREATE SCHEMA IF NOT EXISTS om_schema;
CREATE SCHEMA IF NOT EXISTS cps_schema;

-- CPS gets read access on OM schema
ALTER DEFAULT PRIVILEGES IN SCHEMA om_schema
  GRANT SELECT ON TABLES TO CURRENT_USER;
```

### Step 5: Write `scripts/generate-secrets.sh`

Generates random values for `JWT_SECRET`, `DB_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `REDIS_PASSWORD`, `INTERNAL_API_TOKEN`, `WEBHOOK_SECRET`.

### Step 6: Write `.env.example`

Template with all required env vars and comments.

### Step 7: Commit

```bash
git add -A && git commit -m "feat: scaffold CPS compose template and infrastructure"
```

---

## Task 2: Database Schema (CPS)

**Goal:** All CPS tables created via migration, tested.

**Files:**
- Create: `src/lib/db.ts` (Postgres client using `pg` or `postgres` package)
- Create: `src/lib/migrations/001_cps_schema.sql`
- Create: `src/app/api/health/route.ts` (update for DB check)

### Step 1: Install Postgres client

```bash
npm install postgres
```

### Step 2: Write DB client (`src/lib/db.ts`)

```typescript
import postgres from 'postgres';

const sql = postgres(process.env.DATABASE_URL!, {
  max: 10,
  idle_timeout: 20,
  connect_timeout: 10,
});

export default sql;
```

### Step 3: Write migration `001_cps_schema.sql`

Full CPS schema as defined in design doc Section 4. All tables: `users`, `refresh_tokens`, `item_permissions`, `media_items`, `media_tags`, `ai_config`, `scan_queue`, `scan_history`, `instance_config`.

### Step 4: Write migration runner

Simple script that runs SQL files in order against the DB.

### Step 5: Test migration locally

```bash
docker compose up postgres -d
npm run migrate
```

### Step 6: Commit

```bash
git commit -m "feat: add CPS database schema and migration system"
```

---

## Task 3: JWT Auth System

**Goal:** Login, register (via invite), refresh, logout, invite generation, setup wizard. Middleware protecting all routes.

**Files:**
- Create: `src/lib/auth.ts` (JWT helpers: sign, verify, middleware)
- Create: `src/lib/auth-context.tsx` (React context for client-side auth state)
- Create: `src/app/api/auth/login/route.ts`
- Create: `src/app/api/auth/register/route.ts`
- Create: `src/app/api/auth/refresh/route.ts`
- Create: `src/app/api/auth/logout/route.ts`
- Create: `src/app/api/auth/invite/route.ts`
- Create: `src/app/api/auth/me/route.ts`
- Create: `src/app/(auth)/login/page.tsx`
- Create: `src/app/(auth)/register/[token]/page.tsx`
- Create: `src/app/setup/page.tsx`
- Create: `src/middleware.ts` (Next.js middleware for JWT validation)
- Modify: `src/lib/providers.tsx` (replace AuthProvider with JWT context)
- Test: `tests/auth/login.test.ts`
- Test: `tests/auth/middleware.test.ts`

### Step 1: Install auth dependencies

```bash
npm install bcrypt jose
npm install -D @types/bcrypt
```

### Step 2: Write JWT helpers (`src/lib/auth.ts`)

```typescript
import { SignJWT, jwtVerify } from 'jose';
import bcrypt from 'bcrypt';

const JWT_SECRET = new TextEncoder().encode(process.env.JWT_SECRET);

export interface JWTPayload {
  sub: string;      // user UUID
  email: string;
  role: 'owner' | 'coparent' | 'legal' | 'support';
  name: string;
}

export async function signAccessToken(payload: JWTPayload): Promise<string> {
  return new SignJWT(payload)
    .setProtectedHeader({ alg: 'HS256' })
    .setExpirationTime('1h')
    .setIssuedAt()
    .sign(JWT_SECRET);
}

export async function signRefreshToken(userId: string): Promise<string> {
  return new SignJWT({ sub: userId })
    .setProtectedHeader({ alg: 'HS256' })
    .setExpirationTime('30d')
    .setIssuedAt()
    .sign(JWT_SECRET);
}

export async function verifyToken(token: string) {
  return jwtVerify(token, JWT_SECRET);
}

export async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, 12);
}

export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash);
}
```

### Step 3: Write Next.js middleware (`src/middleware.ts`)

Intercepts all requests except `/login`, `/register`, `/setup`, `/api/auth/*`, `/_next/*`, `/favicon.ico`. Validates JWT from httpOnly cookie. If no owner in DB, redirects to `/setup`.

### Step 4: Write login API route

POST `/api/auth/login` — validate email/password, issue access + refresh tokens as httpOnly cookies.

### Step 5: Write register API route

POST `/api/auth/register` — accept invite token, create user with assigned role, issue tokens.

### Step 6: Write refresh, logout, me, invite routes

- `/api/auth/refresh` — validate refresh token, issue new access token
- `/api/auth/logout` — blacklist refresh token in Redis
- `/api/auth/me` — return current user from JWT claims
- `/api/auth/invite` — owner generates invite link with role (creates `invite_token` in users table)

### Step 7: Write setup wizard page

`/setup` — form: email, password, display name. Creates owner user. Writes `instance_config` (setup_complete=true). Redirects to dashboard.

### Step 8: Write login page

`/login` — email/password form, calls `/api/auth/login`, redirects to `/`.

### Step 9: Write auth context

`src/lib/auth-context.tsx` — React context that calls `/api/auth/me` on mount, provides `{user, isLoading, logout}` to the app.

### Step 10: Update providers

Replace Supabase AuthProvider with new JWT auth context in `src/lib/providers.tsx`.

### Step 11: Write tests

- Test login with valid/invalid credentials
- Test middleware redirects unauthenticated requests
- Test setup wizard creates owner
- Test invite flow creates user with correct role

### Step 12: Commit

```bash
git commit -m "feat: add JWT auth system with login, invite, and setup wizard"
```

---

## Task 4: Strip web-ui

**Goal:** Remove all editing, Supabase, Electric SQL, and TipTap code. Clean slate for read-only wiki.

**Files:**
- Delete: `src/components/TipTapEditor.tsx`
- Delete: `src/components/EditorToolbar.tsx`
- Delete: `src/components/MarkdownEditor.tsx`
- Delete: `src/components/AuthProvider.tsx`
- Delete: `src/lib/supabase-client.ts`
- Delete: `src/lib/supabase-realtime.ts`
- Delete: `src/lib/electric-client.ts`
- Delete: `src/lib/electric-shapes.ts`
- Delete: `src/lib/hooks/useNoteEditor.ts`
- Delete: `src/lib/hooks/useElectricSync.tsx`
- Delete: `src/lib/hooks/useRealtimeNotes.ts`
- Delete: `src/app/notes/new/page.tsx`
- Delete: `src/app/login/page.tsx` (replaced by `(auth)/login`)
- Delete: `src/app/auth/callback/route.ts`
- Modify: `package.json` (remove TipTap, Supabase, Electric SQL packages)
- Modify: `src/lib/api.ts` (rewrite to call CPS proxy routes)
- Modify: `src/lib/hooks/useNotes.ts` (rewrite to use new api.ts)
- Modify: `src/lib/hooks/useSessions.ts` (rewrite)
- Modify: `src/lib/hooks/useRelations.ts` (rewrite)
- Modify: `src/components/NoteView.tsx` (gut TipTap, placeholder for react-markdown)
- Modify: `src/components/NotesList.tsx` (remove onCreateNote, use new hooks)
- Modify: `src/components/Dashboard.tsx` (use new hooks)
- Modify: `src/app/layout.tsx` (use new providers)

### Step 1: Remove packages

```bash
npm uninstall @tiptap/core @tiptap/extension-link @tiptap/extension-placeholder \
  @tiptap/extension-typography @tiptap/pm @tiptap/react @tiptap/starter-kit \
  tiptap-markdown @supabase/auth-helpers-nextjs @supabase/supabase-js \
  @electric-sql/client
```

### Step 2: Delete files

Delete all files listed above.

### Step 3: Rewrite `src/lib/api.ts`

New API client that calls through CPS proxy routes (`/api/proxy/notes`, `/api/proxy/graph`, etc.) instead of directly to OM. Remove all write methods (createNote, updateNote). Add new methods: `getMediaItems()`, `uploadMedia()`, etc.

```typescript
const API_BASE = '/api/proxy';

export async function getNoteByPermalink(permalink: string): Promise<Note> {
  const res = await fetch(`${API_BASE}/notes/by-permalink/${permalink}`);
  if (!res.ok) throw new Error('Note not found');
  return res.json();
}

export async function searchNotes(query: string, filters?: SearchFilters): Promise<NoteListResponse> {
  const res = await fetch(`${API_BASE}/notes/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, ...filters }),
  });
  return res.json();
}

// ... remaining read-only endpoints
```

### Step 4: Rewrite hooks

`useNotes`, `useRelations`, `useSessions` — all switch from Supabase direct queries to the new `api.ts` functions via React Query.

### Step 5: Stub NoteView

Replace TipTap rendering with a simple `<pre>{content}</pre>` placeholder. MD-RENDER task will replace this.

### Step 6: Clean up components

Remove `onCreateNote` from NotesList, remove NewNoteView export from NoteView, update Dashboard to use new hooks.

### Step 7: Verify build

```bash
npm run build
```

Fix any remaining import errors.

### Step 8: Commit

```bash
git commit -m "refactor: strip editing, Supabase, and Electric SQL from web-ui"
```

---

## Task 5: Permission-Filtered API Proxy

**Goal:** Next.js API routes that proxy to OM API with role-based filtering.

**Files:**
- Create: `src/app/api/proxy/notes/route.ts` (list notes)
- Create: `src/app/api/proxy/notes/search/route.ts` (search)
- Create: `src/app/api/proxy/notes/by-permalink/[slug]/route.ts` (permalink lookup)
- Create: `src/app/api/proxy/notes/[id]/route.ts` (single note)
- Create: `src/app/api/proxy/graph/[...path]/route.ts` (graph endpoints)
- Create: `src/app/api/proxy/projects/route.ts`
- Create: `src/app/api/proxy/sessions/route.ts`
- Create: `src/lib/permissions.ts` (permission checking logic)
- Test: `tests/proxy/permissions.test.ts`

### Step 1: Write permission checker (`src/lib/permissions.ts`)

```typescript
import sql from './db';

interface PermissionContext {
  userId: string;
  role: 'owner' | 'coparent' | 'legal' | 'support';
}

// Category defaults per role
const ROLE_CATEGORIES: Record<string, string[]> = {
  owner: [],       // sees everything, no filtering
  coparent: [],    // explicit shares only
  legal: ['LEGAL', 'CPS_EXPENSE', 'MEDICAL'],
  support: ['MEDICAL', 'SCHOOLWORK', 'GENERAL'],
};

export async function canAccessNote(ctx: PermissionContext, noteId: number): Promise<boolean> {
  if (ctx.role === 'owner') return true;

  // Check per-item override first
  const override = await sql`
    SELECT permission FROM cps_schema.item_permissions
    WHERE item_type = 'note' AND item_id = ${noteId} AND user_id = ${ctx.userId}
    ORDER BY created_at DESC LIMIT 1
  `;
  if (override.length > 0) return override[0].permission === 'grant';

  // Coparent: no category defaults, only explicit shares
  if (ctx.role === 'coparent') return false;

  // Legal/support: check category defaults
  // (requires fetching note type/category from OM)
  return false; // default deny
}

export async function filterNoteList(ctx: PermissionContext, notes: Note[]): Promise<Note[]> {
  if (ctx.role === 'owner') return notes;
  // Filter based on category defaults + overrides
  // ...
}
```

### Step 2: Write proxy routes

Each route: extract JWT from cookie → get user context → call OM API at `http://memory:8765` → filter response by permissions → return to client.

### Step 3: Add permalink endpoint to OM backend

**This modifies the Obsidian-Memory backend** (separate from CPS app).

File: `/home/redleif/Obsidian-Memory/backend/app/api/notes.py`

Add `GET /api/notes/by-permalink/{permalink}`:

```python
@router.get("/by-permalink/{permalink}", response_model=NoteResponse)
async def get_note_by_permalink(
    permalink: str,
    search_index: SearchIndex = Depends(get_search_index),
):
    """Get a note by its permalink slug."""
    note = await search_index.get_note_by_permalink(permalink)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note
```

Add corresponding method to `search_index.py`:

```python
async def get_note_by_permalink(self, permalink: str) -> Optional[dict]:
    """Look up a note by permalink."""
    cursor = await self.db.execute(
        "SELECT * FROM notes WHERE permalink = ?", (permalink,)
    )
    row = await cursor.fetchone()
    if not row:
        return None
    return self._row_to_note(row)
```

### Step 4: Write tests

- Test owner sees all notes
- Test coparent sees nothing without explicit shares
- Test legal sees legal-tagged items
- Test per-item grant overrides category default
- Test per-item revoke hides normally-visible item

### Step 5: Commit

```bash
git commit -m "feat: add permission-filtered API proxy to OM backend"
```

---

## Task 6: Markdown Rendering + Wikilinks

**Goal:** Replace TipTap with react-markdown, add wikilink resolution plugin.

**Files:**
- Create: `src/lib/markdown.ts` (markdown config + wikilink plugin)
- Create: `src/components/notes/MarkdownRenderer.tsx`
- Modify: `src/components/NoteView.tsx` (use MarkdownRenderer)
- Test: `tests/markdown/wikilinks.test.ts`

### Step 1: Install markdown packages

```bash
npm install react-markdown remark-gfm rehype-raw rehype-prism-plus
```

### Step 2: Write wikilink remark plugin (`src/lib/markdown.ts`)

Custom remark plugin that transforms `[[Note Title]]` and `[[Title|Display Text]]` into links to `/notes/{permalink-slug}`.

```typescript
import { visit } from 'unist-util-visit';

function remarkWikilinks() {
  return (tree: any) => {
    visit(tree, 'text', (node, index, parent) => {
      const regex = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;
      // Split text node into text + wikilink elements
      // Transform [[Title]] → <a href="/notes/title-slug">Title</a>
      // Transform [[Title|Display]] → <a href="/notes/title-slug">Display</a>
    });
  };
}
```

Permalink slug derivation: lowercase, replace spaces with hyphens, strip special chars. Same logic as OM's `_generate_permalink()` in `search_index.py`.

### Step 3: Write MarkdownRenderer component

```tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import rehypePrism from 'rehype-prism-plus';
import { remarkWikilinks } from '@/lib/markdown';

export function MarkdownRenderer({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkWikilinks]}
      rehypePlugins={[rehypeRaw, rehypePrism]}
      components={{
        // Custom component overrides for headings (ToC anchors), links, etc.
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
```

### Step 4: Write tests

- Test `[[Simple Link]]` → `/notes/simple-link`
- Test `[[Title|Display]]` → link text is "Display", href is `/notes/title`
- Test multiple wikilinks in same paragraph
- Test wikilinks inside other markdown (bold, lists)

### Step 5: Commit

```bash
git commit -m "feat: add react-markdown rendering with wikilink resolution"
```

---

## Task 7: Note Viewer (Wikipedia-style)

**Goal:** Full note article page at `/notes/[permalink]` with Wikipedia-style layout.

**Files:**
- Create: `src/app/notes/[permalink]/page.tsx`
- Create: `src/components/notes/NoteArticle.tsx` (Wikipedia-style layout)
- Create: `src/components/notes/TableOfContents.tsx`
- Create: `src/components/notes/BacklinksPanel.tsx`
- Create: `src/components/notes/NoteMetadata.tsx`
- Create: `src/components/layout/Breadcrumb.tsx`
- Modify: `src/app/globals.css` (article typography styles)

### Step 1: Write article page route

`/notes/[permalink]/page.tsx` — server component that fetches note by permalink via proxy, renders NoteArticle.

### Step 2: Write NoteArticle component

Wikipedia-style layout:
- Max 720px content width, serif font for prose
- Metadata bar at top (type, project, tags, dates)
- Breadcrumb: Project > Note Title
- Table of contents (sticky sidebar on desktop, collapsible on mobile)
- MarkdownRenderer for content
- BacklinksPanel below content

### Step 3: Write TableOfContents

Extract headings from markdown content, generate anchor links. Sticky positioning on desktop. Highlight current section on scroll.

### Step 4: Write BacklinksPanel

Fetch backlinks from `/api/proxy/graph/nodes/{id}/backlinks`. Display as list with note title + snippet.

### Step 5: Write NoteMetadata bar

Display: note_type badge, project link, tags as pills, created/updated dates.

### Step 6: Add Wikipedia typography to globals.css

```css
.article-content {
  font-family: 'Georgia', 'Times New Roman', serif;
  max-width: 720px;
  line-height: 1.7;
  font-size: 1.05rem;
}
.article-content h1, h2, h3 {
  font-family: system-ui, sans-serif;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.3em;
}
```

### Step 7: Commit

```bash
git commit -m "feat: add Wikipedia-style note viewer with ToC and backlinks"
```

---

## Task 8: Note Browser, Search & Sidebar

**Goal:** Browse notes with filters, search, sidebar navigation, project/tag pages.

**Files:**
- Create: `src/components/layout/Sidebar.tsx`
- Create: `src/components/search/SearchBar.tsx`
- Create: `src/components/search/SearchResults.tsx`
- Create: `src/components/notes/NoteCard.tsx`
- Modify: `src/app/notes/page.tsx` (note list with filters)
- Create: `src/app/search/page.tsx`
- Create: `src/app/projects/page.tsx`
- Create: `src/app/projects/[name]/page.tsx`
- Create: `src/app/tags/page.tsx`
- Create: `src/app/tags/[tag]/page.tsx`
- Modify: `src/app/layout.tsx` (add sidebar + header)

### Step 1: Write Sidebar component

Sections: Projects (tree list with counts), Note Types (filter chips), Tags (scrollable list), Recent Notes (from localStorage).

### Step 2: Write SearchBar

Debounced (300ms) search-as-you-type. Calls POST `/api/proxy/notes/search`. Dropdown results. Keyboard shortcut `/` or `Cmd+K` to focus.

### Step 3: Write NoteCard

Card component for note lists: title, snippet, type badge, project, tags, date.

### Step 4: Write note list page

`/notes` — paginated note list with filter sidebar. Filters: project, vault, type, tags. URL params for filter persistence.

### Step 5: Write search results page

`/search?q=...` — full search results with highlighted snippets and filter pills.

### Step 6: Write project and tag pages

- `/projects` — project grid with note counts
- `/projects/[name]` — notes filtered by project
- `/tags` — tag cloud with counts
- `/tags/[tag]` — notes filtered by tag

### Step 7: Update root layout

Add Sidebar (collapsible on mobile) + Header (search bar, dark mode toggle, user menu).

### Step 8: Commit

```bash
git commit -m "feat: add note browser, search, sidebar navigation, project/tag pages"
```

---

## Task 9: Media Gallery

**Goal:** Upload, browse, preview documents/photos/videos with MinIO storage.

**Files:**
- Create: `src/app/api/media/route.ts` (list, upload)
- Create: `src/app/api/media/[id]/route.ts` (detail, delete)
- Create: `src/app/api/media/[id]/share/route.ts` (grant/revoke)
- Create: `src/app/api/media/[id]/presign/route.ts` (presigned download)
- Create: `src/app/api/media/upload-url/route.ts` (presigned upload)
- Create: `src/lib/minio.ts` (MinIO client)
- Create: `src/lib/thumbnails.ts` (thumbnail generation)
- Create: `src/app/media/page.tsx` (gallery grid/list)
- Create: `src/app/media/[id]/page.tsx` (detail + sharing)
- Create: `src/app/media/upload/page.tsx` (upload + camera)
- Create: `src/components/media/MediaGrid.tsx`
- Create: `src/components/media/MediaCard.tsx`
- Create: `src/components/media/MediaPreview.tsx` (PDF/image/video)
- Create: `src/components/media/CameraCapture.tsx`
- Create: `src/components/media/ShareControls.tsx`

### Step 1: Install dependencies

```bash
npm install minio react-webcam
```

### Step 2: Write MinIO client (`src/lib/minio.ts`)

```typescript
import { Client } from 'minio';

export const minio = new Client({
  endPoint: process.env.MINIO_ENDPOINT || 'minio',
  port: 9000,
  useSSL: false,
  accessKey: process.env.MINIO_ACCESS_KEY!,
  secretKey: process.env.MINIO_SECRET_KEY!,
});

const BUCKET = 'cps-media';

export async function ensureBucket() {
  const exists = await minio.bucketExists(BUCKET);
  if (!exists) await minio.makeBucket(BUCKET);
}

export async function getPresignedUploadUrl(key: string): Promise<string> {
  return minio.presignedPutObject(BUCKET, key, 3600);
}

export async function getPresignedDownloadUrl(key: string): Promise<string> {
  return minio.presignedGetObject(BUCKET, key, 3600);
}
```

### Step 3: Write upload API routes

- `POST /api/media` — accept file upload, store in MinIO, create `media_items` row, enqueue in `scan_queue`
- `GET /api/media/upload-url` — return presigned upload URL for direct-to-MinIO uploads

### Step 4: Write media list/detail API routes

- `GET /api/media` — list with filters (category, type, date), permission-filtered
- `GET /api/media/[id]` — detail with metadata
- `DELETE /api/media/[id]` — delete from MinIO + DB (owner only)
- `GET /api/media/[id]/presign` — presigned download URL

### Step 5: Write sharing API route

`POST /api/media/[id]/share` — grant/revoke access per user via `item_permissions`.

### Step 6: Write gallery UI

- `MediaGrid` — grid/list toggle, thumbnails
- `MediaCard` — thumbnail, title, category badge, date
- `/media` page — gallery with filters
- `/media/[id]` page — full preview + metadata + sharing controls

### Step 7: Write MediaPreview component

Handles PDF (embedded viewer or pdf.js), images (lightbox), video (HTML5 player). Uses presigned URLs.

### Step 8: Write CameraCapture component

Mobile document scanner using `react-webcam`:
- Camera viewfinder
- Capture button
- Crop/rotate/enhance (canvas-based)
- Multi-page: capture multiple → merge to single PDF
- Upload result to `/api/media`

### Step 9: Write thumbnail generation

Server-side: generate thumbnail on upload for images (sharp/canvas), PDFs (first page render), videos (ffmpeg frame capture). Store thumbnail in MinIO.

### Step 10: Commit

```bash
git commit -m "feat: add media gallery with MinIO, upload, camera capture, and sharing"
```

---

## Task 10: ScanUI Worker Integration

**Goal:** ScanUI classification pipeline reads from Postgres, processes documents, webhooks results.

**Files:**
- Modify: ScanUI repo — swap SQLite for Postgres, remove Flask web UI
- Create: `src/app/api/scan/route.ts` (queue status)
- Create: `src/app/api/scan/webhook/route.ts` (callback from worker)
- Create: `src/components/media/ScanStatus.tsx` (real-time status)

### Step 1: Modify ScanUI worker

In the ScanUI repo (`github.com/jodfie/ScanUI`):
- Replace `QueueManager` SQLite backend with Postgres (`scan_queue`, `scan_history` tables)
- Remove Flask web UI (`web/app.py`, `web/events.py`, templates, static)
- Keep: `pipeline.py`, `classifier.py`, `extractor.py`, `file_namer.py`, `pattern_detector.py`, `claude_runner.py`
- Add: webhook callback to CPS app on completion
- Add: MinIO client for reading uploaded files
- Change: `route_document()` — if `is_personal`, forward to Paperless-NGX API then delete from MinIO

### Step 2: Write scan webhook route

`POST /api/scan/webhook` — ScanUI calls this when classification/routing completes. Updates `media_items` with category, confidence, metadata. Broadcasts status via WebSocket (or polling).

### Step 3: Write scan status component

`ScanStatus.tsx` — shows processing progress for recently uploaded files. Polls `/api/scan` for queue status.

### Step 4: Build and push ScanUI worker image

```bash
docker build -t ghcr.io/jodfie/cps-scanui-worker:latest .
docker push ghcr.io/jodfie/cps-scanui-worker:latest
```

### Step 5: Commit

```bash
git commit -m "feat: integrate ScanUI worker with Postgres queue and webhook"
```

---

## Task 11: OpenClaw Chat Embed

**Goal:** Chat widget on dashboard, full chat page, settings integration.

**Files:**
- Create: `src/components/chat/ChatWidget.tsx` (iframe embed)
- Create: `src/app/chat/page.tsx` (full-screen chat)
- Create: `src/app/api/settings/openclaw/route.ts` (config management)

### Step 1: Write ChatWidget

Iframe embedding OpenClaw Control UI:

```tsx
export function ChatWidget() {
  const gatewayUrl = `ws://${process.env.NEXT_PUBLIC_OPENCLAW_HOST}:18789`;
  return (
    <iframe
      src={`http://${process.env.NEXT_PUBLIC_OPENCLAW_HOST}:18789/?gatewayUrl=${gatewayUrl}`}
      className="w-full h-[400px] rounded-lg border"
    />
  );
}
```

### Step 2: Write chat page

`/chat` — full-screen iframe with proper sizing. Owner-only access.

### Step 3: Write OpenClaw settings route

`GET/PUT /api/settings/openclaw` — read/write OpenClaw config. Syncs changes to `openclaw.json` config file in the OpenClaw volume.

### Step 4: Commit

```bash
git commit -m "feat: add OpenClaw chat widget and full chat page"
```

---

## Task 12: Dashboard

**Goal:** Home page with stats, recent notes, recent docs, chat widget, scan status.

**Files:**
- Modify: `src/app/page.tsx`
- Modify: `src/components/Dashboard.tsx`
- Create: `src/components/dashboard/StatsGrid.tsx`
- Create: `src/components/dashboard/RecentNotes.tsx`
- Create: `src/components/dashboard/RecentMedia.tsx`

### Step 1: Write StatsGrid

Fetch counts from proxy (notes, projects, sessions) and media API (documents). Display as card grid.

### Step 2: Write RecentNotes

Latest 5 notes the user can access. Links to `/notes/[permalink]`.

### Step 3: Write RecentMedia

Latest 5 media items the user can access. Links to `/media/[id]`.

### Step 4: Compose Dashboard

Assemble: StatsGrid + RecentNotes + RecentMedia + ChatWidget (owner only) + ScanStatus (if items processing).

### Step 5: Commit

```bash
git commit -m "feat: add dashboard with stats, recent items, and chat widget"
```

---

## Task 13: Settings Pages

**Goal:** AI config, user management, integrations, instance config.

**Files:**
- Create: `src/app/settings/page.tsx` (settings layout)
- Create: `src/app/settings/ai/page.tsx`
- Create: `src/app/settings/users/page.tsx`
- Create: `src/app/settings/integrations/page.tsx`
- Create: `src/app/api/settings/ai/route.ts`
- Create: `src/app/api/settings/integrations/route.ts`
- Create: `src/app/api/settings/users/route.ts`
- Create: `src/app/api/settings/users/[id]/route.ts`

### Step 1: Write AI settings page

Form to add/edit API keys per provider. Model selection (main, research, fallback). Keys encrypted at rest in `ai_config` table. Test connection button.

### Step 2: Write user management page

List current users with roles. Invite button (generates link with role selector). Deactivate/reactivate users. Role change (owner only).

### Step 3: Write integrations page

Paperless-NGX: URL + API token, test connection.
OpenClaw: model config, channel settings.
Push notifications: Pushover config.

### Step 4: Write API routes for each

CRUD operations on `ai_config`, `users`, `instance_config` tables. Owner-only middleware.

### Step 5: Commit

```bash
git commit -m "feat: add settings pages for AI, users, and integrations"
```

---

## Task 14: Dark Mode & Polish

**Goal:** Dark mode toggle, responsive layout, final polish.

**Files:**
- Modify: `tailwind.config.js` (dark mode config)
- Modify: `src/app/globals.css` (light/dark theme variables)
- Create: `src/components/layout/ThemeToggle.tsx`
- Modify: `src/components/layout/Header.tsx`
- Modify: all pages for responsive breakpoints

### Step 1: Configure Tailwind dark mode

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class',
  // ...
}
```

### Step 2: Write theme variables

```css
:root {
  --background: #fafaf9;
  --foreground: #1a1a1a;
  /* ... warm white theme */
}
.dark {
  --background: #1a1a1a;
  --foreground: #e5e5e5;
  /* ... dark theme */
}
```

### Step 3: Write ThemeToggle

Toggle button in header. Reads/writes to localStorage. Respects `prefers-color-scheme`.

### Step 4: Responsive pass

- Sidebar: collapses to hamburger on mobile
- Note viewer: single-column, ToC becomes collapsible
- Media gallery: grid adjusts columns
- Dashboard: stack widgets vertically

### Step 5: Commit

```bash
git commit -m "feat: add dark mode and responsive layout polish"
```

---

## Task 15: Docker Build & Deploy

**Goal:** Dockerfiles, CI/CD, final compose, deploy to VPS.

**Files:**
- Create: `Dockerfile` (cps-app multi-stage build)
- Create: `.github/workflows/build-push.yml`
- Modify: `docker-compose.yml` (finalize with health checks)
- Create: `DEPLOYMENT.md`

### Step 1: Write Dockerfile

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

### Step 2: Write GitHub Actions workflow

Build on push to main → push to `ghcr.io/jodfie/cps-app:latest`.

### Step 3: Add health checks to compose

```yaml
cps-app:
  healthcheck:
    test: ["CMD", "wget", "-q", "--spider", "http://localhost:3000/api/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### Step 4: Deploy to VPS

```bash
ssh redleif-dev
cd /opt/cps-fielder
docker compose pull
docker compose up -d
```

### Step 5: Verify

- Hit `https://fielder.coparentingsystem.app` → setup wizard
- Create owner account
- Configure AI keys
- Browse notes, upload documents, test chat

### Step 6: Commit

```bash
git commit -m "feat: add Dockerfile, CI/CD, and deployment configuration"
```

---

## Task Order Summary

| # | Task | Depends On | Parallelizable With |
|---|------|-----------|---------------------|
| 1 | Infrastructure Setup | — | — |
| 2 | Database Schema | 1 | — |
| 3 | JWT Auth System | 2 | — |
| 4 | Strip web-ui | 3 | 5 (PROXY) |
| 5 | Permission-Filtered API Proxy | 3 | 4 (STRIP) |
| 6 | Markdown Rendering + Wikilinks | 4 | — |
| 7 | Note Viewer (Wikipedia-style) | 5, 6 | — |
| 8 | Note Browser, Search & Sidebar | 5 | 7 |
| 9 | Media Gallery | 2, 3 | 4, 5, 6, 7, 8 |
| 10 | ScanUI Worker Integration | 9 | 7, 8 |
| 11 | OpenClaw Chat Embed | 3 | 4-10 |
| 12 | Dashboard | 7, 8, 9, 11 | — |
| 13 | Settings Pages | 3 | 4-11 |
| 14 | Dark Mode & Polish | 7, 8, 9 | 12, 13 |
| 15 | Docker Build & Deploy | All | — |
