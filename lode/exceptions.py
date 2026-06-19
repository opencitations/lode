from datetime import datetime, timezone
import uuid

class LODEError(Exception):
    """Base exception. All LODE errors inherit this exception"""

    def __init__(self, message: str, context: dict = None):
        super().__init__(message)
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.request_id = str(uuid.uuid4())

class ArtefactLoadError(LODEError):
    """Artefatto raggiunto ma non parsabile in nessun formato RDF."""
    pass

class ArtefactNotFoundError(LODEError):
    "Artefatto risponde 404"
    pass

class UploadValidationError(LODEError):
    """The uploaded file failed the security checks (binary, disallowed format,
    potentially malicious XML content, etc.).

    `http_status` is the suggested HTTP status for the response (default 400).
    """
    http_status = 400

class UploadTooLargeError(UploadValidationError):
    """The uploaded file exceeds the maximum allowed size."""
    http_status = 413

class UnsupportedMediaError(UploadValidationError):
    """File extension / type not in the allowlist."""
    http_status = 415

class UnsafeURLError(LODEError):
    """URL blocked by the anti-SSRF protection (internal/private host,
    disallowed scheme, too many redirects)."""
    http_status = 400