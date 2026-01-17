"""Tests for VaultManager service."""

import asyncio
from pathlib import Path

import pytest

from app.models.vault import VaultConfig, VaultManagerConfig
from app.services.exceptions import (
    AtomicWriteError,
    VaultNotFoundError,
    VaultReadOnlyError,
)
from app.services.vault_manager import VaultManager


@pytest.fixture
def vault_config(temp_dir: Path) -> VaultManagerConfig:
    """Create a test vault manager configuration."""
    vault_path = temp_dir / "test_vault"
    vault_path.mkdir()

    return VaultManagerConfig(
        vaults=[
            VaultConfig(
                name="test_vault",
                path=vault_path,
                memory_folder="_claude-mem",
                read_only=False,
            ),
            VaultConfig(
                name="readonly_vault",
                path=temp_dir / "readonly_vault",
                read_only=True,
            ),
        ],
        default_vault="test_vault",
    )


@pytest.fixture
def vault_manager(vault_config: VaultManagerConfig) -> VaultManager:
    """Create a VaultManager instance."""
    return VaultManager(vault_config)


@pytest.mark.asyncio
async def test_read_file_success(vault_manager: VaultManager) -> None:
    """Test reading a file successfully."""
    # Create a test file
    vault_path = vault_manager.get_vault("test_vault").path
    test_file = vault_path / "test.md"
    test_file.write_text("# Test\n\nContent here")

    # Read it
    vault_file = await vault_manager.read_file("test.md", vault="test_vault")

    assert vault_file.vault_name == "test_vault"
    assert vault_file.relative_path == "test.md"
    assert "# Test\n\nContent here" in vault_file.content
    assert vault_file.size_bytes > 0


@pytest.mark.asyncio
async def test_read_file_not_found(vault_manager: VaultManager) -> None:
    """Test reading a non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        await vault_manager.read_file("nonexistent.md")


@pytest.mark.asyncio
async def test_write_file_atomic(vault_manager: VaultManager) -> None:
    """Test writing a file atomically."""
    content = "# New File\n\nThis is new content."
    vault_file = await vault_manager.write_file("new-file.md", content)

    assert vault_file.vault_name == "test_vault"
    assert vault_file.relative_path == "new-file.md"
    assert vault_file.content == content

    # Verify file exists and has correct content
    path = vault_manager.get_vault("test_vault").path / "new-file.md"
    assert path.exists()
    assert path.read_text(encoding="utf-8") == content


@pytest.mark.asyncio
async def test_write_file_creates_dirs(vault_manager: VaultManager) -> None:
    """Test that write_file creates parent directories."""
    content = "Content"
    vault_file = await vault_manager.write_file(
        "nested/deep/path/file.md", content
    )

    assert vault_file.relative_path == "nested/deep/path/file.md"
    path = vault_manager.get_vault("test_vault").path / "nested/deep/path/file.md"
    assert path.exists()


@pytest.mark.asyncio
async def test_write_file_read_only_vault(vault_manager: VaultManager) -> None:
    """Test that writing to a read-only vault raises VaultReadOnlyError."""
    with pytest.raises(VaultReadOnlyError):
        await vault_manager.write_file("test.md", "content", vault="readonly_vault")


@pytest.mark.asyncio
async def test_delete_file_success(vault_manager: VaultManager) -> None:
    """Test deleting a file successfully."""
    # Create a file first
    await vault_manager.write_file("to-delete.md", "content")

    # Delete it
    await vault_manager.delete_file("to-delete.md")

    # Verify it's gone
    assert not await vault_manager.file_exists("to-delete.md")


@pytest.mark.asyncio
async def test_move_file_same_vault(vault_manager: VaultManager) -> None:
    """Test moving a file within the same vault."""
    content = "Moving this file"
    await vault_manager.write_file("source.md", content)

    vault_file = await vault_manager.move_file("source.md", "destination.md")

    assert vault_file.relative_path == "destination.md"
    assert vault_file.content == content
    assert not await vault_manager.file_exists("source.md")
    assert await vault_manager.file_exists("destination.md")


@pytest.mark.asyncio
async def test_move_file_cross_vault(
    vault_manager: VaultManager, temp_dir: Path
) -> None:
    """Test moving a file between vaults."""
    # Create second vault directory
    second_vault_path = temp_dir / "readonly_vault"
    second_vault_path.mkdir(exist_ok=True)

    content = "Cross-vault content"
    await vault_manager.write_file("source.md", content, vault="test_vault")

    # Should fail because readonly_vault is read-only
    with pytest.raises(VaultReadOnlyError):
        await vault_manager.move_file(
            "source.md",
            "destination.md",
            src_vault="test_vault",
            dst_vault="readonly_vault",
        )


@pytest.mark.asyncio
async def test_list_files_recursive(vault_manager: VaultManager) -> None:
    """Test listing files recursively."""
    # Create files in nested structure
    await vault_manager.write_file("root.md", "content")
    await vault_manager.write_file("nested/file.md", "content")
    await vault_manager.write_file("nested/deep/file.md", "content")

    files = await vault_manager.list_files(recursive=True)

    assert "root.md" in files
    assert "nested/file.md" in files
    assert "nested/deep/file.md" in files


@pytest.mark.asyncio
async def test_list_files_pattern(vault_manager: VaultManager) -> None:
    """Test listing files with a pattern."""
    await vault_manager.write_file("note.md", "content")
    await vault_manager.write_file("note.txt", "content")
    await vault_manager.write_file("other.md", "content")

    md_files = await vault_manager.list_files(pattern="*.md")
    assert "note.md" in md_files
    assert "other.md" in md_files
    assert "note.txt" not in md_files


@pytest.mark.asyncio
async def test_path_traversal_blocked(vault_manager: VaultManager) -> None:
    """Test that path traversal attempts are blocked."""
    with pytest.raises(ValueError, match="Invalid path"):
        await vault_manager.read_file("../outside.md")

    with pytest.raises(ValueError, match="Invalid path"):
        await vault_manager.read_file("/absolute/path.md")

    # Try to escape using normalized path - should be caught by normalization check
    with pytest.raises(ValueError):
        vault_path = vault_manager.get_vault("test_vault").path
        parent = vault_path.parent
        relative = Path("..") / parent.name / "escape.md"
        await vault_manager.read_file(str(relative))


@pytest.mark.asyncio
async def test_concurrent_reads(vault_manager: VaultManager) -> None:
    """Test that concurrent reads work correctly."""
    # Create multiple files
    for i in range(5):
        await vault_manager.write_file(f"file{i}.md", f"content {i}")

    # Read them concurrently
    paths = [f"file{i}.md" for i in range(5)]
    files = await vault_manager.read_files(paths)

    assert len(files) == 5
    for i, file in enumerate(files):
        assert f"content {i}" in file.content


@pytest.mark.asyncio
async def test_concurrent_writes_serialized(vault_manager: VaultManager) -> None:
    """Test that concurrent writes are serialized per vault."""
    # Write multiple files concurrently
    tasks = [
        vault_manager.write_file(f"concurrent{i}.md", f"content {i}")
        for i in range(10)
    ]
    files = await asyncio.gather(*tasks)

    # All should succeed
    assert len(files) == 10
    for i, file in enumerate(files):
        assert file.relative_path == f"concurrent{i}.md"
        assert file.content == f"content {i}"


@pytest.mark.asyncio
async def test_memory_path_generation(vault_manager: VaultManager) -> None:
    """Test memory path generation."""
    # Project-specific paths
    assert (
        vault_manager.get_memory_path("error", "auth-bug", project="api")
        == "_claude-mem/projects/api/errors/auth-bug.md"
    )
    assert (
        vault_manager.get_memory_path("decision", "use-jwt", project="api")
        == "_claude-mem/projects/api/decisions/use-jwt.md"
    )
    assert (
        vault_manager.get_memory_path("pattern", "retry-logic", project="api")
        == "_claude-mem/projects/api/patterns/retry-logic.md"
    )

    # Global pattern
    assert (
        vault_manager.get_memory_path("pattern", "global-pattern")
        == "_claude-mem/global/patterns/global-pattern.md"
    )

    # Invalid note types
    with pytest.raises(ValueError):
        vault_manager.get_memory_path("invalid", "test")

    # Non-pattern global notes should fail
    with pytest.raises(ValueError):
        vault_manager.get_memory_path("error", "test")  # No project


@pytest.mark.asyncio
async def test_list_directories(vault_manager: VaultManager) -> None:
    """Test listing directories."""
    # Create nested structure
    await vault_manager.write_file("root.md", "content")
    await vault_manager.write_file("dir1/file1.md", "content")
    await vault_manager.write_file("dir2/file2.md", "content")
    await vault_manager.write_file("dir1/subdir/file.md", "content")

    # List immediate subdirectories only
    dirs = await vault_manager.list_directories()
    assert "dir1" in dirs
    assert "dir2" in dirs

    # List subdirectories of dir1
    dir1_dirs = await vault_manager.list_directories("dir1")
    assert "dir1/subdir" in dir1_dirs


@pytest.mark.asyncio
async def test_file_exists(vault_manager: VaultManager) -> None:
    """Test file_exists method."""
    assert not await vault_manager.file_exists("nonexistent.md")

    await vault_manager.write_file("exists.md", "content")
    assert await vault_manager.file_exists("exists.md")


@pytest.mark.asyncio
async def test_write_files_batch(vault_manager: VaultManager) -> None:
    """Test batch write operation."""
    files = [
        ("batch1.md", "content 1"),
        ("batch2.md", "content 2"),
        ("nested/batch3.md", "content 3"),
    ]

    results = await vault_manager.write_files(files)

    assert len(results) == 3
    for i, result in enumerate(results):
        assert result.content == f"content {i + 1}"


@pytest.mark.asyncio
async def test_vault_not_found(vault_manager: VaultManager) -> None:
    """Test operations with non-existent vault."""
    with pytest.raises(VaultNotFoundError):
        await vault_manager.read_file("test.md", vault="nonexistent")


@pytest.mark.asyncio
async def test_default_vault(vault_manager: VaultManager) -> None:
    """Test using default vault."""
    await vault_manager.write_file("default-test.md", "content")

    # Should use default vault
    file = await vault_manager.read_file("default-test.md")
    assert file.vault_name == "test_vault"


@pytest.mark.asyncio
async def test_set_default_vault(vault_manager: VaultManager) -> None:
    """Test setting default vault."""
    vault_manager.set_default_vault("readonly_vault")

    # Should now use readonly_vault as default
    with pytest.raises(VaultReadOnlyError):
        await vault_manager.write_file("test.md", "content")
