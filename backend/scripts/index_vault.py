#!/usr/bin/env python3
"""
Bulk index all notes in an Obsidian vault.

Usage:
    python index_vault.py [vault_name] [vault_path]
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.search import IndexedNote
from app.services.markdown_parser import MarkdownParser
from app.services.search_index import SearchIndex, compute_file_hash
from app.config import settings


async def scan_vault(vault_name: str, vault_path: Path) -> list[IndexedNote]:
    """Scan vault directory and parse all markdown files."""
    parser = MarkdownParser()
    notes = []
    
    print(f"📁 Scanning {vault_path}...")
    
    # Find all .md files (excluding .obsidian folder)
    md_files = []
    for md_file in vault_path.rglob("*.md"):
        # Skip .obsidian folder
        if ".obsidian" in md_file.parts:
            continue
        md_files.append(md_file)
    
    total = len(md_files)
    print(f"Found {total} markdown files")
    
    for idx, md_file in enumerate(md_files, 1):
        relative_path = md_file.relative_to(vault_path)
        
        try:
            # Read file content
            content = md_file.read_text(encoding="utf-8")
            file_hash = compute_file_hash(content)
            
            # Parse markdown
            try:
                parsed = parser.parse(content)
            except Exception as parse_error:
                # If parsing fails, create a minimal note with basic metadata
                print(f"⚠️  Partial parse for {relative_path}: {parse_error}")
                
                # Get file timestamps
                stat = md_file.stat()
                created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
                updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                
                # Create minimal note with relative path as permalink (guaranteed unique)
                permalink = str(relative_path)
                note = IndexedNote(
                    note_id=0,
                    vault_name=vault_name,
                    relative_path=str(relative_path),
                    permalink=permalink,
                    title=md_file.stem,
                    note_type="note",
                    project=None,
                    content=content,
                    tags=[],
                    wikilinks=[],
                    relations=[],
                    observations=[],
                    created_at=created_at,
                    updated_at=updated_at,
                    file_hash=file_hash,
                )
                notes.append(note)
                continue
            
            # Get file timestamps
            stat = md_file.stat()
            created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
            updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            
            # Create IndexedNote
            # Access frontmatter attributes directly (it's a Pydantic model, not a dict)
            # ALWAYS use relative path as permalink for guaranteed uniqueness
            # The frontmatter permalink field is preserved in the database but not used as the index key
            permalink = str(relative_path)
            
            title = getattr(parsed.frontmatter, "title", md_file.stem) or md_file.stem
            note_type = str(getattr(parsed.frontmatter, "type", "note") or "note")
            project = getattr(parsed.frontmatter, "project", None)
            
            # Get tags from frontmatter, flatten any nested lists
            tags = getattr(parsed.frontmatter, "tags", []) or []
            flat_tags = []
            for tag in tags:
                if isinstance(tag, list):
                    # Flatten nested lists
                    flat_tags.extend(str(t) for t in tag)
                else:
                    flat_tags.append(str(tag))
            
            note = IndexedNote(
                note_id=0,  # Will be assigned by database
                vault_name=vault_name,
                relative_path=str(relative_path),
                permalink=permalink,
                title=title,
                note_type=note_type,
                project=project,
                content=content,
                tags=flat_tags,
                wikilinks=parsed.wikilinks,
                relations=parsed.relations,
                observations=parsed.observations,
                created_at=created_at,
                updated_at=updated_at,
                file_hash=file_hash,
            )
            
            notes.append(note)
            
            if idx % 50 == 0:
                print(f"  Parsed {idx}/{total} files...")
                
        except Exception as e:
            print(f"❌ Error processing {relative_path}: {e}")
            continue
    
    print(f"✅ Successfully parsed {len(notes)} notes")
    return notes


async def main():
    """Main indexing script."""
    # Parse arguments
    vault_name = sys.argv[1] if len(sys.argv) > 1 else "main"
    vault_path_str = sys.argv[2] if len(sys.argv) > 2 else "/vaults"
    vault_path = Path(vault_path_str)
    
    if not vault_path.exists():
        print(f"❌ Vault path does not exist: {vault_path}")
        sys.exit(1)
    
    print(f"🔍 Indexing vault '{vault_name}' at {vault_path}")
    print()
    
    # Scan vault and parse notes
    notes = await scan_vault(vault_name, vault_path)
    
    if not notes:
        print("❌ No notes found to index")
        sys.exit(1)
    
    # Initialize search index
    print()
    print(f"💾 Initializing search index at {settings.index_db_path}")
    index = SearchIndex(settings.index_db_path)
    await index.initialize()
    
    # Index notes with progress callback
    def progress(current, total):
        if current % 10 == 0 or current == total:
            print(f"  Indexed {current}/{total} notes...")
    
    print()
    print(f"📝 Bulk indexing {len(notes)} notes...")
    added, updated, removed = await index.index_vault(
        vault_name=vault_name,
        notes=notes,
        full_reindex=True,
        progress_callback=progress,
    )
    
    await index.close()
    
    print()
    print("✅ Indexing complete!")
    print(f"   Added: {added}")
    print(f"   Updated: {updated}")
    print(f"   Removed: {removed}")


if __name__ == "__main__":
    asyncio.run(main())
