#!/usr/bin/env python3
"""Index all configured vaults."""

import asyncio
import json
from pathlib import Path

# Add backend to path
import sys
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.services.vault_manager import VaultManager, VaultConfig, VaultManagerConfig
from app.services.search_index import SearchIndex
from app.services.markdown_parser import MarkdownParser
from app.models.search import IndexedNote


async def index_all_vaults():
    # Load config
    config_path = Path.home() / ".obsidian-memory" / "config.json"
    with open(config_path) as f:
        config_data = json.load(f)
    
    # Create vault configs
    vaults = [
        VaultConfig(
            name=v["name"],
            path=Path(v["path"]),
            memory_folder=v.get("memory_folder", "_memory"),
            read_only=v.get("read_only", False),
            sync_enabled=v.get("sync_enabled", False),
        )
        for v in config_data["vaults"]
    ]
    
    vault_config = VaultManagerConfig(
        vaults=vaults,
        default_vault=config_data.get("default_vault"),
    )
    
    vault_manager = VaultManager(vault_config)
    
    # Initialize search index
    db_path = Path.home() / ".obsidian-memory" / "search.db"
    search_index = SearchIndex(db_path)
    await search_index.initialize()
    
    # Initialize markdown parser
    parser = MarkdownParser()
    
    total_indexed = 0
    
    for vault in vaults:
        print(f"\n📁 Indexing vault: {vault.name}")
        
        # List all markdown files
        try:
            files = await vault_manager.list_files(vault=vault.name, pattern="**/*.md")
            print(f"   Found {len(files)} files")
            
            notes = []
            for file_path in files:
                try:
                    vault_file = await vault_manager.read_file(file_path, vault=vault.name)
                    parsed = parser.parse(vault_file.content)
                    
                    note = IndexedNote(
                        vault_name=vault.name,
                        relative_path=file_path,
                        title=parsed.frontmatter.get("title", Path(file_path).stem),
                        content=parsed.content,
                        note_type=parsed.frontmatter.get("type", "note"),
                        project=parsed.frontmatter.get("project"),
                        tags=parsed.frontmatter.get("tags", []),
                        permalink=parsed.frontmatter.get("permalink"),
                        frontmatter=parsed.frontmatter,
                        observations=[],
                        relations=[],
                        wikilinks=[],
                        file_hash=str(hash(vault_file.content))[:16],
                    )
                    notes.append(note)
                except Exception as e:
                    print(f"   ⚠️  Error parsing {file_path}: {e}")
            
            # Index the vault
            added, updated, removed = await search_index.index_vault(vault.name, notes, full_reindex=True)
            print(f"   ✅ Indexed: {added} added, {updated} updated, {removed} removed")
            total_indexed += added + updated
            
        except Exception as e:
            print(f"   ❌ Error indexing vault: {e}")
    
    print(f"\n🎉 Total indexed: {total_indexed} notes")
    
    # Close database
    if search_index.db:
        await search_index.db.close()


if __name__ == "__main__":
    asyncio.run(index_all_vaults())
