"""Cloud Functions Python: parse y publicación de cartera desde la web."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore, initialize_app, storage
from firebase_functions import https_fn, options
from google.cloud.firestore import SERVER_TIMESTAMP

from cartera.authz import CarteraAuthError, assert_can_manage_cartera
from cartera.config import CAMPAIGN_ID_DEFAULT, MAX_EXCEL_BYTES
from cartera.diff_engine import compare_cartera
from cartera.excel_parser import ExcelParseError
from cartera.firestore_store import FirestoreStore
from cartera.notifications import build_notifications
from cartera.job_paths import is_owned_storage_path
from cartera.parsed_blob import dumps_parsed, loads_parsed
from cartera.pipeline import parse_to_preview
from cartera.publisher import plan_and_apply, read_current_cartera
from cartera.publisher_lock import lock_is_busy
from cartera.visit_merge import reindex_cartera_for_diff

initialize_app()

_REGION = "us-central1"


def _https_error(code: str, message: str) -> https_fn.HttpsError:
    mapping = {
        "unauthenticated": https_fn.FunctionsErrorCode.UNAUTHENTICATED,
        "permission-denied": https_fn.FunctionsErrorCode.PERMISSION_DENIED,
        "invalid-argument": https_fn.FunctionsErrorCode.INVALID_ARGUMENT,
        "not-found": https_fn.FunctionsErrorCode.NOT_FOUND,
        "failed-precondition": https_fn.FunctionsErrorCode.FAILED_PRECONDITION,
        "aborted": https_fn.FunctionsErrorCode.ABORTED,
    }
    return https_fn.HttpsError(
        code=mapping.get(code, https_fn.FunctionsErrorCode.INTERNAL),
        message=message,
    )


def _caller_uid(req: https_fn.CallableRequest) -> str:
    if not req.auth:
        raise _https_error("unauthenticated", "Debes iniciar sesión.")
    return req.auth.uid


def _load_user(db, uid: str) -> dict[str, Any] | None:
    snap = db.collection("usuarios").document(uid).get()
    return snap.to_dict() if snap.exists else None


def _assert_admin(req: https_fn.CallableRequest) -> tuple[Any, str]:
    uid = _caller_uid(req)
    db = firestore.client()
    try:
        assert_can_manage_cartera({"uid": uid}, _load_user(db, uid))
    except CarteraAuthError as exc:
        raise _https_error(exc.code, exc.message) from exc
    return db, uid


def _job_ref(db, job_id: str):
    return db.collection("trabajos_cartera").document(job_id)


def _require_job(db, job_id: str, uid: str) -> dict[str, Any]:
    if not job_id:
        raise _https_error("invalid-argument", "Falta jobId.")
    snap = _job_ref(db, job_id).get()
    if not snap.exists:
        raise _https_error("not-found", "No existe el trabajo de carga.")
    data = snap.to_dict() or {}
    if data.get("creado_por_uid") != uid:
        raise _https_error("permission-denied", "Este trabajo no te pertenece.")
    return data


def _load_usuarios(db) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for snap in db.collection("usuarios").stream():
        row = snap.to_dict() or {}
        row["uid"] = snap.id
        out.append(row)
    return out


def _write_notifications(db, payload: dict[str, Any], admin_uids: list[str]) -> int:
    count = 0
    col = db.collection("notificaciones")
    for notif in payload.get("gestor") or []:
        col.add({**notif, "fecha": SERVER_TIMESTAMP})
        count += 1
    admin_body = payload.get("admin")
    if admin_body:
        for admin_uid in admin_uids:
            col.add(
                {
                    **admin_body,
                    "destinatario_uid": admin_uid,
                    "fecha": SERVER_TIMESTAMP,
                }
            )
            count += 1
    alerts = db.collection("alertas")
    for alert in payload.get("alertas") or []:
        alerts.add({**alert, "fecha": SERVER_TIMESTAMP, "revisada": False})
    return count


def _admin_uids(usuarios: list[dict[str, Any]]) -> list[str]:
    return [
        str(u.get("uid"))
        for u in usuarios
        if u.get("activo") is not False and u.get("rol") in ("admin", "supervisor")
    ]


@https_fn.on_call(
    region=_REGION,
    timeout_sec=540,
    memory=options.MemoryOption.GB_2,
)
def parseCarteraExcel(req: https_fn.CallableRequest) -> dict[str, Any]:
    db, uid = _assert_admin(req)
    data = req.data or {}
    job_id = str(data.get("jobId") or "").strip()
    job = _require_job(db, job_id, uid)
    job_ref = _job_ref(db, job_id)

    storage_path = str((job.get("archivo") or {}).get("storage_path") or "")
    if not is_owned_storage_path(storage_path, uid, job_id):
        raise _https_error("permission-denied", "Ruta de archivo inválida.")

    job_ref.set(
        {
            "estado": "parseando",
            "progreso": {
                "paso": "parseando",
                "current": 0,
                "total": 1,
                "mensaje": "Leyendo Excel…",
            },
            "error": firestore.DELETE_FIELD,
        },
        merge=True,
    )

    try:
        bucket = storage.bucket()
        blob = bucket.blob(storage_path)
        excel_bytes = blob.download_as_bytes()
        if len(excel_bytes) > MAX_EXCEL_BYTES:
            raise ExcelParseError("El archivo supera 50 MB.")

        fs_store = FirestoreStore(db)
        old_raw = read_current_cartera(fs_store, job.get("campaign_id") or CAMPAIGN_ID_DEFAULT)
        usuarios = _load_usuarios(db)
        archivo_nombre = str((job.get("archivo") or {}).get("nombre") or "")
        parse_result, _report, preview, modo = parse_to_preview(
            excel_bytes,
            old_raw_cartera=old_raw,
            usuarios=usuarios,
            archivo_nombre=archivo_nombre,
        )

        parsed_path = "/".join(storage_path.split("/")[:-1] + ["parsed.json.gz"])
        bucket.blob(parsed_path).upload_from_string(
            dumps_parsed(parse_result),
            content_type="application/gzip",
        )

        archivo = dict(job.get("archivo") or {})
        archivo["parsed_path"] = parsed_path
        job_ref.set(
            {
                "estado": "preview",
                "modo": modo,
                "archivo": archivo,
                "resumen": preview.get("resumen"),
                "diff": preview.get("diff"),
                "secciones": preview.get("secciones"),
                "secciones_sin_gestor": preview.get("secciones_sin_gestor"),
                "conflictos_seccion": preview.get("conflictos_seccion"),
                "muestras": preview.get("muestras"),
                "progreso": {
                    "paso": "preview",
                    "current": 1,
                    "total": 1,
                    "mensaje": "Listo para confirmar",
                },
            },
            merge=True,
        )
        return {"jobId": job_id, "estado": "preview", "modo": modo, "diff": preview.get("diff")}
    except ExcelParseError as exc:
        job_ref.set(
            {
                "estado": "error",
                "error": {"code": "excel_invalido", "message": str(exc)},
            },
            merge=True,
        )
        raise _https_error("invalid-argument", str(exc)) from exc
    except https_fn.HttpsError:
        raise
    except Exception as exc:  # noqa: BLE001
        job_ref.set(
            {
                "estado": "error",
                "error": {"code": "interno", "message": "No se pudo parsear el Excel."},
            },
            merge=True,
        )
        raise _https_error("internal", "No se pudo parsear el Excel.") from exc


@https_fn.on_call(
    region=_REGION,
    timeout_sec=1800,
    memory=options.MemoryOption.GB_1,
)
def publishCarteraExcel(req: https_fn.CallableRequest) -> dict[str, Any]:
    db, uid = _assert_admin(req)
    data = req.data or {}
    job_id = str(data.get("jobId") or "").strip()
    if data.get("confirmar") is not True:
        raise _https_error("failed-precondition", "Debes confirmar la publicación.")
    job = _require_job(db, job_id, uid)
    estado = str(job.get("estado") or "")
    parsed_path = str((job.get("archivo") or {}).get("parsed_path") or "")
    if estado == "error" and parsed_path:
        pass
    elif estado != "preview":
        raise _https_error(
            "failed-precondition",
            f"El trabajo no está en preview (estado={job.get('estado')}).",
        )
    if parsed_path and not is_owned_storage_path(parsed_path, uid, job_id):
        raise _https_error("permission-denied", "Ruta de archivo inválida.")

    lock_ref = db.collection("configuracion").document("cartera_publisher")
    transaction = db.transaction()

    class _PublisherBusy(Exception):
        pass

    @firestore.transactional
    def _claim_lock(transaction):
        snap = lock_ref.get(transaction=transaction)
        lock = snap.to_dict() if snap.exists else {}
        if lock_is_busy(lock, job_id):
            raise _PublisherBusy()
        transaction.set(
            lock_ref,
            {
                "activo": "web",
                "job_id": job_id,
                "estado": "publicando",
                "since": SERVER_TIMESTAMP,
            },
            merge=True,
        )

    try:
        _claim_lock(transaction)
    except _PublisherBusy as exc:
        raise _https_error("aborted", "Hay otra publicación de cartera en curso.") from exc
    job_ref = _job_ref(db, job_id)
    job_ref.set(
        {
            "estado": "publicando",
            "progreso": {
                "paso": "publicando",
                "current": 0,
                "total": 1,
                "mensaje": "Publicando cartera…",
            },
        },
        merge=True,
    )

    try:
        parsed_path = str((job.get("archivo") or {}).get("parsed_path") or "")
        if not parsed_path:
            raise _https_error("failed-precondition", "Falta el JSON parseado.")
        parsed = loads_parsed(storage.bucket().blob(parsed_path).download_as_bytes())
        by_seccion = parsed.get("by_seccion") or {}
        campaign_id = str(job.get("campaign_id") or CAMPAIGN_ID_DEFAULT)
        ultimo_excel = str((job.get("archivo") or {}).get("nombre") or "")

        fs_store = FirestoreStore(db)
        old_raw = read_current_cartera(fs_store, campaign_id)
        report = compare_cartera(reindex_cartera_for_diff(old_raw), by_seccion)

        def on_progress(current: int, total: int, mensaje: str) -> None:
            if current == 1 or current == total or current % 250 == 0:
                job_ref.set(
                    {
                        "progreso": {
                            "paso": "publicando",
                            "current": current,
                            "total": max(total, 1),
                            "mensaje": mensaje,
                        }
                    },
                    merge=True,
                )

        result = plan_and_apply(
            fs_store,
            by_seccion=by_seccion,
            change_report=report,
            campaign_id=campaign_id,
            ultimo_excel=ultimo_excel,
            progress_callback=on_progress,
            existing_cartera=old_raw,
        )
        usuarios = _load_usuarios(db)
        notif_payload = build_notifications(
            change_report=report,
            usuarios=usuarios,
            campaign_id=campaign_id,
        )
        sent = _write_notifications(db, notif_payload, _admin_uids(usuarios))
        job_ref.set(
            {
                "estado": "listo",
                "resultado_publicacion": {
                    **result,
                    "notifications_sent": sent,
                    "secciones_sin_gestor": notif_payload.get("secciones_sin_gestor") or [],
                },
                "progreso": {
                    "paso": "listo",
                    "current": 1,
                    "total": 1,
                    "mensaje": "Cartera publicada",
                },
            },
            merge=True,
        )
        lock_ref.set(
            {
                "activo": "web",
                "job_id": job_id,
                "estado": "listo",
                "since": SERVER_TIMESTAMP,
            },
            merge=True,
        )
        return {
            "jobId": job_id,
            "estado": "listo",
            "resultado": result,
            "notifications_sent": sent,
        }
    except https_fn.HttpsError:
        lock_ref.set({"estado": "error", "job_id": job_id}, merge=True)
        raise
    except Exception as exc:  # noqa: BLE001
        job_ref.set(
            {
                "estado": "error",
                "error": {"code": "interno", "message": "No se pudo publicar la cartera."},
            },
            merge=True,
        )
        lock_ref.set({"estado": "error", "job_id": job_id}, merge=True)
        raise _https_error("internal", "No se pudo publicar la cartera.") from exc
