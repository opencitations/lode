# tests/test_packaging.py
import importlib
import importlib.resources as ir
import os
import subprocess
import sys
from pathlib import Path

import pytest


# --- 1. le risorse dati sono nel package (prende il bug di packaging) ---
def test_package_data_present():
    files = ir.files("lode")
    assert (files / "templates" / "viewer.html").is_file()
    assert (files / "static" / "style.css").is_file()
    assert (files / "reader" / "config" / "owl.yaml").is_file()
    assert (files / "warnings.json").is_file()


# --- 2. i template si risolvono a prescindere dalla cwd (prende il path cwd-relative) ---
def test_templates_resolved_regardless_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)          # cwd != root repo
    import lode.api as api
    importlib.reload(api)
    tdir = Path(api.templates.env.loader.searchpath[0])
    assert tdir.is_dir()
    assert (tdir / "viewer.html").is_file()
    # deve stare DENTRO il package, non relativo alla cwd
    assert Path("lode/templates").resolve() != tdir or tdir.is_absolute()


# --- 3. SPOOL/BUILD rispettano le env var (prende Blocker 1 / Docker) ---
def test_spool_and_build_env_override(tmp_path, monkeypatch):
    sp, bd = tmp_path / "sp", tmp_path / "bd"
    monkeypatch.setenv("LODE_SPOOL_DIR", str(sp))
    monkeypatch.setenv("LODE_BUILD_DIR", str(bd))
    import lode.helpers.spool as spool_mod
    import lode.api as api
    importlib.reload(spool_mod)
    importlib.reload(api)
    # spool vive ora in helpers/spool.py
    assert spool_mod.SPOOL_DIR == os.path.realpath(str(sp))
    # build dir resta in api.py
    assert api.BUILD_DIR == os.path.realpath(str(bd))

# --- 4. di default NON scrivono dentro il package (fs read-only in Docker) ---
def test_writable_dirs_outside_package(monkeypatch):
    monkeypatch.delenv("LODE_SPOOL_DIR", raising=False)
    monkeypatch.delenv("LODE_BUILD_DIR", raising=False)
    import lode
    import lode.helpers.spool as spool_mod
    import lode.api as api
    importlib.reload(spool_mod)
    importlib.reload(api)
    pkg = Path(lode.__file__).resolve().parent
    for d in (spool_mod.SPOOL_DIR, api.BUILD_DIR):
        assert pkg not in Path(d).resolve().parents, f"{d} sta dentro il package"


# --- 5. l'entrypoint CLI esiste e funziona (prende project.scripts rotto) ---
def test_cli_entrypoint():
    r = subprocess.run([sys.executable, "-m", "lode.cli", "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "serve" in r.stdout and "build" in r.stdout


# --- 6. /health risponde (readiness probe usata da Docker/K8s) ---
def test_health_endpoint():
    from fastapi.testclient import TestClient
    from lode.api import app
    r = TestClient(app).get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"