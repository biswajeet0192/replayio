"""Exception hierarchy for ReplayKit."""


class ReplayKitError(Exception):
    """Base class for all ReplayKit errors."""


class SessionNotFoundError(ReplayKitError):
    """Raised when a session id cannot be found in the configured storage."""


class RecorderStateError(ReplayKitError):
    """Raised when the recorder is used in an invalid state (e.g. double start)."""


class StorageError(ReplayKitError):
    """Raised when a storage backend operation fails."""
