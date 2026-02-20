# SQLite Write Lock Design

## Problem

Concurrent writes from the file watcher and API cause `sqlite3.OperationalError: database is locked`. The SearchIndex singleton shares one aiosqlite connection with no write serialization and no busy_timeout (default 0ms). When both paths call `index_note()` simultaneously, the second writer fails instantly.

## Solution

Add `asyncio.Lock` to serialize all writes + `PRAGMA busy_timeout=5000` as safety net.

## Changes (search_index.py only)

1. Add `import asyncio`
2. `__init__()`: add `self._write_lock = asyncio.Lock()`
3. `initialize()`: add `PRAGMA busy_timeout=5000` after WAL pragma
4. Wrap all public write methods with `async with self._write_lock:`
5. Wrap `_refresh_access()` with lock (called from unlocked `search()`)
6. Do NOT wrap `_incremental_vacuum()` (only called from already-locked `index_vault()`)

### Write methods to lock

| Method | Line | Called From |
|--------|------|-------------|
| `index_note` | 539 | API, file watcher |
| `remove_note` | 767 | API |
| `index_vault` | 2298 | API sync |
| `delete_entities` | 3214 | API |
| `promote_inferred_relation` | 3521 | API |
| `delete_inferred_relation` | 3544 | API |
| `delete_inferred_relations_for_note` | 3561 | API |
| `create_pattern_run` | 3594 | pattern service |
| `store_pattern` | 3604 | pattern service |
| `update_dedup_suggestion_status` | 3804 | API |
| `mark_dedup_suggestion_merged_for_pair` | 3816 | API |
| `decay_confidence` | 2797 | API |
| `_refresh_access` | 2769 | `search()` (read path, needs own lock) |
