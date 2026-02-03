# OAuth 2.0 Flow Diagrams

Visual representation of OAuth authentication flows in Obsidian-Memory.

## Claude.ai OAuth Flow

```mermaid
sequenceDiagram
    participant User
    participant Claude.ai
    participant CF as Cloudflare Access
    participant Backend as Obsidian-Memory

    User->>Claude.ai: Configure MCP Server
    Note over User,Claude.ai: Enter OAuth credentials

    Claude.ai->>CF: 1. Authorization Request
    Note over Claude.ai,CF: /cdn-cgi/access/authorize<br/>+ client_id + redirect_uri + PKCE

    CF->>User: 2. Login Page
    User->>CF: 3. Email + OTP Code

    CF->>Claude.ai: 4. Authorization Code
    Note over CF,Claude.ai: Redirect to callback URL

    Claude.ai->>CF: 5. Token Request
    Note over Claude.ai,CF: /cdn-cgi/access/token<br/>+ code + PKCE verifier

    CF->>Claude.ai: 6. Access Token
    Note over CF,Claude.ai: JWT token (24h)

    Claude.ai->>Backend: 7. MCP Request + Token
    Note over Claude.ai,Backend: Authorization: Bearer <token>

    Backend->>CF: 8. Validate Token
    Note over Backend,CF: Check JWT signature

    CF->>Backend: 9. Token Valid
    Backend->>Claude.ai: 10. MCP Response
    Claude.ai->>User: 11. Display Result
```

## PKCE Flow Detail

```mermaid
flowchart TB
    A[Claude.ai Initiates Auth] --> B[Generate Code Verifier]
    B --> C[Create Code Challenge]
    C --> D[Auth Request with Challenge]
    D --> E[User Authenticates]
    E --> F[Receive Auth Code]
    F --> G[Token Request with Verifier]
    G --> H{CF Validates}
    H -->|Match| I[Issue Access Token]
    H -->|No Match| J[Reject Request]
    I --> K[Claude.ai Has Token]

    style A fill:#e1f5ff
    style K fill:#c8e6c9
    style J fill:#ffcdd2
```

## Token Lifecycle

```mermaid
stateDiagram-v2
    [*] --> NoToken: User Starts
    NoToken --> Authorizing: Initiate OAuth
    Authorizing --> TokenReceived: Auth Success
    Authorizing --> Failed: Auth Failed
    TokenReceived --> TokenValid: Token Active
    TokenValid --> TokenExpired: 24 Hours
    TokenExpired --> Authorizing: Refresh
    TokenValid --> [*]: User Disconnects
    Failed --> NoToken: Retry

    note right of TokenValid
        Token used for all
        MCP requests
    end note

    note right of TokenExpired
        Auto-refresh or
        re-authenticate
    end note
```

## Authentication Middleware Flow

```mermaid
flowchart TD
    A[HTTP Request] --> B{Path Check}
    B -->|OAuth Endpoints| C[Skip Auth]
    B -->|Public Endpoints| C
    B -->|Protected| D[Extract Token]

    D --> E{Token Present?}
    E -->|No| F[401 Unauthorized]
    E -->|Yes| G{Cloudflare Access?}

    G -->|Enabled| H[Validate CF JWT]
    G -->|Disabled| I[Validate Bearer Token]

    H --> J{Valid?}
    I --> J

    J -->|Yes| K[Allow Request]
    J -->|No| L[403 Forbidden]

    C --> K
    K --> M[Continue to Handler]

    style F fill:#ffcdd2
    style L fill:#ffcdd2
    style M fill:#c8e6c9
```

## Multi-Client Authentication

```mermaid
flowchart LR
    subgraph Claude.ai
        A1[MCP Client]
    end

    subgraph Cursor
        B1[MCP Client]
    end

    subgraph Claude Code
        C1[MCP Client<br/>stdio]
    end

    subgraph Web Browser
        D1[Web UI]
    end

    A1 -->|OAuth 2.0| E[Cloudflare Access]
    B1 -->|OAuth 2.0| E
    D1 -->|Session Cookie| E
    C1 -->|No Auth<br/>localhost| F[MCP Server]

    E -->|Valid JWT| F
    F -->|HTTP + Bearer| G[Backend API]

    style C1 fill:#fff9c4
    style E fill:#e1bee7
    style F fill:#b2dfdb
    style G fill:#bbdefb
```

## Cloudflare Access Policy Evaluation

```mermaid
flowchart TD
    A[Request to /mcp] --> B{Cloudflare Access}
    B --> C{Email in Policy?}
    C -->|No| D[Deny Access]
    C -->|Yes| E{MFA Passed?}
    E -->|No| F[Request OTP]
    F --> G[User Enters OTP]
    G --> H{OTP Valid?}
    H -->|No| D
    H -->|Yes| I[Issue JWT]
    E -->|Yes| I
    I --> J[Forward to Backend]
    J --> K[MCP Request Processed]

    style D fill:#ffcdd2
    style K fill:#c8e6c9
```

## Token Validation Process

```mermaid
sequenceDiagram
    participant Client
    participant Backend
    participant CF as Cloudflare
    participant Cache

    Client->>Backend: Request + JWT
    Backend->>Cache: Check Public Keys

    alt Keys Cached
        Cache-->>Backend: Return Keys
    else Keys Not Cached
        Backend->>CF: Fetch Public Keys
        CF-->>Backend: Return Keys
        Backend->>Cache: Cache Keys (1h)
    end

    Backend->>Backend: Validate JWT Signature
    Backend->>Backend: Check Expiration
    Backend->>Backend: Check Audience

    alt Valid Token
        Backend->>Client: Process Request
    else Invalid Token
        Backend->>Client: 403 Forbidden
    end
```

## Error Recovery Flow

```mermaid
flowchart TD
    A[MCP Request] --> B{Token Valid?}
    B -->|Yes| C[Process Request]
    B -->|No| D[401/403 Error]
    D --> E{Auto-Refresh?}
    E -->|Yes| F[Refresh Token]
    E -->|No| G[Prompt User]
    F --> H{Success?}
    H -->|Yes| A
    H -->|No| G
    G --> I[User Re-authenticates]
    I --> A

    style C fill:#c8e6c9
    style D fill:#ffcdd2
    style I fill:#fff9c4
```

## Related Documentation

- [Claude.ai Integration Guide](../CLAUDE-AI-INTEGRATION.md)
- [Authentication Guide](../AUTHENTICATION.md)
- [MCP Integration](../mcp-integration.md)
- [Architecture Overview](../ARCHITECTURE.md)
