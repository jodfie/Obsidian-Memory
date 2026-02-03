# System Architecture Diagrams

Visual representation of Obsidian-Memory system architecture and data flows.

## High-Level System Architecture

```mermaid
graph TB
    subgraph Clients
        A1[Claude.ai<br/>Remote/SSE]
        A2[Claude Code<br/>Local/stdio]
        A3[Cursor<br/>Remote/HTTP]
        A4[Web UI<br/>Browser]
    end

    subgraph MCP Layer
        B[MCP Server<br/>TypeScript/Bun]
    end

    subgraph Backend
        C[FastAPI<br/>Python]
    end

    subgraph Storage
        D1[Markdown Files<br/>Source of Truth]
        D2[SQLite DB<br/>Index]
    end

    A1 -->|OAuth 2.0<br/>HTTPS| B
    A2 -->|stdio| B
    A3 -->|OAuth<br/>HTTPS| B
    A4 -->|Session<br/>HTTPS| C

    B -->|HTTP/JSON| C
    C -->|Read/Write| D1
    C -->|Query/Update| D2
    D1 -.Index.-> D2

    style A1 fill:#e3f2fd
    style A2 fill:#e3f2fd
    style A3 fill:#e3f2fd
    style A4 fill:#e3f2fd
    style B fill:#fff9c4
    style C fill:#f3e5f5
    style D1 fill:#e8f5e9
    style D2 fill:#e8f5e9
```

## MCP Server Architecture

```mermaid
graph LR
    subgraph MCP Server
        A[Transport Layer]
        B[Tool Handlers]
        C[API Client]

        A -->|Requests| B
        B -->|HTTP Calls| C
    end

    subgraph Transports
        T1[stdio]
        T2[SSE]
        T3[Streamable HTTP]
    end

    T1 --> A
    T2 --> A
    T3 --> A

    C -->|REST API| D[Backend]

    style A fill:#fff9c4
    style B fill:#b2dfdb
    style C fill:#ffccbc
```

## Backend Architecture

```mermaid
graph TB
    A[FastAPI App] --> B[Middleware Chain]
    B --> C[API Routes]
    C --> D[Service Layer]
    D --> E[Storage Layer]

    subgraph Middleware
        M1[Validation]
        M2[Rate Limit]
        M3[CF Access]
        M4[Auth]
        M5[CORS]
    end

    subgraph Services
        S1[VaultService]
        S2[GraphService]
        S3[AIService]
        S4[SearchService]
        S5[SyncService]
    end

    subgraph Storage
        ST1[Markdown Files]
        ST2[SQLite FTS5]
    end

    B --> M1 --> M2 --> M3 --> M4 --> M5 --> C
    D --> S1 & S2 & S3 & S4 & S5
    S1 --> ST1
    S2 --> ST2
    S3 --> ST2
    S4 --> ST2
    S5 --> ST1

    style A fill:#e3f2fd
    style C fill:#f3e5f5
    style D fill:#fff9c4
    style E fill:#e8f5e9
```

## Data Flow: Write Operation

```mermaid
sequenceDiagram
    participant Client
    participant MCP as MCP Server
    participant API as Backend API
    participant Vault as VaultService
    participant DB as Database
    participant File as Markdown File

    Client->>MCP: mem_write(title, content)
    MCP->>API: POST /api/notes
    API->>API: Validate Request
    API->>Vault: Create/Update Note
    Vault->>File: Write Markdown
    File-->>Vault: Success
    Vault->>DB: Update Index
    DB->>DB: Extract Wikilinks
    DB->>DB: Update FTS5
    DB-->>Vault: Index Updated
    Vault-->>API: Note Created
    API-->>MCP: Note Response
    MCP-->>Client: Success
```

## Data Flow: Search Operation

```mermaid
sequenceDiagram
    participant Client
    participant MCP as MCP Server
    participant API as Backend API
    participant Search as SearchService
    participant DB as SQLite FTS5

    Client->>MCP: mem_search(query, filters)
    MCP->>API: POST /api/notes/search
    API->>Search: Search Notes
    Search->>DB: FTS5 Query
    DB-->>Search: Matching IDs
    Search->>DB: Load Note Data
    DB-->>Search: Note Details
    Search->>Search: Apply Filters
    Search->>Search: Rank Results
    Search-->>API: Ranked Results
    API-->>MCP: JSON Response
    MCP-->>Client: Formatted Results
```

## Data Flow: Graph Traversal

```mermaid
sequenceDiagram
    participant Client
    participant MCP as MCP Server
    participant API as Backend API
    participant Graph as GraphService
    participant DB as Database

    Client->>MCP: graph_traverse(start_id, depth)
    MCP->>API: GET /api/graph/traverse
    API->>Graph: Traverse Graph
    Graph->>DB: Get Start Node
    DB-->>Graph: Node Data

    loop For each depth level
        Graph->>DB: Get Neighbors
        DB-->>Graph: Neighbor IDs
        Graph->>Graph: Visit Nodes
    end

    Graph->>DB: Load Visited Nodes
    DB-->>Graph: Node Details
    Graph-->>API: Traversal Results
    API-->>MCP: JSON Response
    MCP-->>Client: Graph Data
```

## Knowledge Graph Structure

```mermaid
graph LR
    N1[Note: Python Async]
    N2[Note: FastAPI Guide]
    N3[Note: API Design]
    N4[Note: Error Handling]
    N5[Note: Testing]

    N1 -->|wikilink| N2
    N2 -->|wikilink| N3
    N3 -->|wikilink| N4
    N1 -->|relates_to| N5
    N2 -->|relates_to| N5

    N1 -.superseded_by.-> N6[Note: Async Patterns 2024]

    style N1 fill:#e3f2fd
    style N2 fill:#e3f2fd
    style N3 fill:#e3f2fd
    style N4 fill:#e3f2fd
    style N5 fill:#fff9c4
    style N6 fill:#c8e6c9
```

## Deployment Architecture (Production)

```mermaid
graph TB
    Internet -->|HTTPS| CF[Cloudflare Tunnel]
    CF -->|Auth Check| CFA[Cloudflare Access]
    CFA -->|Valid JWT| Traefik[Traefik Proxy]

    subgraph Docker Host
        Traefik -->|/| Memory[memory<br/>Backend]
        Traefik -->|/mcp| MCP[memory-mcp<br/>MCP Server]
        Traefik -->|/web| Web[memory-web<br/>Web UI]

        Memory -->|Internal| MCP
    end

    subgraph Storage
        Memory -->|RW| Vault[Vault Files<br/>/vaults]
        Memory -->|RW| DB[(SQLite DB)]
    end

    style CF fill:#fce4ec
    style CFA fill:#fce4ec
    style Traefik fill:#e1bee7
    style Memory fill:#bbdefb
    style MCP fill:#c5e1a5
    style Web fill:#fff9c4
    style Vault fill:#c8e6c9
    style DB fill:#c8e6c9
```

## Session Tracking Flow

```mermaid
sequenceDiagram
    participant User
    participant Hook as Claude Code Hook
    participant MCP as MCP Server
    participant Backend
    participant AI as Claude API

    User->>Hook: /session-start
    Hook->>MCP: session_observe(start)
    MCP->>Backend: POST /api/sessions
    Backend-->>MCP: Session ID
    MCP-->>Hook: Session Created

    loop During Session
        User->>Hook: [Actions]
        Hook->>MCP: session_observe(events)
        MCP->>Backend: POST /api/sessions/observe
    end

    User->>Hook: /pre-compact
    Hook->>MCP: session_summary()
    MCP->>Backend: POST /api/sessions/summary
    Backend->>AI: Summarize Events
    AI-->>Backend: Summary
    Backend-->>MCP: Summary Data
    MCP-->>Hook: Session Summary

    Hook->>MCP: mem_write(session_note)
    MCP->>Backend: Save Session Note
```

## Middleware Chain Flow

```mermaid
flowchart TB
    A[Incoming Request] --> B{Validation<br/>Middleware}
    B -->|Invalid| E1[400 Bad Request]
    B -->|Valid| C{Rate Limit<br/>Middleware}
    C -->|Exceeded| E2[429 Too Many]
    C -->|OK| D{CF Access<br/>Middleware}
    D -->|Invalid JWT| E3[403 Forbidden]
    D -->|Valid/Disabled| F{Auth<br/>Middleware}
    F -->|No Token| E4[401 Unauthorized]
    F -->|Valid| G{CORS<br/>Middleware}
    G --> H[API Handler]
    H --> I[Response]
    I --> J[Client]

    style E1 fill:#ffcdd2
    style E2 fill:#ffcdd2
    style E3 fill:#ffcdd2
    style E4 fill:#ffcdd2
    style J fill:#c8e6c9
```

## File Storage Structure

```mermaid
graph TB
    Vault[Vault Root]
    Vault --> CM[_claude-mem]
    Vault --> User[User Files]

    CM --> Notes[notes/]
    CM --> Sessions[sessions/]
    CM --> Projects[projects/]

    Notes --> N1[note-1.md]
    Notes --> N2[note-2.md]
    Sessions --> S1[session-abc.md]
    Projects --> P1[project-xyz.md]

    N1 -.Indexed.-> DB[(SQLite)]
    N2 -.Indexed.-> DB
    S1 -.Indexed.-> DB

    style Vault fill:#e8f5e9
    style CM fill:#fff9c4
    style User fill:#e0e0e0
    style DB fill:#bbdefb
```

## AI Processing Pipeline

```mermaid
flowchart LR
    A[Raw Text] --> B[Extract Entities]
    B --> C[Infer Relations]
    C --> D[Generate Embeddings]
    D --> E[Update Graph]
    E --> F[Store in DB]

    subgraph AIService
        B
        C
        D
    end

    subgraph GraphService
        E
    end

    style B fill:#fff9c4
    style C fill:#fff9c4
    style D fill:#fff9c4
    style E fill:#b2dfdb
    style F fill:#c8e6c9
```

## Related Documentation

- [Architecture Guide](../ARCHITECTURE.md)
- [MCP Integration](../mcp-integration.md)
- [API Documentation](../api.md)
- [Deployment Guide](../deployment.md)
