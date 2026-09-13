#!/usr/bin/env python3
"""Backfill idempotente de bitacora_campo desde doxeo_jobs e historial_contacto.

Uso (desde AntCobra1 o con SA en env):

  set FIREBASE_SERVICE_ACCOUNT_PATH=C:\\ruta\\clase-001-....json
  python scripts/backfill_bitacora_campo.py

  # Solo dry-run:
  python scripts/backfill_bitacora_campo.py --dry-run

  # Limitar docs:
  python scripts/backfill_bitacora_campo.py --limit 500

IDs deterministas (no duplica):
  telegram_{jobId}
  ubicacion_{histId}
  nota_campo_{histId}
  nota_gestion_{visitaId}
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _resolve_sa_path() -> Path:
    raw = (
        os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or ""
    ).strip()
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else (Path.cwd() / p).resolve()
    # Fallback admin-app bundle name (no commitear el JSON).
    candidate = (
        REPO_ROOT
        / "admin-app"
        / "clase-001-firebase-adminsdk-fbsvc-ee190f0bcc.json"
    )
    return candidate


def _fecha_dia_from_iso_or_ts(value: Any) -> str:
    if value is None:
        return datetime.now().strftime("%Y-%m-%d")
    if hasattr(value, "timestamp"):
        try:
            dt = value  # DatetimeWithNanoseconds
            if hasattr(dt, "astimezone"):
                local = dt.astimezone().replace(tzinfo=None)
                return local.strftime("%Y-%m-%d")
        except Exception:
            pass
    text = str(value)
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _client_meta_from_path(db: Any, path: str) -> dict[str, str]:
    """path tipo campañas/{c}/gestores/{s}/clientes/{id}/historial_contacto/{h}."""
    parts = path.split("/")
    out = {
        "campaign_id": "",
        "seccion_key": "",
        "cliente_id": "",
        "cliente_nombre": "",
        "codigo_cliente": "",
        "dni": "",
    }
    try:
        i = parts.index("campañas")
        out["campaign_id"] = parts[i + 1]
        out["seccion_key"] = parts[i + 3]
        out["cliente_id"] = parts[i + 5]
        snap = (
            db.collection("campañas")
            .document(out["campaign_id"])
            .collection("gestores")
            .document(out["seccion_key"])
            .collection("clientes")
            .document(out["cliente_id"])
            .get()
        )
        data = snap.to_dict() or {}
        nombre = (data.get("nombre_completo") or "").strip()
        if not nombre:
            nombre = " ".join(
                x
                for x in [
                    data.get("nombres") or "",
                    data.get("apellido_paterno") or "",
                    data.get("apellido_materno") or "",
                ]
                if str(x).strip()
            ).strip()
        out["cliente_nombre"] = nombre
        out["codigo_cliente"] = str(data.get("codigo_cliente") or out["cliente_id"])
        out["dni"] = str(data.get("numero_documento") or "")
    except Exception:
        pass
    return out


def _set_event(db: Any, event_id: str, doc: dict[str, Any], *, dry_run: bool) -> bool:
    ref = db.collection("bitacora_campo").document(event_id)
    if ref.get().exists:
        return False
    if dry_run:
        return True
    doc = dict(doc)
    doc["backfill"] = True
    ref.set(doc)
    return True


def backfill_telegram(db: Any, *, dry_run: bool, limit: int | None) -> tuple[int, int]:
    written = 0
    skipped = 0
    q = db.collection("doxeo_jobs").limit(limit or 5000)
    for doc in q.stream():
        data = doc.to_dict() or {}
        estado = str(data.get("estado") or "")
        if estado not in {"completado", "timeout", "error"}:
            continue
        event_id = f"telegram_{doc.id}"
        cliente = data.get("cliente") if isinstance(data.get("cliente"), dict) else {}
        solicitante = (
            data.get("solicitante") if isinstance(data.get("solicitante"), dict) else {}
        )
        res = data.get("resultado") if isinstance(data.get("resultado"), dict) else {}
        has_data = bool(res.get("has_data"))
        comando_nombre = str(data.get("comando_nombre") or "Telegram")
        dni = str(data.get("dni") or "")
        err = str(data.get("error_msg") or "")
        if estado == "completado":
            resumen = f"{comando_nombre}: {'con datos' if has_data else 'sin datos'}"
            if dni:
                resumen = f"{resumen} (DNI {dni})"
        elif estado == "timeout":
            resumen = f"{comando_nombre}: timeout"
        else:
            resumen = f"{comando_nombre}: error"
            if err:
                resumen = f"{resumen} — {err[:80]}"
        payload_doc = {
            "tipo": "telegram",
            "creado_at": data.get("creado_at") or data.get("completado_at"),
            "fecha_dia": _fecha_dia_from_iso_or_ts(
                data.get("creado_at") or data.get("completado_at")
            ),
            "campaign_id": str(cliente.get("campaign_id") or ""),
            "seccion_key": str(cliente.get("seccion_key") or ""),
            "cliente_id": str(cliente.get("cliente_id") or ""),
            "cliente_nombre": str(cliente.get("nombre") or ""),
            "codigo_cliente": str(cliente.get("codigo_cliente") or ""),
            "dni": dni,
            "usuario_uid": str(solicitante.get("uid") or ""),
            "usuario_nombre": str(solicitante.get("nombre") or ""),
            "usuario_rol": str(solicitante.get("rol") or "gestor"),
            "resumen": resumen[:200],
            "origen_id": doc.id,
            "origen_coleccion": "doxeo_jobs",
            "payload": {
                "job_id": doc.id,
                "comando_id": str(data.get("comando_id") or ""),
                "comando_nombre": comando_nombre,
                "estado": estado,
                "has_data": has_data,
                "error_msg": err[:300],
            },
        }
        if _set_event(db, event_id, payload_doc, dry_run=dry_run):
            written += 1
        else:
            skipped += 1
    return written, skipped


def backfill_historial_contacto(
    db: Any, *, dry_run: bool, limit: int | None
) -> tuple[int, int, int, int]:
    ubic_w = ubic_s = nota_w = nota_s = 0
    count = 0
    for doc in db.collection_group("historial_contacto").stream():
        if limit is not None and count >= limit:
            break
        count += 1
        data = doc.to_dict() or {}
        tipo = str(data.get("tipo") or "")
        meta = _client_meta_from_path(db, doc.reference.path)
        when = data.get("fecha") or data.get("fecha_evento")
        fecha_dia = _fecha_dia_from_iso_or_ts(when)
        usuario_uid = str(data.get("usuario_uid") or "")
        usuario_nombre = str(data.get("usuario_nombre") or "")
        usuario_rol = str(data.get("rol_editor") or "gestor")

        if tipo == "gps_verificado":
            gps = data.get("gps") if isinstance(data.get("gps"), dict) else {}
            lat = gps.get("latitude")
            lng = gps.get("longitude")
            lat_ant = gps.get("latitude_anterior")
            lng_ant = gps.get("longitude_anterior")
            coord = ""
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                coord = f"{float(lat):.5f}, {float(lng):.5f}"
            event_id = f"ubicacion_{doc.id}"
            payload_doc = {
                "tipo": "ubicacion",
                "creado_at": when,
                "fecha_dia": fecha_dia,
                "campaign_id": meta["campaign_id"],
                "seccion_key": meta["seccion_key"] or str(data.get("seccion_key") or ""),
                "cliente_id": meta["cliente_id"],
                "cliente_nombre": meta["cliente_nombre"],
                "codigo_cliente": meta["codigo_cliente"],
                "dni": meta["dni"],
                "usuario_uid": usuario_uid,
                "usuario_nombre": usuario_nombre,
                "usuario_rol": usuario_rol,
                "resumen": f"GPS verificado: {coord}" if coord else "GPS verificado",
                "origen_id": doc.id,
                "origen_coleccion": "historial_contacto",
                "payload": {
                    "lat": lat,
                    "lng": lng,
                    "accuracy": gps.get("accuracy") or 0,
                    **(
                        {"lat_anterior": lat_ant, "lng_anterior": lng_ant}
                        if lat_ant is not None and lng_ant is not None
                        else {}
                    ),
                    "maps_url": (
                        f"https://www.google.com/maps?q={lat},{lng}"
                        if lat is not None and lng is not None
                        else ""
                    ),
                },
            }
            if _set_event(db, event_id, payload_doc, dry_run=dry_run):
                ubic_w += 1
            else:
                ubic_s += 1
            continue

        # Observaciones de campo (mobile) / alternativas
        origen = str(data.get("origen_actualizacion") or "")
        if origen != "mobile" and tipo not in {"direccion", "telefono", "alternativa"}:
            continue
        if tipo == "gps_verificado":
            continue
        nota = str(data.get("nota") or "").strip()
        if not nota and not data.get("direccion_nueva") and not data.get("telefono_nuevo"):
            continue
        event_id = f"nota_campo_{doc.id}"
        resumen = nota or str(data.get("direccion_nueva") or data.get("telefono_nuevo") or "Observación")
        payload_doc = {
            "tipo": "nota_campo",
            "creado_at": when,
            "fecha_dia": fecha_dia,
            "campaign_id": meta["campaign_id"],
            "seccion_key": meta["seccion_key"] or str(data.get("seccion_key") or ""),
            "cliente_id": meta["cliente_id"],
            "cliente_nombre": meta["cliente_nombre"],
            "codigo_cliente": meta["codigo_cliente"],
            "dni": meta["dni"],
            "usuario_uid": usuario_uid,
            "usuario_nombre": usuario_nombre,
            "usuario_rol": usuario_rol,
            "resumen": resumen[:200],
            "origen_id": doc.id,
            "origen_coleccion": "historial_contacto",
            "payload": {
                "nota": nota,
                "tipo_contacto": tipo or "alternativa",
                "direccion_nueva": str(data.get("direccion_nueva") or ""),
                "telefono_nuevo": str(data.get("telefono_nuevo") or ""),
            },
        }
        if _set_event(db, event_id, payload_doc, dry_run=dry_run):
            nota_w += 1
        else:
            nota_s += 1
    return ubic_w, ubic_s, nota_w, nota_s


def backfill_notas_gestion(
    db: Any, *, dry_run: bool, limit: int | None
) -> tuple[int, int]:
    written = skipped = 0
    count = 0
    for doc in db.collection_group("historial_visitas").stream():
        if limit is not None and count >= limit:
            break
        count += 1
        data = doc.to_dict() or {}
        nota = str(data.get("nota_gestor") or "").strip()
        if not nota:
            continue
        meta = _client_meta_from_path(
            db, doc.reference.path.replace("/historial_visitas/", "/historial_contacto/")
        )
        # path replace hack: use real path parts
        parts = doc.reference.path.split("/")
        try:
            i = parts.index("campañas")
            meta["campaign_id"] = parts[i + 1]
            meta["seccion_key"] = parts[i + 3]
            meta["cliente_id"] = parts[i + 5]
            if not meta["cliente_nombre"]:
                meta = _client_meta_from_path(
                    db,
                    f"campañas/{meta['campaign_id']}/gestores/{meta['seccion_key']}/"
                    f"clientes/{meta['cliente_id']}/historial_contacto/x",
                )
        except Exception:
            pass
        when = data.get("fecha_gestion") or data.get("timestamp") or data.get("fecha")
        estado = str(data.get("estado_gestion") or "")
        event_id = f"nota_gestion_{doc.id}"
        payload_doc = {
            "tipo": "nota_gestion",
            "creado_at": when,
            "fecha_dia": _fecha_dia_from_iso_or_ts(when),
            "campaign_id": meta["campaign_id"] or str(data.get("campaign_id") or ""),
            "seccion_key": meta["seccion_key"] or str(data.get("seccion_key") or ""),
            "cliente_id": meta["cliente_id"] or str(data.get("client_id") or ""),
            "cliente_nombre": meta["cliente_nombre"],
            "codigo_cliente": meta["codigo_cliente"],
            "dni": meta["dni"],
            "usuario_uid": str(data.get("gestor_uid") or ""),
            "usuario_nombre": str(data.get("gestor_nombre") or ""),
            "usuario_rol": "gestor",
            "resumen": f"Gestión ({estado}): {nota}"[:200],
            "origen_id": doc.id,
            "origen_coleccion": "historial_visitas",
            "payload": {"nota": nota, "estado_gestion": estado},
        }
        if _set_event(db, event_id, payload_doc, dry_run=dry_run):
            written += 1
        else:
            skipped += 1
    return written, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill bitacora_campo")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-telegram", action="store_true")
    parser.add_argument("--skip-contacto", action="store_true")
    parser.add_argument("--skip-gestion", action="store_true")
    args = parser.parse_args()

    sa = _resolve_sa_path()
    if not sa.exists():
        print(f"ERROR: No se encontró service account: {sa}", file=sys.stderr)
        print(
            "Defina FIREBASE_SERVICE_ACCOUNT_PATH o coloque el JSON en admin-app/.",
            file=sys.stderr,
        )
        return 1

    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(sa)))
    db = firestore.client()

    mode = "DRY-RUN" if args.dry_run else "WRITE"
    print(f"[{mode}] Backfill bitacora_campo — SA={sa.name}")

    if not args.skip_telegram:
        w, s = backfill_telegram(db, dry_run=args.dry_run, limit=args.limit)
        print(f"  telegram: escritos={w} omitidos(existentes)={s}")
    if not args.skip_contacto:
        uw, us, nw, ns = backfill_historial_contacto(
            db, dry_run=args.dry_run, limit=args.limit
        )
        print(f"  ubicacion: escritos={uw} omitidos={us}")
        print(f"  nota_campo: escritos={nw} omitidos={ns}")
    if not args.skip_gestion:
        w, s = backfill_notas_gestion(db, dry_run=args.dry_run, limit=args.limit)
        print(f"  nota_gestion: escritos={w} omitidos={s}")

    print("Listo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
