# Obsidian-Memory Scripts

Utility scripts for managing Obsidian-Memory data.

## Migration Script: `migrate_to_supabase.py`

Migrates existing Obsidian vault `.md` files and SQLite session data to Supabase Postgres.

### Features

- Parses all `.md` files recursively from your vault
- Extracts YAML frontmatter into JSONB
- Extracts wikilinks `[[...]]` with surrounding context
- Extracts `#tags` with surrounding context
- Migrates existing SQLite sessions data (if present)
- Supports `--dry-run` mode to preview changes
- Batch inserts for efficiency (50 notes, 100 relations per batch)
- Continues on single file failures - won't abort entire migration
- Detailed progress logging

### Prerequisites

1. **Python 3.10+**

2. **Install dependencies:**

   ```bash
   pip install supabase python-frontmatter python-dotenv
   ```

3. **Supabase project setup:**
   - Create a Supabase project at https://supabase.com
   - Run the schema migrations from `supabase/migrations/`
   - Get your project URL and service role key from Settings > API

4. **Environment variables** (create `.env` file or set in environment):

   ```bash
   # Required
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-service-role-key  # NOT the anon key
   MIGRATION_USER_ID=your-user-uuid     # UUID from auth.users table

   # Optional - use existing Obsidian-Memory .env
   # VAULT_PATH=/path/to/vault
   ```

### Usage

#### Dry Run (Preview)

Always start with a dry run to see what will be migrated:

```bash
python scripts/migrate_to_supabase.py \
    --vault-path /path/to/your/vault \
    --dry-run
```

#### Full Migration

```bash
python scripts/migrate_to_supabase.py \
    --vault-path /path/to/your/vault
```

#### With SQLite Sessions

If you have existing session data in SQLite:

```bash
python scripts/migrate_to_supabase.py \
    --vault-path /path/to/your/vault \
    --sqlite-db /path/to/sessions.db
```

#### Custom Excludes

By default, these directories are excluded:
- `node_modules`
- `.git`
- `.obsidian`
- `.trash`
- `__pycache__`
- `.venv`, `venv`

Add custom excludes:

```bash
python scripts/migrate_to_supabase.py \
    --vault-path ./brain \
    --exclude node_modules .git .obsidian Archive
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `--vault-path PATH` | **Required.** Path to Obsidian vault directory |
| `--sqlite-db PATH` | Optional path to SQLite database with sessions |
| `--dry-run` | Preview migration without inserting data |
| `--exclude PATTERN...` | Directory patterns to exclude |
| `--env-file PATH` | Path to `.env` file (default: `.env`) |
| `--verbose, -v` | Enable debug logging |

### Output

The script logs progress as it runs:

```
2026-02-05 16:30:00 - INFO - Scanning vault: /path/to/your/vault
2026-02-05 16:30:00 - INFO - Found 813 markdown files
2026-02-05 16:30:00 - INFO - Parsing markdown files...
2026-02-05 16:30:01 - INFO - Parsed 100/813 files...
2026-02-05 16:30:02 - INFO - Parsed 200/813 files...
...
2026-02-05 16:30:05 - INFO - Successfully parsed 813 notes with 2456 relations
2026-02-05 16:30:05 - INFO - Migrating 813 notes to Supabase...
2026-02-05 16:30:06 - INFO - Inserted batch: 1-50/813 notes
...
```

### Data Mapping

| Source | Supabase Table | Notes |
|--------|---------------|-------|
| `.md` file path | `notes.path` | Relative to vault root |
| Frontmatter `title` or filename | `notes.title` | Falls back to filename |
| Markdown content | `notes.content` | Body without frontmatter |
| YAML frontmatter | `notes.frontmatter` | Stored as JSONB |
| `[[wikilink]]` | `relations` | `relation_type = 'wikilink'` |
| `#tag` | `relations` | `relation_type = 'tag'`, target = `#/tagname` |
| SQLite sessions | `sessions` | Preserves events as JSONB |

### Error Handling

- Individual file parsing failures are logged but don't stop migration
- Batch insert failures are logged with error details
- Exit code 1 if any failures occurred
- Exit code 0 if all successful

### Troubleshooting

**"Missing required environment variables"**
- Ensure `SUPABASE_URL`, `SUPABASE_KEY`, and `MIGRATION_USER_ID` are set
- Check your `.env` file exists in the current directory or use `--env-file`

**"Vault path does not exist"**
- Verify the path exists: `ls /path/to/vault`
- Use absolute paths to avoid confusion

**"permission denied" or RLS errors**
- Make sure you're using the **service role key**, not the anon key
- The service role key bypasses Row Level Security

**"user_id violates foreign key constraint"**
- The `MIGRATION_USER_ID` must be a valid UUID in `auth.users`
- Create a user first via Supabase Auth or SQL

### Getting the MIGRATION_USER_ID

You can find or create a user ID in Supabase:

1. **Via Supabase Dashboard:**
   - Go to Authentication > Users
   - Copy the UUID of your user

2. **Via SQL Editor:**
   ```sql
   -- Find existing users
   SELECT id, email FROM auth.users;

   -- Or create a user for migration
   INSERT INTO auth.users (id, email, encrypted_password, email_confirmed_at)
   VALUES (
       gen_random_uuid(),
       'migration@example.com',
       crypt('temp-password', gen_salt('bf')),
       now()
   )
   RETURNING id;
   ```

### Re-running Migration

The script uses `upsert` for notes (based on `path`), so you can safely re-run it:
- Existing notes with same path will be updated
- New notes will be inserted
- Relations are always inserted (may create duplicates if re-run)

To do a clean re-migration:

```sql
-- In Supabase SQL Editor
DELETE FROM relations WHERE source_id IN (
    SELECT id FROM notes WHERE user_id = 'your-user-id'
);
DELETE FROM notes WHERE user_id = 'your-user-id';
DELETE FROM sessions WHERE user_id = 'your-user-id';
```

---

## Other Scripts

### `bitwarden-helper.sh`
Helper for BitWarden Secrets Manager integration.

### `deploy-server.sh`
Deployment script for server updates.

### `cleanup-branches.sh`
Git branch cleanup utility.

### `configure-cloudflare-access.py`
Automated Cloudflare Access setup.

### `enhanced-session-consolidation.py`
Session consolidation for Clawdbot integration.

### `index_vault.py`
Local vault indexing for search.
