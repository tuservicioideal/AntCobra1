"""Unit tests for desktop update apply helpers and DB path resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest


def test_resolve_install_target_frozen_writable(tmp_path, monkeypatch):
    from services import update_service

    exe = tmp_path / "AntCobranzas.exe"
    exe.write_bytes(b"old")
    monkeypatch.setattr(update_service, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", str(exe))

    target, fallback = update_service.resolve_install_target()
    assert Path(target) == exe.resolve()
    assert fallback is False


def test_resolve_install_target_falls_back_when_not_writable(tmp_path, monkeypatch):
    from services import update_service

    exe = tmp_path / "locked" / "AntCobranzas.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"old")
    local = tmp_path / "LocalAppData"
    local.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setattr(update_service, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(update_service, "_is_writable_dir", lambda _p: False)

    target, fallback = update_service.resolve_install_target()
    assert fallback is True
    assert target == str(local / "AntCobranzas" / "AntCobranzas.exe")


def test_apply_update_inplace_non_frozen_copies(tmp_path, monkeypatch):
    from services import update_service

    source = tmp_path / "new.exe"
    source.write_bytes(b"NEWVERSION")
    install_dir = tmp_path / "LocalAppData" / "AntCobranzas"
    install_dir.mkdir(parents=True)
    target = install_dir / "AntCobranzas.exe"
    target.write_bytes(b"OLD")

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.setattr(update_service, "is_frozen", lambda: False)
    # Avoid launching the fake exe via startfile
    monkeypatch.setattr(os, "startfile", lambda *_a, **_k: None, raising=False)

    result = update_service.apply_update_inplace(str(source), relaunch=False)
    assert result.success
    assert Path(result.target_exe).read_bytes() == b"NEWVERSION"


def test_user_db_path_preferred_when_frozen(tmp_path, monkeypatch):
    from services import database as db

    appdata = tmp_path / "Roaming"
    appdata.mkdir()
    exe_dir = tmp_path / "install"
    exe_dir.mkdir()
    (exe_dir / db.DB_FILENAME).write_bytes(b"portable")

    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.delenv("ANTCOBRANZAS_DB_PATH", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "AntCobranzas.exe"))

    resolved = db._resolve_default_db_path()
    assert resolved == str(appdata / "AntCobranzas" / "data" / db.DB_FILENAME)

    db._migrate_legacy_db_if_needed(resolved)
    assert Path(resolved).exists()
    assert Path(resolved).read_bytes() == b"portable"
