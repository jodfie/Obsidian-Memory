# BrainWiki — Product Requirements Document

> Read-only wiki-style web app for browsing and exploring Obsidian-Memory vault notes.

**Version:** 1.0
**Date:** 2026-02-18
**Status:** Draft

---

## 1. Overview

BrainWiki is a read-only, Wikipedia-inspired web interface for exploring notes stored in the Obsidian-Memory system. It connects to the existing REST API at `localhost:8765` and provides a clean reading experience with search, graph visualization, backlinks, and project-based navigation.

**Non-goal:** Editing. All mutations happen via the AI agent (Brain) through the API. This app is purely for reading and exploring.

### Current State
- **Backend:** Obsidian-Memory API running at `localhost:8765` (FastAPI/uvicorn)
- **Existing UI:** SilverBullet at `memory.redleif.dev` — functional for editing but weak for navigation/discovery
- **Data:** 510+ notes across multiple vaults (Brain, ADHD, etc.) and projects (secondbrain, TechKB, CoparentingSystem, etc.)
- **Graph:** 500+ nodes, 1200+ edges

### Deployment Target
- **VPS:** redleif-dev (194.140.199.114)
- **Auth:** Behind Authelia at a subdomain (e.g., `wiki.redleif.dev`)
- **Container:** Docker with reverse proxy support

---

## 2. API Surface

All data comes from the existing Obsidian-Memory API. No new backend needed.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/notes` | GET | List notes with filters (vault, project, type, tags, limit, offset) |
| `/api/notes/{id}` | GET | Read single note by ID |
| `/api/notes/search` | POST | Full-text search with filters |
| `/api/projects` | GET | List projects with note counts |
| `/api/graph` | GET | Full graph (nodes + edges) |
| `/api/graph/stats` | GET | Graph statistics |
| `/api/graph/nodes/{id}/backlinks` | GET | Notes linking to this note |
| `/api/graph/nodes/{id}/similar` | GET | Similar notes (embedding similarity) |
| `/api/graph/nodes/{id}/neighbors` | GET | Connected notes in graph |
| `/api/graph/traverse` | POST | BFS/DFS traversal from a node |
| `/api/notes/entities/search` | GET | Search entities |
| `/api/notes/entities/by-type/{type}` | GET | Entities grouped by type |

---

## 3. Tech Stack

### Recommended: **Next.js 14 (App Router) + Tailwind CSS**

**Why Next.js:**
- Server-side rendering for fast initial loads and SEO (if ever exposed)
- App Router with layouts maps perfectly to wiki navigation patterns
- API route proxying to avoid CORS issues with the backend
- React ecosystem for graph visualization libraries
- Excellent Docker support

**Full Stack:**

| Layer | Choice | Rationale |
|---|---|---|
| Framework | Next.js 14 (App Router) | SSR, layouts, API proxy |
| Styling | Tailwind CSS + shadcn/ui | Rapid UI, dark mode, consistent design |
| Markdown | `react-markdown` + `rehype-raw` + `remark-gfm` | Full markdown rendering |
| Syntax highlighting | `rehype-prism-plus` or `shiki` | Code block highlighting |
| Graph viz | `react-force-graph-2d` (or `d3-force` directly) | Interactive, performant |
| Search | Client-side debounced fetch | API already handles search |
| State | React Server Components + `nuqs` for URL state | Minimal client JS |
| Icons | `lucide-react` | Clean, consistent |
| Container | Docker (multi-stage) | Production deployment |

### Alternative considered:
- **Astro** — great for static, but wiki needs dynamic search/graph interaction
- **SvelteKit** — viable but smaller ecosystem for graph libs

---

## 4. Features

### 4.1 Navigation Sidebar

Collapsible left sidebar (hidden on mobile, toggled via hamburger).

**Sections:**
- **Projects** — tree list from `/api/projects`, showing note counts. Click to filter.
- **Note Types** — filter chips (knowledge, decision, reference, project, etc.)
- **Tags** — tag cloud or scrollable list, sized by frequency. Click to filter.
- **Recent Notes** — last 10 viewed (stored in localStorage)
- **Vaults** — vault switcher (Brain, ADHD, etc.)

### 4.2 Search

- Search bar in header, always visible
- Debounced (300ms) search-as-you-type hitting `POST /api/notes/search`
- Results dropdown with title + highlighted content snippet
- Filter pills: project, vault, type, tags (persisted in URL params)
- Keyboard shortcut: `/` or `Cmd+K` to focus search
- Cache recent searches in sessionStorage

### 4.3 Note Viewer (Main Content Area)

- Clean markdown rendering with proper typography
- **Wikilinks** (`[[Note Title]]`) rendered as clickable internal links — resolve via note title/permalink
- Syntax highlighting for code blocks (all common languages)
- Frontmatter displayed as a subtle metadata bar (type, project, tags, dates)
- Table of contents generated from headings (sticky on desktop, collapsible)
- Breadcrumb: Vault > Project > Note Title

### 4.4 Backlinks Panel

- Right sidebar or collapsible section below content
- "What links here" — fetched from `/api/graph/nodes/{id}/backlinks`
- Each backlink shows note title + snippet of the linking context
- Count badge in the section header

### 4.5 Related Notes

- Section below or beside backlinks
- Fetched from `/api/graph/nodes/{id}/similar`
- Show top 5-8 similar notes with title and similarity score
- Also show `/api/graph/nodes/{id}/neighbors` as "Connected Notes"

### 4.6 Graph Visualization

**Two modes:**

1. **Local graph** (per-note page) — small interactive graph showing the current note + its neighbors (1-2 hops). Collapsible panel.
2. **Full graph** (dedicated `/graph` page) — full knowledge graph from `/api/graph`. Zoom, pan, click nodes to navigate. Color-code by project or type.

**Implementation:**
- `react-force-graph-2d` for both views
- Nodes colored by project, sized by connection count
- Click node → navigate to note
- Hover → show title tooltip
- Filter controls: by project, type, vault

### 4.7 Browse Pages

- `/` — Home: search bar, stats (from `/api/graph/stats`), recent notes, featured projects
- `/notes` — Paginated note list with filters
- `/notes/[id]` — Note detail page (viewer + backlinks + related + local graph)
- `/projects` — Project grid with note counts and descriptions
- `/projects/[name]` — Notes filtered by project
- `/graph` — Full interactive graph
- `/tags` — All tags with counts
- `/tags/[tag]` — Notes filtered by tag
- `/search?q=...` — Dedicated search results page

### 4.8 Design

- **Wikipedia-inspired:** content-first, generous whitespace, readable line lengths (max 720px for prose)
- **Dark mode:** toggle in header, respect `prefers-color-scheme`, persist in localStorage
- **Light theme:** warm white (#fafaf9) background, dark text
- **Dark theme:** near-black (#1a1a1a) background, soft white text
- **Typography:** system font stack or Inter/Source Serif Pro for body text
- **Mobile:** sidebar collapses to hamburger menu, single-column layout, graph hidden by default

---

## 5. File Structure

```
brainwiki/
├── Dockerfile
├── docker-compose.yml
├── next.config.js
├── tailwind.config.ts
├── package.json
├── tsconfig.json
│
├── src/
│   ├── app/
│   │   ├── layout.tsx              # Root layout (sidebar + header)
│   │   ├── page.tsx                # Home page
│   │   ├── notes/
│   │   │   ├── page.tsx            # Note list with filters
│   │   │   └── [id]/
│   │   │       └── page.tsx        # Note detail view
│   │   ├── projects/
│   │   │   ├── page.tsx            # Project grid
│   │   │   └── [name]/
│   │   │       └── page.tsx        # Project notes
│   │   ├── graph/
│   │   │   └── page.tsx            # Full graph view
│   │   ├── tags/
│   │   │   ├── page.tsx            # Tag cloud
│   │   │   └── [tag]/
│   │   │       └── page.tsx        # Tag notes
│   │   └── search/
│   │       └── page.tsx            # Search results
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx          # Search bar, dark mode toggle, nav
│   │   │   ├── Sidebar.tsx         # Projects, types, tags, recent
│   │   │   └── Breadcrumb.tsx
│   │   ├── notes/
│   │   │   ├── NoteContent.tsx     # Markdown renderer with wikilinks
│   │   │   ├── NoteMetadata.tsx    # Frontmatter display bar
│   │   │   ├── NoteCard.tsx        # Card for note lists
│   │   │   ├── BacklinksPanel.tsx  # "What links here"
│   │   │   ├── RelatedNotes.tsx    # Similar + neighbors
│   │   │   └── TableOfContents.tsx # Generated from headings
│   │   ├── search/
│   │   │   ├── SearchBar.tsx       # Instant search with dropdown
│   │   │   └── SearchResults.tsx   # Results list with snippets
│   │   ├── graph/
│   │   │   ├── FullGraph.tsx       # Full knowledge graph
│   │   │   └── LocalGraph.tsx      # Per-note mini graph
│   │   └── ui/                     # shadcn/ui components
│   │       ├── button.tsx
│   │       ├── badge.tsx
│   │       ├── input.tsx
│   │       └── ...
│   │
│   ├── lib/
│   │   ├── api.ts                  # API client (fetch wrapper for all endpoints)
│   │   ├── markdown.ts             # Markdown processing + wikilink resolver
│   │   ├── types.ts                # TypeScript interfaces for API responses
│   │   └── utils.ts                # Helpers (cn, debounce, etc.)
│   │
│   └── styles/
│       └── globals.css             # Tailwind base + custom typography
│
└── public/
    └── favicon.ico
```

---

## 6. Component Breakdown

### API Client (`lib/api.ts`)
```typescript
const API_BASE = process.env.API_URL || 'http://localhost:8765';

export async function searchNotes(query: string, filters?: SearchFilters): Promise<SearchResult[]>
export async function getNote(id: number): Promise<Note>
export async function listNotes(filters?: NoteFilters): Promise<Note[]>
export async function getProjects(): Promise<Project[]>
export async function getBacklinks(noteId: number): Promise<Backlink[]>
export async function getSimilarNotes(noteId: number): Promise<SimilarNote[]>
export async function getNeighbors(noteId: number): Promise<Neighbor[]>
export async function getFullGraph(): Promise<Graph>
export async function getGraphStats(): Promise<GraphStats>
export async function searchEntities(query: string): Promise<Entity[]>
```

### Wikilink Resolver (`lib/markdown.ts`)
- Custom remark plugin that transforms `[[Note Title]]` into `<a href="/notes/{id}">Note Title</a>`
- Needs a title→id lookup — fetch once and cache (or use API search as fallback)
- Handle `[[Title|Display Text]]` syntax

### Key Types (`lib/types.ts`)
```typescript
interface Note {
  id: number;
  title: string;
  content: string;
  vault_name: string;
  relative_path: string;
  permalink: string;
  note_type: string;
  project: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

interface Project {
  name: string;
  note_count: number;
}

interface GraphNode {
  id: number;
  title: string;
  type: string;
  project: string;
}

interface GraphEdge {
  source: number;
  target: number;
  type: string;
}
```

---

## 7. Deployment

### Docker
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

ENV API_URL=http://host.docker.internal:8765
EXPOSE 3000
CMD ["node", "server.js"]
```

### docker-compose.yml
```yaml
services:
  brainwiki:
    build: .
    ports:
      - "3100:3000"
    environment:
      - API_URL=http://host.docker.internal:8765
    restart: unless-stopped
```

### Reverse Proxy (Caddy/Nginx)
```
wiki.redleif.dev {
    reverse_proxy localhost:3100
}
```

Authelia middleware sits in front as usual — no app-level auth needed.

---

## 8. Performance

- **SSR for note pages** — fast first paint, good for sharing links
- **Client-side search** — debounced API calls, cache results in sessionStorage
- **Graph data** — fetch full graph once, cache in memory. Lazy-load graph component (dynamic import)
- **Note list pagination** — 50 notes per page, infinite scroll or pagination
- **Image optimization** — Next.js `<Image>` for any embedded images
- **Bundle size** — keep graph viz in dynamic import (~150KB), rest should be <100KB

---

## 9. MVP Scope (Phase 1)

Ship these first:

1. ✅ Note viewing with markdown rendering + wikilinks
2. ✅ Search (instant, with filters)
3. ✅ Sidebar navigation (projects, types)
4. ✅ Backlinks panel
5. ✅ Dark mode
6. ✅ Docker deployment
7. ✅ Responsive layout

### Phase 2
- Full graph visualization
- Local per-note graph
- Tag cloud
- Related/similar notes
- Entity browsing

### Phase 3
- Search result caching + offline support
- Keyboard navigation (j/k to scroll notes, Enter to open)
- Reading history with localStorage
- Note "collections" or bookmarks

---

## 10. Open Questions

1. **Wikilink resolution** — Does the API support lookup by title/permalink, or only by ID? May need a title→ID mapping endpoint or use search.
2. **Auth** — Authelia handles auth at the proxy level. Does the app need to pass any headers to the API?
3. **Subdomain** — Confirm `wiki.redleif.dev` or alternative.
4. **API CORS** — If the app SSRs everything, CORS isn't needed. If client-side fetches are needed, API may need CORS headers for the wiki subdomain.

---

*This PRD is ready for a coding agent to pick up and build. Start with the file structure, implement the API client, then build pages top-down starting with the note viewer.*
