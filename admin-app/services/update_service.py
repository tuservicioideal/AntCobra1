"""
Desktop app update checker / downloader.

Reads the public Hosting manifest at UPDATE_MANIFEST_URL and downloads
the published ZIP when a newer version is available.

When running as a frozen EXE, apply_update_inplace replaces the running
binary (via a helper .bat) instead of launching a second copy from Downloads.

Staging builds (Downloads\\RecaudoLegal\\updates or Cobranzas-Setup-*.exe)
migrate to the canonical LocalAppData install and refresh the desktop shortcut.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Callable

import requests

from config import APP_VERSION, UPDATE_MANIFEST_URL


ProgressCb = Callable[[str, float], None]

SHORTCUT_NAME = "Recaudo Legal"


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


@dataclass
class ApplyResult:
    success: bool
    message: str
    target_exe: str = ""
    used_fallback: bool = False
    will_relaunch: bool = False
    shortcut_path: str = ""


@dataclass
class CanonicalInstallResult:
    migrated: bool
    message: str
    target_exe: str = ""
    will_relaunch: bool = False
    shortcut_path: str = ""


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in (version or "0").strip().lstrip("vV").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) if parts else (0,)


def current_version() -> str:
    return APP_VERSION


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


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


def _local_install_dir() -> str:
    local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(local, "AntCobranzas")
    os.makedirs(path, exist_ok=True)
    return path


def canonical_exe_path() -> str:
    """Stable install path used after leaving Downloads staging."""
    return os.path.join(_local_install_dir(), "AntCobranzas.exe")


def is_staging_exe(path: str | None = None) -> bool:
    """
    True when the EXE lives in the update download folder or is a Setup rename.

    Those copies must not become the long-term install target (old shortcuts
    would keep pointing at an outdated Desktop/USB binary).
    """
    raw = path if path is not None else (sys.executable if is_frozen() else "")
    if not raw:
        return False
    abspath = os.path.abspath(raw)
    name = os.path.basename(abspath).lower()
    if name.startswith("cobranzas-setup-") and name.endswith(".exe"):
        return True
    norm = abspath.replace("/", "\\").lower()
    return "\\recaudolegal\\updates\\" in norm or norm.rstrip("\\").endswith(
        "\\recaudolegal\\updates"
    )


def _is_writable_dir(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, delete=True):
            pass
        return True
    except Exception:
        return False


def resolve_install_target() -> tuple[str, bool]:
    """
    Return (target_exe_path, used_canonical_or_fallback).

    Staging EXEs always install to the canonical LocalAppData path.
    Otherwise prefer replacing the currently running frozen EXE when writable.
    """
    if is_frozen():
        current = os.path.abspath(sys.executable)
        if is_staging_exe(current):
            return canonical_exe_path(), True
        exe_dir = os.path.dirname(current)
        if _is_writable_dir(exe_dir):
            return current, False
        return canonical_exe_path(), True

    # Dev / non-frozen: stage under LocalAppData so the flow stays testable.
    return canonical_exe_path(), True


def _desktop_dir() -> str:
    home = os.path.expanduser("~")
    userprofile = os.environ.get("USERPROFILE") or home
    candidates = [
        os.path.join(userprofile, "Desktop"),
        os.path.join(home, "Desktop"),
        os.path.join(userprofile, "OneDrive", "Desktop"),
    ]
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    return candidates[0]


def create_or_update_desktop_shortcut(
    target_exe: str,
    name: str = SHORTCUT_NAME,
) -> str:
    """
    Create or refresh a Desktop .lnk pointing at ``target_exe``.

    Uses WScript.Shell via PowerShell (no extra Python deps). Returns the .lnk path.
    """
    if not target_exe:
        return ""
    target_exe = os.path.abspath(target_exe)
    desktop = _desktop_dir()
    os.makedirs(desktop, exist_ok=True)
    lnk_path = os.path.join(desktop, f"{name}.lnk")
    work_dir = os.path.dirname(target_exe)

    def _ps_escape(value: str) -> str:
        return value.replace("'", "''")

    ps = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{_ps_escape(lnk_path)}'); "
        f"$s.TargetPath = '{_ps_escape(target_exe)}'; "
        f"$s.WorkingDirectory = '{_ps_escape(work_dir)}'; "
        "$s.Description = 'Recaudo Legal — AntCobranzas'; "
        f"$s.IconLocation = '{_ps_escape(target_exe)},0'; "
        "$s.Save()"
    )
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps,
            ],
            check=False,
            capture_output=True,
            timeout=45,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return ""
    return lnk_path if os.path.isfile(lnk_path) else lnk_path


def ensure_canonical_install() -> CanonicalInstallResult:
    """
    If the frozen EXE is a staging/Setup copy, install it to LocalAppData,
    refresh the desktop shortcut, relaunch, and signal the UI to quit.
    """
    if not is_frozen():
        return CanonicalInstallResult(migrated=False, message="")

    current = os.path.abspath(sys.executable)
    if not is_staging_exe(current):
        return CanonicalInstallResult(migrated=False, message="")

    target = canonical_exe_path()
    if os.path.abspath(current) == os.path.abspath(target):
        shortcut = create_or_update_desktop_shortcut(target)
        return CanonicalInstallResult(
            migrated=False,
            message="",
            target_exe=target,
            shortcut_path=shortcut,
        )

    target_dir = os.path.dirname(target)
    if not _is_writable_dir(target_dir):
        return CanonicalInstallResult(
            migrated=False,
            message=(
                f"No hay permiso de escritura en:\n{target_dir}\n\n"
                "Copie el EXE manualmente a esa carpeta o ejecute como usuario "
                "con permisos."
            ),
            target_exe=target,
        )

    try:
        if os.path.exists(target):
            try:
                os.replace(target, target + ".old")
            except OSError:
                pass
        shutil.copy2(current, target)
        shortcut = create_or_update_desktop_shortcut(target)
        try:
            os.startfile(target)  # type: ignore[attr-defined]
        except Exception as e:
            return CanonicalInstallResult(
                migrated=True,
                message=(
                    f"Se instaló en:\n{target}\n\n"
                    f"No se pudo reabrir automáticamente: {e}\n"
                    "Ábrala desde el acceso directo del Escritorio."
                ),
                target_exe=target,
                will_relaunch=False,
                shortcut_path=shortcut,
            )
        msg = (
            f"La app se instaló en una ubicación estable:\n{target}\n\n"
            "Se creó/actualizó el acceso directo «Recaudo Legal» en el Escritorio.\n"
            "Use ese acceso directo de ahora en adelante."
        )
        return CanonicalInstallResult(
            migrated=True,
            message=msg,
            target_exe=target,
            will_relaunch=True,
            shortcut_path=shortcut,
        )
    except Exception as e:
        # Fallback: schedule bat replace after this process exits.
        applied = apply_update_inplace(current, relaunch=True, refresh_shortcut=True)
        if applied.success:
            return CanonicalInstallResult(
                migrated=True,
                message=applied.message or str(e),
                target_exe=applied.target_exe,
                will_relaunch=applied.will_relaunch,
                shortcut_path=applied.shortcut_path,
            )
        return CanonicalInstallResult(
            migrated=False,
            message=f"No se pudo migrar la instalación:\n{e}",
            target_exe=target,
        )


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
    """Download ZIP, verify sha256 when present, extract update EXE."""
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
                    message="El paquete no contiene un ejecutable .exe.",
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
            message=f"No se pudo extraer el ejecutable: {e}",
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
    """Legacy: open the downloaded EXE in place (avoid for frozen installs)."""
    if exe_path and os.path.isfile(exe_path):
        os.startfile(exe_path)  # type: ignore[attr-defined]


def _write_replace_bat(
    *,
    source_exe: str,
    target_exe: str,
    pid: int,
    relaunch: bool,
) -> str:
    """
    Write a helper .bat that waits for this process to exit, replaces the EXE,
    optionally relaunches, then deletes itself.
    """
    bat_dir = os.path.dirname(target_exe) or tempfile.gettempdir()
    os.makedirs(bat_dir, exist_ok=True)
    bat_path = os.path.join(bat_dir, "_antcobranzas_update.bat")

    # Escape for cmd: paths with spaces must be quoted; percent doubled.
    src = source_exe.replace("%", "%%")
    dst = target_exe.replace("%", "%%")
    old = (target_exe + ".old").replace("%", "%%")
    bat_self = bat_path.replace("%", "%%")

    relaunch_line = f'start "" "{dst}"' if relaunch else "rem no relaunch"

    content = f"""@echo off
setlocal
set PID={pid}
:wait
tasklist /FI "PID eq %PID%" 2>NUL | find "%PID%" >NUL
if not errorlevel 1 (
  timeout /t 1 /nobreak >NUL
  goto wait
)
if exist "{old}" del /f /q "{old}" >NUL 2>&1
if exist "{dst}" move /y "{dst}" "{old}" >NUL 2>&1
copy /y "{src}" "{dst}" >NUL
if errorlevel 1 (
  echo ERROR: no se pudo copiar la actualizacion.
  pause
  exit /b 1
)
del /f /q "{old}" >NUL 2>&1
{relaunch_line}
del /f /q "{bat_self}" >NUL 2>&1
"""
    with open(bat_path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(content)
    return bat_path


def apply_update_inplace(
    source_exe: str,
    *,
    relaunch: bool = True,
    refresh_shortcut: bool = True,
) -> ApplyResult:
    """
    Replace the installed EXE with ``source_exe`` and optionally relaunch.

    When frozen, schedules a .bat that runs after this process exits (Windows
    locks the running executable). Caller should quit the app after success.
    """
    if not source_exe or not os.path.isfile(source_exe):
        return ApplyResult(success=False, message="No se encontró el ejecutable descargado.")

    target_exe, used_fallback = resolve_install_target()
    target_dir = os.path.dirname(target_exe)
    if not _is_writable_dir(target_dir):
        return ApplyResult(
            success=False,
            message=(
                f"No hay permiso de escritura en:\n{target_dir}\n\n"
                "Abra la carpeta de descarga y copie el EXE manualmente."
            ),
            target_exe=target_exe,
            used_fallback=used_fallback,
        )

    shortcut_path = ""

    # Same path: nothing to replace (already running the downloaded file).
    if os.path.abspath(source_exe) == os.path.abspath(target_exe):
        if refresh_shortcut:
            shortcut_path = create_or_update_desktop_shortcut(target_exe)
        return ApplyResult(
            success=True,
            message="La actualización ya está en la ubicación de instalación.",
            target_exe=target_exe,
            used_fallback=used_fallback,
            will_relaunch=False,
            shortcut_path=shortcut_path,
        )

    if is_frozen():
        try:
            bat_path = _write_replace_bat(
                source_exe=os.path.abspath(source_exe),
                target_exe=os.path.abspath(target_exe),
                pid=os.getpid(),
                relaunch=relaunch,
            )
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP so bat outlives us.
            creationflags = 0x00000008 | 0x00000200
            subprocess.Popen(
                ["cmd.exe", "/c", bat_path],
                close_fds=True,
                creationflags=creationflags,
                cwd=target_dir,
            )
        except Exception as e:
            return ApplyResult(
                success=False,
                message=f"No se pudo programar el reemplazo:\n{e}",
                target_exe=target_exe,
                used_fallback=used_fallback,
            )

        if refresh_shortcut:
            shortcut_path = create_or_update_desktop_shortcut(target_exe)

        msg = (
            f"Se reemplazará la aplicación en:\n{target_exe}\n\n"
            "La app se cerrará y se abrirá de nuevo con la versión nueva."
        )
        if used_fallback:
            msg += (
                "\n\nSe actualizó el acceso directo «Recaudo Legal» en el Escritorio "
                "(LocalAppData\\AntCobranzas). Use ese acceso directo de ahora en adelante."
            )
        return ApplyResult(
            success=True,
            message=msg,
            target_exe=target_exe,
            used_fallback=used_fallback,
            will_relaunch=relaunch,
            shortcut_path=shortcut_path,
        )

    # Non-frozen: copy immediately (no running EXE lock on target).
    try:
        if os.path.exists(target_exe):
            try:
                os.replace(target_exe, target_exe + ".old")
            except OSError:
                pass

        shutil.copy2(source_exe, target_exe)
        if refresh_shortcut:
            shortcut_path = create_or_update_desktop_shortcut(target_exe)
        if relaunch and os.path.isfile(target_exe):
            os.startfile(target_exe)  # type: ignore[attr-defined]
    except Exception as e:
        return ApplyResult(
            success=False,
            message=f"No se pudo copiar la actualización:\n{e}",
            target_exe=target_exe,
            used_fallback=used_fallback,
        )

    return ApplyResult(
        success=True,
        message=f"Actualización aplicada en:\n{target_exe}",
        target_exe=target_exe,
        used_fallback=used_fallback,
        will_relaunch=relaunch,
        shortcut_path=shortcut_path,
    )
