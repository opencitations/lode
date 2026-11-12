"""ZIP build of a static site: workspace, disk quota and concurrency limit.

Builds write hundreds of files each, so they get their own directory with an
explicit budget instead of filling up /tmp. Nothing here knows about HTTP: when
the service is at capacity it raises BuildCapacityError and the caller decides
how to tell the client.
"""
import os
import re
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import lode.core as core
from lode.exceptions import BuildCapacityError

# ==========================================================================
# 1. BUILD WORKSPACE
# ==========================================================================
BUILD_DIR = os.path.realpath(
    os.getenv("LODE_BUILD_DIR", os.path.join(tempfile.gettempdir(), "lode-builds"))
)
os.makedirs(BUILD_DIR, exist_ok=True)
_BUILD_TTL = 30 * 60                          # orphans (aborted downloads) age out
_BUILD_MAX_BYTES = 2 * 1024 ** 3              # 2 GB for all pending builds
_BUILD_SLOTS = threading.BoundedSemaphore(2)  # concurrent builds, per worker process
_BUILD_WAIT = 5                               # seconds a request waits for a slot


def _prune_builds() -> int:
    """Drop orphaned build directories and return the bytes still in use.

    A build is orphaned when the caller never removed it, i.e. the client
    opened the connection and never finished reading the archive.
    """
    cutoff = time.time() - _BUILD_TTL
    total = 0
    for name in os.listdir(BUILD_DIR):
        p = os.path.join(BUILD_DIR, name)
        try:
            st = os.stat(p)
        except OSError:
            continue
        if st.st_mtime < cutoff:
            shutil.rmtree(p, ignore_errors=True)
            continue
        for root, _, files in os.walk(p):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    return total


# ==========================================================================
# 2. SLUG
# ==========================================================================
def slugify(name: Optional[str]) -> str:
    """Safe directory/file stem derived from a URL or filename.

    Must never yield '.' or '..': those would let make_archive(base_dir=...)
    escape the build directory and archive its parent.
    """
    if not name:
        return "ontology"
    raw = name.rstrip("/").split("#")[0].split("/")[-1]
    raw = re.sub(r"\.(ttl|rdf|owl|n3|nt|jsonld|xml)$", "", raw, flags=re.I)
    raw = re.sub(r"[^A-Za-z0-9._-]", "-", raw).strip("-.")
    if not raw or raw in {".", ".."}:
        return "ontology"
    return raw[:64]


# ==========================================================================
# 3. BUILD
# ==========================================================================
def build_zip(artefact, slug: str, lang: Optional[str] = None) -> Tuple[str, str]:
    """Render the whole static site of an artefact and return (zip_path, workdir).

    The caller owns `workdir` and must delete it once the archive has been sent;
    orphans are pruned by age. Raises BuildCapacityError when no build slot frees
    up in time or the workspace quota is used up. Blocking and disk-heavy: keep
    it off the event loop.
    """
    if not _BUILD_SLOTS.acquire(timeout=_BUILD_WAIT):
        raise BuildCapacityError("Server busy: too many concurrent builds", retry_after=30)
    workdir = None
    try:
        if _prune_builds() > _BUILD_MAX_BYTES:
            raise BuildCapacityError("Build storage full, retry shortly", retry_after=60)

        workdir = tempfile.mkdtemp(prefix="build_", dir=BUILD_DIR)
        site_dir = Path(workdir) / slug
        site_dir.mkdir(parents=True, exist_ok=True)

        core.build_site(artefact, site_dir, lang=lang or "en")

        zip_path = shutil.make_archive(
            os.path.join(workdir, f"{slug}-lode"), "zip",
            root_dir=workdir, base_dir=slug,
        )
        # The loose pages are redundant once archived: halve the disk peak.
        shutil.rmtree(site_dir, ignore_errors=True)
    except BaseException:
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        raise
    finally:
        # Free the slot as soon as the build ends, not when the client is done
        # downloading: a slow reader must not hold a build slot hostage.
        _BUILD_SLOTS.release()
    return zip_path, workdir
