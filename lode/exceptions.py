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
    """Artefatto risponde 404 o errore di rete."""
    pass

class ArtefactUnavailableError(LODEError):
    """Host remoto raggiunto ma in errore server (5xx): l'artefatto puo' esistere,
    e' il servizio a essere temporaneamente non disponibile."""
    pass

class ArtefactValidationError(LODEError):
    """Artefatto rifiutato dai security check (size, estensione, scheme/SSRF, non testo)."""
    pass