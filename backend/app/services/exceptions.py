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
