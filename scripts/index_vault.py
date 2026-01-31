#!/usr/bin/env python3
"""Index all markdown files in a vault."""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.search_index import SearchIndex, compute_file_hash
from app.services.markdown_parser import MarkdownParser
from app.services.vault_manager import VaultManager, VaultManagerConfig
from app.models.vault import VaultConfig
from app.models.search import IndexedNote
from app.config import settings


async def index_vault(vault_name: str, vault_path: Path):
    """Index all markdown files in a vault."""
    print(f"Indexing vault: {vault_name} at {vault_path}")
    
    # Initialize services
    search_index = SearchIndex(settings.index_db_path)
    await search_index.initialize()
    
    parser = MarkdownParser()
    
    # Find all markdown files
    md_files = list(vault_path.rglob("*.md"))
    print(f"Found {len(md_files)} markdown files")
    
    indexed = 0
    errors = 0
    
    for md_file in md_files:
        try:
            # Skip hidden directories
            if any(part.startswith('.') for part in md_file.parts):
                continue
                
            relative_path = str(md_file.relative_to(vault_path))
            content = md_file.read_text(encoding='utf-8')
            
            # Parse markdown
            parsed = parser.parse(content)
            
            # Create indexed note
            file_hash = compute_file_hash(content)
            stat = md_file.stat()
            
            note = IndexedNote(
                vault_name=vault_name,
                relative_path=relative_path,
                permalink=parsed.frontmatter.permalink,
                title=parsed.frontmatter.title or md_file.stem,
                note_type=parsed.frontmatter.type or "note",
                project=parsed.frontmatter.project,
                tags=parsed.frontmatter.tags or [],
                content=content,
                created_at=parsed.frontmatter.created or datetime.fromtimestamp(stat.st_ctime),
                updated_at=parsed.frontmatter.updated or datetime.fromtimestamp(stat.st_mtime),
                file_hash=file_hash,
                observations=[],
                relations=[],
                wikilinks=[],
            )
            
            await search_index.index_note(note)
            indexed += 1
            
            if indexed % 100 == 0:
                print(f"  Indexed {indexed} files...")
                
        except Exception as e:
            print(f"  Error indexing {md_file}: {e}")
            errors += 1
    
    await search_index.close()
    print(f"\nDone! Indexed {indexed} files, {errors} errors")


if __name__ == "__main__":
    vault_name = sys.argv[1] if len(sys.argv) > 1 else "brain"
    vault_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/vaults/brain")
    
    asyncio.run(index_vault(vault_name, vault_path))
