# lode/helpers/spool.py
"""Disk cache (spool) for uploaded files and fetched URLs.

Lifecycle:
- Entries expire after TTL seconds (default 4 h).
- Total size is capped at MAX_BYTES (default 1 GB).
- Location is controlled by LODE_SPOOL_DIR; defaults to the system
  temp directory so it works out of the box after pip install without
  needing write access to the package directory.

No dependency on FastAPI or any HTTP layer.
"""
import os
import tempfile
import time
from uuid import uuid4

from lode.exceptions import ArtefactValidationError

SPOOL_DIR: str = os.path.realpath(
    os.getenv("LODE_SPOOL_DIR", os.path.join(tempfile.gettempdir(), "lode-spool"))
)
os.makedirs(SPOOL_DIR, exist_ok=True)

TTL       = 4 * 60 * 60   # seconds before an entry is considered stale
MAX_BYTES = 1024 ** 3      # 1 GB total budget


def get_path(token: str) -> str:
    """Return the absolute spool path for a token.

    Validates that the resolved path stays inside SPOOL_DIR to prevent
    path-injection via a crafted token.
    """
    p = os.path.realpath(os.path.join(SPOOL_DIR, f"{token}.rdf"))
    if os.path.commonpath((SPOOL_DIR, p)) != SPOOL_DIR:
        raise ArtefactValidationError(
            "Invalid upload token", context={"token": token}
        )
    return p


def prune() -> None:
    """Evict expired entries, then enforce the size budget.

    Deletes the oldest entries (by mtime) until total size is back
    under MAX_BYTES. Best-effort: OSError races are silently ignored.
    """
    cutoff = time.time() - TTL
    survivors: list[tuple[float, int, str]] = []

    for name in os.listdir(SPOOL_DIR):
        p = os.path.join(SPOOL_DIR, name)
        try:
            st = os.stat(p)
        except OSError:
            continue
        if st.st_mtime < cutoff:
            try:
                os.unlink(p)
            except OSError:
                pass
            continue
        survivors.append((st.st_mtime, st.st_size, p))

    total = sum(size for _, size, _ in survivors)
    if total <= MAX_BYTES:
        return

    for _, size, p in sorted(survivors):   # oldest first
        if total <= MAX_BYTES:
            break
        try:
            os.unlink(p)
            total -= size
        except OSError:
            pass


def save(content: bytes) -> str:
    """Persist raw bytes in the spool and return the token."""
    prune()
    token = uuid4().hex
    with open(get_path(token), "wb") as f:
        f.write(content)
    return token