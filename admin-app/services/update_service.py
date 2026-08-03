"""
Desktop app update checker / downloader.

Reads the public Hosting manifest at UPDATE_MANIFEST_URL and downloads
the published ZIP when a newer version is available.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import zipfile
from dataclasses import dataclass
from typing import Callable

import requests

from config import APP_VERSION, UPDATE_MANIFEST_URL


ProgressCb = Callable[[str, float], None]


@dataclass
class UpdateInfo:
    version: str
    filename: str
    url: str
    sha256: str
    notes: str
    published_at: str
    package: str

    @property
    def is_newer(self) -> bool:
        return _version_tuple(self.version) > _version_tuple(APP_VERSION)


@dataclass
class DownloadResult:
    success: bool
    message: str
    zip_path: str = ""
    exe_path: str = ""
    folder: str = ""


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in (version or "0").strip().lstrip("vV").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) if parts else (0,)


def current_version() -> str:
    return APP_VERSION


def fetch_latest(timeout: int = 20) -> UpdateInfo:
    """Fetch and parse landing/updates/latest.json from Hosting."""
    resp = requests.get(UPDATE_MANIFEST_URL, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return UpdateInfo(
        version=str(data.get("version") or "").strip(),
        filename=str(data.get("filename") or "").strip(),
        url=str(data.get("url") or "").strip(),
        sha256=str(data.get("sha256") or "").strip().lower(),
        notes=str(data.get("notes") or "").strip(),
        published_at=str(data.get("published_at") or "").strip(),
        package=str(data.get("package") or "").strip(),
    )


def default_download_dir() -> str:
    home = os.path.expanduser("~")
    downloads = os.path.join(home, "Downloads")
    base = downloads if os.path.isdir(downloads) else home
    target = os.path.join(base, "RecaudoLegal", "updates")
    os.makedirs(target, exist_ok=True)
    return target


def _sha256_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def download_update(
    info: UpdateInfo,
    dest_dir: str | None = None,
    progress: ProgressCb | None = None,
) -> DownloadResult:
    """Download ZIP, verify sha256 when present, extract installer EXE."""
    if not info.url:
        return DownloadResult(success=False, message="El manifiesto no incluye URL de descarga.")

    folder = dest_dir or default_download_dir()
    os.makedirs(folder, exist_ok=True)
    zip_name = info.package or os.path.basename(info.url) or f"Cobranzas-Setup-{info.version}.zip"
    zip_path = os.path.join(folder, zip_name)

    if progress:
        progress("Descargando actualización…", 0.05)

    try:
        with requests.get(info.url, stream=True, timeout=120) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            with open(zip_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    fh.write(chunk)
                    done += len(chunk)
                    if progress and total > 0:
                        progress(
                            f"Descargando… {done // (1024 * 1024)} / {total // (1024 * 1024)} MB",
                            min(0.85, done / total),
                        )
    except requests.exceptions.ConnectionError:
        return DownloadResult(success=False, message="Sin conexión a Internet.")
    except requests.exceptions.Timeout:
        return DownloadResult(success=False, message="Tiempo de espera agotado al descargar.")
    except Exception as e:
        return DownloadResult(success=False, message=f"Error al descargar: {e}")

    if progress:
        progress("Verificando archivo…", 0.9)

    if info.sha256:
        digest = _sha256_file(zip_path)
        if digest.lower() != info.sha256.lower():
            try:
                os.remove(zip_path)
            except OSError:
                pass
            return DownloadResult(
                success=False,
                message="El archivo descargado no coincide con el hash esperado (corrupto).",
            )

    exe_path = ""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".exe") and not n.endswith("/")]
            if not names:
                return DownloadResult(
                    success=False,
                    message="El paquete no contiene un instalador .exe.",
                    zip_path=zip_path,
                    folder=folder,
                )
            # Prefer the declared filename when present
            preferred = info.filename
            member = next((n for n in names if os.path.basename(n) == preferred), names[0])
            zf.extract(member, folder)
            exe_path = os.path.join(folder, member)
            # Flatten nested paths if any
            if os.path.dirname(member):
                flat = os.path.join(folder, os.path.basename(member))
                if os.path.abspath(exe_path) != os.path.abspath(flat):
                    if os.path.exists(flat):
                        os.remove(flat)
                    os.replace(exe_path, flat)
                    exe_path = flat
    except zipfile.BadZipFile:
        return DownloadResult(
            success=False,
            message="El archivo descargado no es un ZIP válido.",
            zip_path=zip_path,
            folder=folder,
        )
    except Exception as e:
        return DownloadResult(
            success=False,
            message=f"No se pudo extraer el instalador: {e}",
            zip_path=zip_path,
            folder=folder,
        )

    if progress:
        progress("Listo", 1.0)

    return DownloadResult(
        success=True,
        message=f"Actualización {info.version} descargada.",
        zip_path=zip_path,
        exe_path=exe_path,
        folder=folder,
    )


def open_folder(path: str) -> None:
    if not path:
        return
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    if folder and os.path.isdir(folder):
        subprocess.Popen(["explorer", folder], shell=False)


def launch_installer(exe_path: str) -> None:
    if exe_path and os.path.isfile(exe_path):
        os.startfile(exe_path)  # type: ignore[attr-defined]
