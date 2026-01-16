"""Exception classes for vault operations."""


class VaultError(Exception):
    """Base exception for vault operations."""

    pass


class VaultNotFoundError(VaultError):
    """Raised when a vault name doesn't exist in config."""

    pass


class VaultReadOnlyError(VaultError):
    """Raised when attempting to write to a read-only vault."""

    pass


class AtomicWriteError(VaultError):
    """Raised when atomic write fails (temp file, rename, etc.)."""

    pass
