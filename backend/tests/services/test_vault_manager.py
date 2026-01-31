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
    with pytest.raises(ValueError):
        await vault_manager.read_file("../outside.md")

    with pytest.raises(ValueError):
        await vault_manager.read_file("/absolute/path.md")


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


def test_validate_vault_config_valid(vault_manager: VaultManager) -> None:
    """Test validating a valid vault configuration."""
    vault = vault_manager.get_vault("test_vault")
    errors = vault_manager.validate_vault_config(vault)
    assert len(errors) == 0


def test_validate_vault_config_nonexistent_path(temp_dir: Path) -> None:
    """Test validation fails for non-existent path."""
    manager = VaultManager(VaultManagerConfig(vaults=[], default_vault=None))
    vault = VaultConfig(name="invalid", path=temp_dir / "nonexistent")
    errors = manager.validate_vault_config(vault)
    assert len(errors) > 0
    assert any("does not exist" in err for err in errors)


def test_validate_vault_config_not_directory(temp_dir: Path) -> None:
    """Test validation fails when path is not a directory."""
    manager = VaultManager(VaultManagerConfig(vaults=[], default_vault=None))
    # Create a file instead of a directory
    file_path = temp_dir / "not_a_dir.txt"
    file_path.write_text("not a directory")
    vault = VaultConfig(name="invalid", path=file_path)
    errors = manager.validate_vault_config(vault)
    assert len(errors) > 0
    assert any("not a directory" in err for err in errors)


def test_validate_vault_config_read_only(temp_dir: Path) -> None:
    """Test validation passes for read-only vault."""
    manager = VaultManager(VaultManagerConfig(vaults=[], default_vault=None))
    vault_path = temp_dir / "readonly"
    vault_path.mkdir()
    vault = VaultConfig(name="readonly", path=vault_path, read_only=True)
    errors = manager.validate_vault_config(vault)
    # Should pass even if not writable (because it's read-only)
    assert len(errors) == 0


def test_validate_vault_config_memory_folder(temp_dir: Path) -> None:
    """Test validation checks memory folder accessibility."""
    manager = VaultManager(VaultManagerConfig(vaults=[], default_vault=None))
    vault_path = temp_dir / "with_memory"
    vault_path.mkdir()
    memory_path = vault_path / "_claude-mem"
    memory_path.mkdir()

    vault = VaultConfig(name="test", path=vault_path, memory_folder="_claude-mem")
    errors = manager.validate_vault_config(vault)
    assert len(errors) == 0


def test_validate_vault_config_memory_folder_not_dir(temp_dir: Path) -> None:
    """Test validation fails when memory folder exists but is not a directory."""
    manager = VaultManager(VaultManagerConfig(vaults=[], default_vault=None))
    vault_path = temp_dir / "bad_memory"
    vault_path.mkdir()
    # Create a file with the memory folder name
    memory_path = vault_path / "_claude-mem"
    memory_path.write_text("not a directory")

    vault = VaultConfig(name="test", path=vault_path, memory_folder="_claude-mem")
    errors = manager.validate_vault_config(vault)
    assert len(errors) > 0
    assert any("not a directory" in err for err in errors)


def test_validate_all_vaults(vault_manager: VaultManager, temp_dir: Path) -> None:
    """Test validation of all vaults."""
    # Create the readonly vault directory so it validates
    readonly_path = temp_dir / "readonly_vault"
    readonly_path.mkdir(exist_ok=True)

    validation_results = vault_manager.validate_all_vaults()
    # Both vaults should be valid (no errors)
    assert len(validation_results) == 0


def test_validate_all_vaults_with_errors(temp_dir: Path) -> None:
    """Test validation of all vaults with some invalid."""
    vault_path = temp_dir / "valid_vault"
    vault_path.mkdir()

    config = VaultManagerConfig(
        vaults=[
            VaultConfig(name="valid", path=vault_path),
            VaultConfig(name="invalid", path=temp_dir / "nonexistent"),
        ],
        default_vault="valid",
    )
    manager = VaultManager(config)

    validation_results = manager.validate_all_vaults()
    assert len(validation_results) == 1
    assert "invalid" in validation_results
    assert len(validation_results["invalid"]) > 0


def test_vault_name_validation() -> None:
    """Test vault name validation."""
    # Valid names
    valid_names = ["test_vault", "my-vault", "vault123", "ABC_XYZ-123"]
    for name in valid_names:
        config = VaultConfig(name=name, path=Path("/tmp/test"))
        assert config.name == name

    # Invalid names
    invalid_names = ["vault with spaces", "vault@special", "vault/slash", "vault.dot"]
    for name in invalid_names:
        with pytest.raises(ValueError):
            VaultConfig(name=name, path=Path("/tmp/test"))


def test_initialize_memory_structure(vault_manager: VaultManager) -> None:
    """Test initializing memory folder structure."""
    vault_manager.initialize_memory_structure("test_vault")

    vault = vault_manager.get_vault("test_vault")
    memory_path = vault.path / vault.memory_folder

    # Check all expected folders exist
    assert (memory_path / "projects").exists()
    assert (memory_path / "global" / "patterns").exists()
    assert (memory_path / "sessions").exists()


def test_initialize_memory_structure_read_only(
    vault_manager: VaultManager,
) -> None:
    """Test initializing memory structure fails for read-only vault."""
    with pytest.raises(VaultReadOnlyError):
        vault_manager.initialize_memory_structure("readonly_vault")


def test_initialize_memory_structure_idempotent(
    vault_manager: VaultManager,
) -> None:
    """Test that initialize_memory_structure is idempotent."""
    # Initialize twice - should not raise error
    vault_manager.initialize_memory_structure("test_vault")
    vault_manager.initialize_memory_structure("test_vault")

    vault = vault_manager.get_vault("test_vault")
    memory_path = vault.path / vault.memory_folder

    # Check structure still exists
    assert (memory_path / "projects").exists()


def test_ensure_memory_folder(vault_manager: VaultManager) -> None:
    """Test ensuring memory folder exists."""
    vault_manager.ensure_memory_folder("test_vault")

    vault = vault_manager.get_vault("test_vault")
    memory_path = vault.path / vault.memory_folder

    assert memory_path.exists()
    assert memory_path.is_dir()


def test_ensure_memory_folder_idempotent(vault_manager: VaultManager) -> None:
    """Test that ensure_memory_folder is idempotent."""
    vault_manager.ensure_memory_folder("test_vault")
    vault_manager.ensure_memory_folder("test_vault")

    vault = vault_manager.get_vault("test_vault")
    memory_path = vault.path / vault.memory_folder

    assert memory_path.exists()


def test_ensure_memory_folder_read_only(vault_manager: VaultManager) -> None:
    """Test ensuring memory folder fails for read-only vault without folder."""
    with pytest.raises(VaultReadOnlyError):
        vault_manager.ensure_memory_folder("readonly_vault")


def test_list_projects_empty(vault_manager: VaultManager) -> None:
    """Test listing projects when none exist."""
    projects = vault_manager.list_projects("test_vault")
    assert projects == []


def test_list_projects(vault_manager: VaultManager) -> None:
    """Test listing projects."""
    # Initialize memory structure
    vault_manager.initialize_memory_structure("test_vault")

    # Create some projects
    vault_manager.create_project("test_vault", "project1")
    vault_manager.create_project("test_vault", "project2")

    projects = vault_manager.list_projects("test_vault")
    assert len(projects) == 2
    assert "project1" in projects
    assert "project2" in projects


def test_list_projects_no_memory_folder(vault_manager: VaultManager) -> None:
    """Test listing projects when memory folder doesn't exist."""
    projects = vault_manager.list_projects("test_vault")
    assert projects == []


def test_create_project(vault_manager: VaultManager) -> None:
    """Test creating a project."""
    vault_manager.create_project("test_vault", "test-project")

    vault = vault_manager.get_vault("test_vault")
    project_path = vault.path / vault.memory_folder / "projects" / "test-project"

    # Check all subfolders were created
    assert (project_path / "decisions").exists()
    assert (project_path / "errors").exists()
    assert (project_path / "knowledge").exists()
    assert (project_path / "patterns").exists()
    assert (project_path / "sessions").exists()


def test_create_project_read_only(vault_manager: VaultManager) -> None:
    """Test creating project fails in read-only vault."""
    with pytest.raises(VaultReadOnlyError):
        vault_manager.create_project("readonly_vault", "test")


def test_create_project_invalid_name(vault_manager: VaultManager) -> None:
    """Test creating project with invalid name fails."""
    invalid_names = ["project with spaces", "project@special", "project/slash"]
    for name in invalid_names:
        with pytest.raises(ValueError, match="Invalid project name"):
            vault_manager.create_project("test_vault", name)


def test_create_project_idempotent(vault_manager: VaultManager) -> None:
    """Test that create_project is idempotent."""
    vault_manager.create_project("test_vault", "test-project")
    vault_manager.create_project("test_vault", "test-project")  # Should not fail

    vault = vault_manager.get_vault("test_vault")
    project_path = vault.path / vault.memory_folder / "projects" / "test-project"

    assert project_path.exists()


@pytest.mark.asyncio
async def test_get_vault_status(vault_manager: VaultManager) -> None:
    """Test getting vault status."""
    vault_status = await vault_manager.get_vault_status("test_vault")

    assert vault_status.name == "test_vault"
    assert vault_status.is_accessible is True
    assert vault_status.is_writable is True  # Not read-only
    assert vault_status.file_count is not None
    assert vault_status.disk_usage_bytes is not None
    assert vault_status.memory_folder_exists is False  # Not initialized yet
    assert len(vault_status.validation_errors) == 0


@pytest.mark.asyncio
async def test_get_vault_status_with_files(vault_manager: VaultManager) -> None:
    """Test vault status includes file count and disk usage."""
    # Create some files
    await vault_manager.write_file("test1.md", "content 1")
    await vault_manager.write_file("test2.md", "longer content here")

    vault_status = await vault_manager.get_vault_status("test_vault")

    assert vault_status.file_count == 2
    assert vault_status.disk_usage_bytes > 0
    assert vault_status.last_modified is not None


@pytest.mark.asyncio
async def test_get_vault_status_read_only(vault_manager: VaultManager) -> None:
    """Test status for read-only vault."""
    vault_status = await vault_manager.get_vault_status("readonly_vault")

    assert vault_status.name == "readonly_vault"
    assert vault_status.is_writable is False  # Read-only
