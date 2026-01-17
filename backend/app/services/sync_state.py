"""Sync state management for cross-device synchronization."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models.sync import SyncStatus


class SyncStateManager:
    """Manages sync state across devices."""

    def __init__(self, state_file: Path) -> None:
        """Initialize sync state manager.

        Args:
            state_file: Path to the sync state file
        """
        self.state_file = state_file
        self._state: dict[str, Any] = {}

    def _load_state(self) -> dict[str, Any]:
        """Load state from file.

        Returns:
            State dictionary
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_state(self) -> None:
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2, default=str)

    def get_sync_status(self, vault_name: str) -> SyncStatus | None:
        """Get sync status for a vault.

        Args:
            vault_name: Name of the vault

        Returns:
            Sync status or None if not found
        """
        self._state = self._load_state()
        vault_state = self._state.get(vault_name)
        if not vault_state:
            return None

        return SyncStatus(
            vault_name=vault_name,
            is_repo=vault_state.get("is_repo", False),
            has_remote=vault_state.get("has_remote", False),
            last_sync_time=datetime.fromisoformat(vault_state["last_sync_time"])
            if vault_state.get("last_sync_time")
            else None,
            last_sync_device=vault_state.get("last_sync_device"),
            sync_state=vault_state.get("sync_state", "idle"),
            modified_files=vault_state.get("modified_files", []),
            untracked_files=vault_state.get("untracked_files", []),
            conflicts=vault_state.get("conflicts", []),
            pending_changes=vault_state.get("pending_changes", 0),
            device_id=vault_state.get("device_id"),
        )

    def update_sync_status(
        self,
        vault_name: str,
        status: dict[str, Any],
        device_id: str | None = None,
    ) -> None:
        """Update sync status for a vault.

        Args:
            vault_name: Name of the vault
            status: Status dictionary from SyncService
            device_id: Optional device identifier
        """
        self._state = self._load_state()
        if vault_name not in self._state:
            self._state[vault_name] = {}

        vault_state = self._state[vault_name]
        vault_state.update(status)
        vault_state["last_sync_time"] = datetime.now().isoformat()
        if device_id:
            vault_state["last_sync_device"] = device_id
            vault_state["device_id"] = device_id

        # Calculate pending changes
        pending = len(status.get("modified_files", [])) + len(
            status.get("untracked_files", [])
        )
        vault_state["pending_changes"] = pending

        self._save_state()

    def set_sync_state(self, vault_name: str, state: str) -> None:
        """Set sync state for a vault.

        Args:
            vault_name: Name of the vault
            state: Sync state (idle, syncing, conflict, error)
        """
        self._state = self._load_state()
        if vault_name not in self._state:
            self._state[vault_name] = {}
        self._state[vault_name]["sync_state"] = state
        self._save_state()

    def get_all_statuses(self) -> dict[str, SyncStatus]:
        """Get sync statuses for all vaults.

        Returns:
            Dictionary mapping vault names to sync statuses
        """
        self._state = self._load_state()
        result = {}
        for vault_name in self._state:
            status = self.get_sync_status(vault_name)
            if status:
                result[vault_name] = status
        return result
