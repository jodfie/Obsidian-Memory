# Obsidian-Memory SDK Examples

Example client libraries for the Obsidian-Memory API.

## Python SDK

Located in `python/obsidian_memory_client.py`.

### Installation

```bash
cd examples/python
pip install -r requirements.txt
```

### Usage

```python
from obsidian_memory_client import ObsidianMemoryClient

# Initialize client
client = ObsidianMemoryClient(
    base_url="http://localhost:8000",
    auth_token="your-token"  # Optional
)

# List notes
notes, total = client.list_notes(limit=10)

# Search
results, count = client.search("machine learning", project="research")

# Create a note
note = client.create_note(
    vault_name="my-vault",
    title="New Note",
    content="# My Note\n\nContent here..."
)

# Supersede a note
result = client.supersede_note(
    old_note_id=1,
    new_note_id=2,
    reason="Updated with latest findings"
)
```

### Run Example

```bash
python obsidian_memory_client.py
```

## TypeScript SDK

Located in `typescript/obsidian-memory-client.ts`.

### Installation

```bash
cd examples/typescript
npm install
```

### Usage

```typescript
import { ObsidianMemoryClient } from './obsidian-memory-client';

// Initialize client
const client = new ObsidianMemoryClient({
  baseUrl: 'http://localhost:8000',
  authToken: 'your-token',  // Optional
});

// List notes
const { notes, total } = await client.listNotes({ limit: 10 });

// Search
const results = await client.search('machine learning', { project: 'research' });

// Create a note
const note = await client.createNote({
  vaultName: 'my-vault',
  title: 'New Note',
  content: '# My Note\n\nContent here...',
});

// Supersede a note
const result = await client.supersedeNote(1, 2, 'Updated with latest findings');
```

### Run Example

```bash
npm run example
```

## Error Handling

Both SDKs provide typed error classes:

| Error | Status Code | Description |
|-------|-------------|-------------|
| `AuthenticationError` | 401/403 | Invalid or missing credentials |
| `NotFoundError` | 404 | Resource not found |
| `RateLimitError` | 429 | Rate limit exceeded |
| `ObsidianMemoryError` | Various | Base error class |

### Python

```python
from obsidian_memory_client import (
    ObsidianMemoryClient,
    RateLimitError,
    NotFoundError,
    AuthenticationError,
)

try:
    note = client.get_note(999)
except NotFoundError:
    print("Note not found")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except AuthenticationError:
    print("Check your credentials")
```

### TypeScript

```typescript
import {
  ObsidianMemoryClient,
  RateLimitError,
  NotFoundError,
  AuthenticationError,
} from './obsidian-memory-client';

try {
  const note = await client.getNote(999);
} catch (error) {
  if (error instanceof NotFoundError) {
    console.log('Note not found');
  } else if (error instanceof RateLimitError) {
    console.log(`Rate limited. Retry after ${error.retryAfter} seconds`);
  } else if (error instanceof AuthenticationError) {
    console.log('Check your credentials');
  }
}
```

## Rate Limiting

The API includes rate limiting headers in all responses:

- `X-RateLimit-Limit` - Maximum requests per minute
- `X-RateLimit-Remaining` - Remaining requests in current window
- `X-RateLimit-Reset` - Unix timestamp when limit resets

When rate limited (HTTP 429), check the `Retry-After` header or `retry_after`/`retryAfter` property.

## API Documentation

See the main [API documentation](../docs/api.md) for complete endpoint reference.
