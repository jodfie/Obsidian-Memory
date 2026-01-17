"""Git sync service for vault synchronization."""

import asyncio
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.exceptions import (
    GitNotAvailableError,
    SyncConflictError,
    SyncError,
    VaultError,
)


class SyncService:
    """Service for synchronizing vaults with Git repositories."""

    def __init__(self, vault_path: Path, device_id: str | None = None) -> None:
        """Initialize sync service for a vault.

        Args:
            vault_path: Path to the vault directory
            device_id: Optional device identifier for cross-device tracking
        """
        self.vault_path = vault_path
        self.device_id = device_id or self._generate_device_id()
        self._git_available: bool | None = None

    @staticmethod
    def _generate_device_id() -> str:
        """Generate a device identifier.

        Returns:
            Device identifier string
        """
        import socket

        hostname = socket.gethostname()
        system = platform.system()
        return f"{system}-{hostname}"

    async def _check_git_available(self) -> bool:
        """Check if Git is available."""
        if self._git_available is not None:
            return self._git_available

        try:
            result = await asyncio.create_subprocess_exec(
                'git',
                '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.wait()
            self._git_available = result.returncode == 0
            return self._git_available
        except Exception:
            self._git_available = False
            return False

    async def _run_git_command(
        self, *args: str, check: bool = True
    ) -> tuple[str, str, int]:
        """Run a Git command and return stdout, stderr, and return code.

        Args:
            *args: Git command arguments
            check: If True, raise exception on non-zero return code

        Returns:
            Tuple of (stdout, stderr, return_code)

        Raises:
            GitNotAvailableError: If Git is not available
            SyncError: If command fails and check=True
        """
        if not await self._check_git_available():
            raise GitNotAvailableError('Git is not available on this system')

        process = await asyncio.create_subprocess_exec(
            'git',
            *args,
            cwd=str(self.vault_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()
        return_code = await process.wait()

        stdout_text = stdout.decode('utf-8', errors='replace')
        stderr_text = stderr.decode('utf-8', errors='replace')

        if check and return_code != 0:
            raise SyncError(
                f'Git command failed: git {" ".join(args)}\n'
                f'Return code: {return_code}\n'
                f'Stderr: {stderr_text}'
            )

        return stdout_text, stderr_text, return_code

    async def is_git_repo(self) -> bool:
        """Check if vault is a Git repository.

        Returns:
            True if vault is a Git repository
        """
        try:
            _, _, return_code = await self._run_git_command(
                'rev-parse', '--git-dir', check=False
            )
            return return_code == 0
        except GitNotAvailableError:
            return False

    async def init_repo(self) -> None:
        """Initialize Git repository in vault.

        Raises:
            SyncError: If initialization fails
        """
        if await self.is_git_repo():
            return  # Already initialized

        await self._run_git_command('init')
        # Add .gitignore if it exists
        gitignore_path = self.vault_path / '.gitignore'
        if gitignore_path.exists():
            await self._run_git_command('add', '.gitignore')

    async def get_status(self) -> dict[str, Any]:
        """Get Git status of the vault.

        Returns:
            Dictionary with status information including device_id
        """
        if not await self.is_git_repo():
            return {
                'is_repo': False,
                'has_remote': False,
                'modified_files': [],
                'untracked_files': [],
                'conflicts': [],
                'device_id': self.device_id,
            }

        # Get status
        stdout, _, _ = await self._run_git_command('status', '--porcelain')
        lines = stdout.strip().split('\n') if stdout.strip() else []

        modified_files = []
        untracked_files = []
        conflicts = []

        for line in lines:
            if not line.strip():
                continue
            status = line[:2]
            filename = line[3:].strip()

            if status.startswith('U') or status.endswith('U') or 'AA' in status or 'DD' in status:
                conflicts.append(filename)
            elif status.startswith('??'):
                untracked_files.append(filename)
            elif status != '  ':
                modified_files.append(filename)

        # Check for remote
        stdout, _, return_code = await self._run_git_command(
            'remote', 'get-url', 'origin', check=False
        )
        has_remote = return_code == 0

        return {
            'is_repo': True,
            'has_remote': has_remote,
            'modified_files': modified_files,
            'untracked_files': untracked_files,
            'conflicts': conflicts,
            'device_id': self.device_id,
        }

    async def add_remote(self, url: str, name: str = 'origin') -> None:
        """Add a remote repository.

        Args:
            url: Remote repository URL
            name: Remote name (default: 'origin')
        """
        # Check if remote already exists
        stdout, _, return_code = await self._run_git_command(
            'remote', 'get-url', name, check=False
        )
        if return_code == 0:
            # Update existing remote
            await self._run_git_command('remote', 'set-url', name, url)
        else:
            # Add new remote
            await self._run_git_command('remote', 'add', name, url)

    async def commit_changes(
        self, message: str, author: str | None = None
    ) -> None:
        """Commit all changes in the vault.

        Args:
            message: Commit message
            author: Optional author (format: "Name <email>")
        """
        # Check if there are changes to commit
        status = await self.get_status()
        if (
            not status['modified_files']
            and not status['untracked_files']
            and not status['conflicts']
        ):
            return  # Nothing to commit

        # Add all changes
        await self._run_git_command('add', '-A')

        # Commit
        commit_args = ['commit', '-m', message]
        if author:
            commit_args.extend(['--author', author])

        await self._run_git_command(*commit_args)

    async def pull(self, remote: str = 'origin', branch: str = 'main') -> dict[str, Any]:
        """Pull changes from remote repository.

        Args:
            remote: Remote name (default: 'origin')
            branch: Branch name (default: 'main')

        Returns:
            Dictionary with pull result information

        Raises:
            SyncConflictError: If conflicts are detected
        """
        # Fetch first
        await self._run_git_command('fetch', remote, branch)

        # Check for conflicts before merge
        await self._run_git_command('merge', '--no-commit', '--no-ff', f'{remote}/{branch}')

        status = await self.get_status()
        if status['conflicts']:
            # Abort merge
            await self._run_git_command('merge', '--abort')
            raise SyncConflictError(
                f'Merge conflicts detected: {", ".join(status["conflicts"])}'
            )

        # Complete merge
        await self._run_git_command('commit', '--no-edit')

        return {
            'success': True,
            'conflicts': [],
            'updated_files': status['modified_files'],
        }

    async def push(
        self, remote: str = 'origin', branch: str = 'main'
    ) -> dict[str, Any]:
        """Push changes to remote repository.

        Args:
            remote: Remote name (default: 'origin')
            branch: Branch name (default: 'main')

        Returns:
            Dictionary with push result information
        """
        await self._run_git_command('push', remote, branch)

        return {'success': True}

    async def sync(
        self, remote: str = 'origin', branch: str = 'main'
    ) -> dict[str, Any]:
        """Perform full sync: pull, commit local changes, push.

        Args:
            remote: Remote name (default: 'origin')
            branch: Branch name (default: 'main')

        Returns:
            Dictionary with sync result information including device_id and sync_time

        Raises:
            SyncConflictError: If conflicts are detected
        """
        result: dict[str, Any] = {
            'pulled': False,
            'committed': False,
            'pushed': False,
            'conflicts': [],
            'device_id': self.device_id,
            'sync_time': datetime.now().isoformat(),
        }

        # Pull changes
        try:
            pull_result = await self.pull(remote, branch)
            result['pulled'] = True
            result['conflicts'] = pull_result.get('conflicts', [])
            result['updated_files'] = pull_result.get('updated_files', [])
        except SyncConflictError as e:
            result['conflicts'] = [str(e)]
            raise
        except Exception:
            # No remote or other error - continue with local commit
            pass

        # Commit local changes
        status = await self.get_status()
        if status['modified_files'] or status['untracked_files']:
            commit_message = f'Auto-sync: Update notes from {self.device_id}'
            await self.commit_changes(commit_message)
            result['committed'] = True

        # Push changes
        try:
            await self.push(remote, branch)
            result['pushed'] = True
        except Exception:
            # Push failed (might not have remote)
            pass

        return result
