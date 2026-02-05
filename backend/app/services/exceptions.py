"""Exception classes for vault and parsing operations."""


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


class ParseError(Exception):
    """Base parsing error."""

    def __init__(self, message: str, line_number: int | None = None) -> None:
        self.line_number = line_number
        if line_number:
            super().__init__(f"Line {line_number}: {message}")
        else:
            super().__init__(message)


class FrontmatterError(ParseError):
    """Invalid YAML frontmatter."""

    pass


class InvalidObservationError(ParseError):
    """Observation doesn't match expected format."""

    pass


class InvalidRelationError(ParseError):
    """Relation doesn't match expected format."""

    pass


class AIProcessorError(Exception):
    """Base exception for AI processing errors."""

    pass


class AIProcessorUnavailableError(AIProcessorError):
    """Raised when AI processing is disabled or unavailable."""

    pass


class SyncError(VaultError):
    """Base exception for sync operations."""

    pass


class GitNotAvailableError(SyncError):
    """Raised when Git is not available."""

    pass


class SyncConflictError(SyncError):
    """Raised when sync conflicts are detected."""

    pass


class VaultConfigValidationError(VaultError):
    """Raised when vault configuration validation fails."""

    pass


# Database-backed vault manager exceptions


class DatabaseVaultError(Exception):
    """Base exception for database-backed vault operations."""

    pass


class NoteNotFoundError(DatabaseVaultError):
    """Raised when a note is not found in the database."""

    def __init__(self, identifier: str, by_field: str = "id") -> None:
        self.identifier = identifier
        self.by_field = by_field
        super().__init__(f"Note not found with {by_field}: {identifier}")


class DuplicatePathError(DatabaseVaultError):
    """Raised when attempting to create a note with a path that already exists."""

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"Note already exists at path: {path}")


class UnauthorizedError(DatabaseVaultError):
    """Raised when a user attempts to access a note they don't own."""

    def __init__(self, note_id: str, user_id: str) -> None:
        self.note_id = note_id
        self.user_id = user_id
        super().__init__(f"User {user_id} is not authorized to access note {note_id}")
