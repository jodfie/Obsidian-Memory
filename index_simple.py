#!/usr/bin/env python3
"""Simple vault indexer - more forgiving of frontmatter formats."""

import asyncio
import json
import hashlib
import os
from pathlib import Path
from datetime import datetime

import aiosqlite
import frontmatter

VAULTS_DIR = Path(os.environ.get("VAULT_PATH", "/vaults"))
DB_PATH = Path.home() / ".obsidian-memory" / "search.db"

async def create_schema(db):
    """Create database schema."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vault_name TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            tags TEXT,
            note_type TEXT DEFAULT 'note',
            indexed_at TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            UNIQUE(vault_name, relative_path)
        )
    """)
    await db.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            title, content, tags,
            content='notes',
            content_rowid='id'
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_vault ON notes(vault_name)")
    await db.commit()

async def index_file(db, vault_name: str, file_path: Path, vault_path: Path):
    """Index a single markdown file."""
    try:
        content = file_path.read_text(encoding='utf-8')
        relative_path = str(file_path.relative_to(vault_path))
        
        # Parse frontmatter (tolerant)
        try:
            post = frontmatter.loads(content)
            fm = dict(post.metadata) if hasattr(post, 'metadata') else {}
            body = post.content if hasattr(post, 'content') else content
        except:
            fm = {}
            body = content
        
        title = fm.get('title', file_path.stem)
        tags = fm.get('tags', [])
        if isinstance(tags, list):
            tags = ','.join(str(t) for t in tags)
        note_type = fm.get('type', 'note')
        file_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        # Upsert
        await db.execute("""
            INSERT INTO notes (vault_name, relative_path, title, content, tags, note_type, indexed_at, file_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(vault_name, relative_path) DO UPDATE SET
                title=excluded.title,
                content=excluded.content,
                tags=excluded.tags,
                note_type=excluded.note_type,
                indexed_at=excluded.indexed_at,
                file_hash=excluded.file_hash
        """, (vault_name, relative_path, title, body, tags, note_type, datetime.utcnow().isoformat(), file_hash))
        
        return True
    except Exception as e:
        print(f"   ⚠️  {file_path.name}: {e}")
        return False

async def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await create_schema(db)
        
        total = 0
        for vault_dir in VAULTS_DIR.iterdir():
            if not vault_dir.is_dir() or vault_dir.name.startswith('.'):
                continue
            
            print(f"\n📁 Indexing: {vault_dir.name}")
            files = list(vault_dir.rglob("*.md"))
            print(f"   Found {len(files)} files")
            
            indexed = 0
            for f in files:
                if await index_file(db, vault_dir.name, f, vault_dir):
                    indexed += 1
            
            print(f"   ✅ Indexed {indexed}/{len(files)}")
            total += indexed
        
        await db.commit()
        
        # Rebuild FTS
        await db.execute("INSERT INTO notes_fts(notes_fts) VALUES('rebuild')")
        await db.commit()
        
        print(f"\n🎉 Total: {total} notes indexed")
        
        # Quick stats
        cursor = await db.execute("SELECT vault_name, COUNT(*) FROM notes GROUP BY vault_name")
        print("\n📊 By vault:")
        async for row in cursor:
            print(f"   {row[0]}: {row[1]}")

if __name__ == "__main__":
    asyncio.run(main())
