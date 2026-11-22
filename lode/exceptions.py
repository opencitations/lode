"""Domain exceptions of LODE.

Every error the user can cause (bad URL, unreachable or malformed artefact,
rejected upload) is a LODEError subclass, so the web layer can tell it apart
from an unexpected failure and show a clear message instead of a traceback.
"""
from datetime import datetime, timezone
from typing import Optional
import uuid

class LODEError(Exception):
    """Base exception. All LODE errors inherit this exception.

    Carries a `context` dict (which file, which URL, which limit), a UTC
    `timestamp` and a unique `request_id` so a message shown to the user can be
    matched with the server log.
    """

    def __init__(self, message: str, context: Optional[dict] = None):
        """Store the message together with its context, timestamp and request id."""
        super().__init__(message)
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.request_id = str(uuid.uuid4())

class ArtefactLoadError(LODEError):
    """The artefact was reached but cannot be parsed in any RDF format."""
    pass

class ArtefactNotFoundError(LODEError):
    """The artefact answers 404 or the request fails with a network error."""
    pass

class ArtefactUnavailableError(LODEError):
    """The remote host was reached but answers with a server error (5xx).

    The artefact may well exist: it is the service that is temporarily unavailable.
    """
    pass

class BuildCapacityError(LODEError):
    """The service cannot start a static-site build right now (no free slot or no disk quota).

    `retry_after` is the number of seconds the client should wait before retrying.
    """

    def __init__(self, message: str, retry_after: int, context: Optional[dict] = None):
        """Store the message, the suggested wait and the optional context."""
        super().__init__(message, context)
        self.retry_after = retry_after

class ArtefactValidationError(LODEError):
    """The artefact was rejected by a security check (size, extension, URL scheme/SSRF, non-text)."""
    pass