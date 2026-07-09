"""
Firebase Service
Handles connection to Firebase/Firestore and uploading client data
organized by Seccion (gestor assignment).
"""

from __future__ import annotations

import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
from google.cloud.firestore import SERVER_TIMESTAMP as _SERVER_TIMESTAMP
from google.cloud.firestore_v1.base_query import BaseQuery
import os
import sys
import json
import mimetypes
from datetime import datetime, timedelta
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FIREBASE_CONFIG, SERVICE_ACCOUNT_KEY_PATH
from services.database import POOL_REASIGNACION_SECTION, MOTIVO_BAJA_EXCEL_BANCO


class FirebaseService:
    def __init__(self):
        self.db: Any = None
        self.app: Any = None
        self._initialized = False
    
    def initialize(self, service_key_path: str | None = None) -> bool:
        """
        Initialize Firebase Admin SDK with a service account key.
        
        Args:
            service_key_path: Path to the service account JSON key file.
                            If None, uses the default from config.
        
        Returns:
            True if initialization succeeded, False otherwise.
        """
        if self._initialized:
            return True
        
        key_path = service_key_path or SERVICE_ACCOUNT_KEY_PATH
        
        # Check if path is relative; resolve from app directory
        if not os.path.isabs(key_path):
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            key_path = os.path.join(app_dir, key_path)
        
        if not os.path.exists(key_path):
            raise FileNotFoundError(
                f"No se encontró el archivo de credenciales: {key_path}\n"
                f"Descárgalo desde: Firebase Console > Configuración del proyecto > "
                f"Cuentas de servicio > Generar nueva clave privada"
            )
        
        try:
            cred = credentials.Certificate(key_path)
            # Check if already initialized (e.g. by another FirebaseService instance)
            try:
                self.app = firebase_admin.get_app()
            except ValueError:
                self.app = firebase_admin.initialize_app(cred, {
                    "projectId": FIREBASE_CONFIG["projectId"],
                    "storageBucket": FIREBASE_CONFIG.get("storageBucket", ""),
                })
            self.db = firestore.client()
            self._initialized = True
            return True
        except Exception as e:
            raise ConnectionError(f"Error al conectar con Firebase: {str(e)}")
    
    def is_initialized(self) -> bool:
        return self._initialized

    def firestore_timestamp(self):
        """Expose a server timestamp token for Firestore writes."""
        return _SERVER_TIMESTAMP

    def upload_generated_letter(
        self,
        file_path: str,
        campaign_id: str,
        numero_carta: int,
        seccion_key: str,
        gestor_uid: str,
        cliente_id: str = "",
        extra_metadata: dict[str, Any] | None = None,
    ) -> dict:
        """
        Upload a generated letter to Firebase Storage and persist metadata
        into Firestore/cartas_generadas.
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        if not os.path.isfile(file_path):
            raise FileNotFoundError(file_path)

        ext = os.path.splitext(file_path)[1].lower()
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        file_name = os.path.basename(file_path)
        safe_campaign = (campaign_id or "sin_campana").strip() or "sin_campana"
        safe_section = (seccion_key or "SIN_SECCION").strip() or "SIN_SECCION"
        safe_uid = (gestor_uid or "SIN_GESTOR").strip() or "SIN_GESTOR"
        storage_path = f"cartas_generadas/{safe_campaign}/{safe_section}/{safe_uid}/{file_name}"

        bucket = storage.bucket()
        blob = bucket.blob(storage_path)
        blob.upload_from_filename(file_path, content_type=mime_type)

        size_bytes = os.path.getsize(file_path)
        ext_tag = ext.lstrip(".") or "bin"
        doc_id = (
            f"{safe_campaign}_{numero_carta}_{safe_section}_{safe_uid}_"
            f"{os.path.splitext(file_name)[0]}_{ext_tag}"
        )
        metadata = {
            "campaign_id": safe_campaign,
            "numero_carta": int(numero_carta),
            "cliente_id": str(cliente_id or ""),
            "seccion_key": safe_section,
            "gestor_uid": safe_uid,
            "nombre_archivo": file_name,
            "mime_type": mime_type,
            "tipo": ext_tag,
            "storage_path": storage_path,
            "size_bytes": int(size_bytes),
            "estado": "disponible",
            "created_at": _SERVER_TIMESTAMP,
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        self.db.collection("cartas_generadas").document(doc_id).set(metadata, merge=True)
        return metadata

    def upload_letter_template(self, numero_carta: int, local_path: str) -> dict:
        """
        Upload an official Word template to Storage and register metadata in
        Firestore ``configuracion/plantillas_cartas``.
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")
        if not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)

        numero = int(numero_carta)
        if numero < 1 or numero > 5:
            raise ValueError("numero_carta debe estar entre 1 y 5.")

        storage_path = f"plantillas_carta/carta_{numero}.docx"
        mime_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        size_bytes = os.path.getsize(local_path)

        bucket = storage.bucket()
        blob = bucket.blob(storage_path)
        blob.upload_from_filename(local_path, content_type=mime_type)

        entry = {
            "numero_carta": numero,
            "storage_path": storage_path,
            "nombre_archivo": os.path.basename(local_path),
            "size_bytes": int(size_bytes),
            "mime_type": mime_type,
            "updated_at": _SERVER_TIMESTAMP,
        }
        ref = self.db.collection("configuracion").document("plantillas_cartas")
        ref.set({str(numero): entry}, merge=True)
        return entry

    def remove_letter_template(self, numero_carta: int) -> None:
        """Remove template metadata from Firestore (Storage blob kept for audit)."""
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")
        numero = int(numero_carta)
        ref = self.db.collection("configuracion").document("plantillas_cartas")
        ref.set({str(numero): firestore.DELETE_FIELD}, merge=True)
    
    # Fields set by gestors in the field — must be preserved on re-upload
    _VISIT_FIELDS = (
        "estado_gestion", "fecha_gestion", "nota_gestor", "gps_gestor",
        "ubicacion_verificada", "historial_zona",
        "gps_latitud", "gps_longitud", "gps_timestamp",
        "nivel_1", "nivel_2", "nivel_3", "nivel_4",
        "canal_gestion", "fecha_promesa_pago", "monto_promesa_pago",
        "direccion", "telefono_movil", "ultima_nota_contacto",
        "fecha_actualizacion_contacto_iso",
        "actualizado_por_uid", "actualizado_por_nombre", "actualizado_por_email",
        "origen_actualizacion",
        "etiquetas",
    )

    def _read_existing_visit_data(self, campaign_ref, seccion: str) -> dict:
        """
        Read existing visit statuses for a whole section so we can preserve
        them when re-uploading the portfolio.

        Returns:
            dict  { client_id: { estado_gestion, fecha_gestion, nota_gestor, gps_gestor } }
        """
        result = {}
        try:
            clients_ref = (
                campaign_ref.collection("gestores")
                .document(seccion)
                .collection("clientes")
            )
            for doc in clients_ref.stream():
                d = doc.to_dict()
                has_visit = d.get("estado_gestion") and d["estado_gestion"] != "pendiente"
                has_contact_update = bool(d.get("fecha_actualizacion_contacto_iso"))
                if has_visit or has_contact_update:
                    result[doc.id] = {k: d.get(k) for k in self._VISIT_FIELDS}
        except Exception:
            pass  # first upload — nothing to preserve
        return result

    def _sections_for_visit_lookup(
        self,
        seccion_key: str,
        client_data: dict,
    ) -> list[str]:
        """Secciones donde buscar visitas previas (territorial + _CALL_)."""
        from .database import make_call_section_key
        from .excel_parser import make_seccion_key

        sections = [seccion_key]
        uid = str(client_data.get("call_gestor_uid") or "").strip()
        if uid:
            call_sec = make_call_section_key(uid)
            if call_sec not in sections:
                sections.append(call_sec)
        if seccion_key.startswith("_CALL_"):
            terr = make_seccion_key(
                str(client_data.get("region") or ""),
                str(client_data.get("zona") or ""),
                str(client_data.get("seccion") or "SIN_SECCION"),
            )
            if terr not in sections:
                sections.append(terr)
        return sections

    def _read_visit_for_client_cross_sections(
        self,
        campaign_ref,
        client_id: str,
        seccion_keys: list[str],
    ) -> dict:
        """Merge visit data from multiple sections (más reciente gana)."""
        best: dict = {}
        best_ts = ""
        for sk in seccion_keys:
            visits = self._read_existing_visit_data(campaign_ref, sk)
            prev = visits.get(str(client_id), {})
            if not prev:
                continue
            ts = str(
                prev.get("fecha_gestion")
                or prev.get("fecha_actualizacion_contacto_iso")
                or ""
            )
            if ts >= best_ts:
                best = prev
                best_ts = ts
        return best

    def _seed_contactos_to_batch(self, batch, client_ref, contactos_seed: list) -> int:
        """Write durable contact agenda entries into historial_contacto subcollection."""
        if not contactos_seed:
            return 0
        from .campaign_manager import contacto_seed_to_firestore_entry
        count = 0
        for seed_entry in contactos_seed:
            event_id = str(seed_entry.get("event_id", "") or "").strip()
            if not event_id:
                continue
            hist_ref = client_ref.collection("historial_contacto").document(event_id)
            batch.set(
                hist_ref,
                contacto_seed_to_firestore_entry(seed_entry),
                merge=True,
            )
            count += 1
        return count

    def upload_cartera(self, by_seccion: dict, campaign_id: str | None = None, 
                       progress_callback=None) -> dict:
        """
        Upload client data to Firestore, organized by composite section key.
        
        The *by_seccion* dict is keyed by composite keys of the form
        ``region_zona_seccion`` (e.g. ``01_1211_H``).  Each key becomes
        a Firestore document under ``campañas/{campaign_id}/gestores/``.
        
        IDEMPOTENT: Uses a fixed campaign ID ("cartera_activa") so
        re-distributing the portfolio updates existing clients rather than
        creating duplicates.  Visit data recorded by field gestors
        (estado_gestion, fecha_gestion, nota_gestor, gps_gestor) is
        preserved for clients that already exist.
        
        Structure in Firestore:
            campañas/{campaign_id}/
                metadata: { fecha, total_clientes, secciones, etc. }
            campañas/{campaign_id}/gestores/{seccion_key}/
                info: { seccion_key, seccion, region, zona, num_clientes, ... }
            campañas/{campaign_id}/gestores/{seccion_key}/clientes/{codigo_cliente}/
                { all client data }
        
        Args:
            by_seccion: Dict of seccion_key -> list of client dicts
            campaign_id: Optional campaign ID. Defaults to "cartera_activa".
            progress_callback: Optional callback(current, total, message) for progress
        
        Returns:
            dict with upload statistics
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado. Llame a initialize() primero.")
        
        # Always use the same campaign id — idempotent uploads
        if campaign_id is None:
            campaign_id = "cartera_activa"
        
        total_clients = sum(len(clients) for clients in by_seccion.values())
        uploaded = 0
        preserved = 0
        errors = []
        
        try:
            # Create / overwrite campaign metadata
            campaign_ref = self.db.collection("campañas").document(campaign_id)
            campaign_ref.set({
                "fecha_creacion": _SERVER_TIMESTAMP,
                "total_clientes": total_clients,
                "total_secciones": len(by_seccion),
                "secciones": list(by_seccion.keys()),
                "estado": "activa"
            })
            
            if progress_callback:
                progress_callback(0, total_clients, "Campaña creada, subiendo clientes...")
            
            # Upload each seccion
            for seccion, clients in by_seccion.items():
                # Read existing visit data BEFORE overwriting
                existing_visits = self._read_existing_visit_data(campaign_ref, seccion)

                # Create / overwrite gestor document (keyed by composite seccion_key)
                gestor_ref = campaign_ref.collection("gestores").document(seccion)
                
                deuda_total = sum(float(c.get("importe_deuda_asignada", 0) or 0) for c in clients)
                deuda_pendiente = sum(float(c.get("importe_deuda_pendiente", 0) or 0) for c in clients)
                clientes_con_coordenadas = sum(
                    1 for c in clients
                    if float(c.get("coordenada_y", 0) or 0) != 0
                    and float(c.get("coordenada_x", 0) or 0) != 0
                )
                
                # Extract region/zona/letter from clients
                sample = clients[0] if clients else {}
                region_val = sample.get("region", "")
                zona_val = sample.get("zona", "")
                seccion_letter = sample.get("seccion", "")

                gestor_ref.set({
                    "seccion_key": seccion,
                    "seccion": seccion_letter,
                    "region": region_val,
                    "zona": zona_val,
                    "num_clientes": len(clients),
                    "clientes_con_coordenadas": clientes_con_coordenadas,
                    "deuda_asignada_total": round(deuda_total, 2),
                    "deuda_pendiente_total": round(deuda_pendiente, 2),
                    "fecha_asignacion": _SERVER_TIMESTAMP,
                    "estado": "pendiente"
                })
                
                # Upload each client under the gestor
                batch = self.db.batch()
                batch_count = 0
                
                for client in clients:
                    client_id = client.get("codigo_cliente", "")
                    if not client_id:
                        client_id = f"unknown_{uploaded}"

                    contactos_seed = client.pop("contactos_seed", None) or []
                    
                    client_ref = gestor_ref.collection("clientes").document(str(client_id))
                    
                    # Prepare client data for Firestore
                    client_data = {
                        **client,
                        "estado_gestion": client.get("estado_gestion", "pendiente"),
                        "fecha_subida": _SERVER_TIMESTAMP,
                        "seccion": client.get("seccion", ""),
                        "seccion_key": seccion,
                        "activo_en_cartera": client.get("activo_en_cartera", True),
                    }
                    
                    # Preserve visit data if the gestor already visited this client
                    prev = existing_visits.get(str(client_id))
                    if prev:
                        client_data.update(prev)
                        preserved += 1
                    
                    batch.set(client_ref, client_data)
                    batch_count += 1
                    uploaded += 1

                    # Seed durable contact agenda into historial_contacto (idempotent by event_id)
                    if contactos_seed:
                        batch_count += self._seed_contactos_to_batch(
                            batch, client_ref, contactos_seed
                        )
                        if batch_count >= 400:
                            batch.commit()
                            batch = self.db.batch()
                            batch_count = 0
                    
                    # Firestore batch limit is 500
                    if batch_count >= 400:
                        batch.commit()
                        batch = self.db.batch()
                        batch_count = 0
                    
                    if progress_callback:
                        progress_callback(
                            uploaded, total_clients,
                            f"Sección {seccion}: {client.get('nombre_completo', 'N/A')}"
                        )
                
                # Commit remaining batch
                if batch_count > 0:
                    batch.commit()
            
            # Update campaign as completed
            total_clientes_con_coordenadas = sum(
                sum(
                    1 for c in clients
                    if float(c.get("coordenada_y", 0) or 0) != 0
                    and float(c.get("coordenada_x", 0) or 0) != 0
                )
                for clients in by_seccion.values()
            )
            campaign_ref.update({
                "estado": "distribuida",
                "clientes_subidos": uploaded,
                "total_clientes_con_coordenadas": total_clientes_con_coordenadas,
                "fecha_distribucion": _SERVER_TIMESTAMP
            })
            
        except Exception as e:
            errors.append(str(e))
        
        return {
            "campaign_id": campaign_id,
            "total_uploaded": uploaded,
            "total_expected": total_clients,
            "preserved_visits": preserved,
            "errors": errors,
            "success": len(errors) == 0
        }
    
    def get_gestores(self, campaign_id: str) -> list:
        """Get list of gestores for a campaign."""
        if not self._initialized:
            return []
        
        try:
            gestores_ref = self.db.collection("campañas").document(campaign_id).collection("gestores")
            docs = gestores_ref.stream()
            return [doc.to_dict() for doc in docs]
        except Exception:
            return []

    def get_campaign_status(self, campaign_id: str = "cartera_activa") -> dict:
        """
        Read all sections and clients from a campaign, including visit statuses
        set by field gestors.  Used by the desktop monitor view.

        Optimized: reads all gestor subcollections in parallel using
        ThreadPoolExecutor instead of sequential N+1 queries.

        Returns:
            {
              "campaign_id": str,
              "secciones": {
                  "A": {
                      "info": { ... },
                      "clientes": [ { ...client_data, estado_gestion, nota_gestor, gps_gestor, ... }, ... ]
                  },
                  ...
              },
              "resumen": {
                  "total": int,
                  "pendiente": int,
                  "visitado_habido": int,
                  "visitado_no_habido": int,
                  "fallecido_inubicable": int,
                  "deuda_total": float,
                  "deuda_visitada": float,
              }
            }
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        campaign_ref = self.db.collection("campañas").document(campaign_id)

        # Step 1: get gestor documents (single query)
        gestores_list = list(campaign_ref.collection("gestores").stream())

        # Step 2: read all client subcollections in parallel
        def _read_section(gestor_doc):
            sec_id = gestor_doc.id
            sec_info = gestor_doc.to_dict()
            clients = []
            for cdoc in (campaign_ref.collection("gestores")
                         .document(sec_id)
                         .collection("clientes")
                         .stream()):
                c = cdoc.to_dict()
                c["_id"] = cdoc.id
                clients.append(c)
            return sec_id, sec_info, clients

        secciones = {}
        total = 0
        pendiente = 0
        visitado_habido = 0
        visitado_no_habido = 0
        fallecido_inubicable = 0
        suplantacion = 0
        pago_no_registrado = 0
        deuda_total = 0.0
        deuda_visitada = 0.0

        workers = min(len(gestores_list), 10) or 1
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_read_section, gd): gd for gd in gestores_list}
            for fut in as_completed(futures):
                sec_id, sec_info, clients = fut.result()

                for c in clients:
                    estado = c.get("estado_gestion", "pendiente")
                    deuda = float(c.get("importe_deuda_asignada", 0) or 0)
                    deuda_total += deuda
                    total += 1
                    if estado == "pendiente":
                        pendiente += 1
                    elif estado == "visitado_habido":
                        visitado_habido += 1
                        deuda_visitada += deuda
                    elif estado == "visitado_no_habido":
                        visitado_no_habido += 1
                        deuda_visitada += deuda
                    elif estado == "fallecido_inubicable":
                        fallecido_inubicable += 1
                        deuda_visitada += deuda
                    elif estado == "suplantacion":
                        suplantacion += 1
                        deuda_visitada += deuda
                    elif estado == "pago_no_registrado":
                        pago_no_registrado += 1
                        deuda_visitada += deuda

                secciones[sec_id] = {"info": sec_info, "clientes": clients}

        return {
            "campaign_id": campaign_id,
            "secciones": secciones,
            "resumen": {
                "total": total,
                "pendiente": pendiente,
                "visitado_habido": visitado_habido,
                "visitado_no_habido": visitado_no_habido,
                "fallecido_inubicable": fallecido_inubicable,
                "suplantacion": suplantacion,
                "pago_no_registrado": pago_no_registrado,
                "deuda_total": round(deuda_total, 2),
                "deuda_visitada": round(deuda_visitada, 2),
            }
        }

    def cleanup_old_campaigns(self) -> dict:
        """
        Delete ALL campaigns except 'cartera_activa'.
        This removes duplicate data created by previous timestamp-based uploads.

        Returns:
            {"deleted": [list of deleted IDs], "kept": "cartera_activa"}
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        campaigns_ref = self.db.collection("campañas")
        deleted = []

        for camp_doc in campaigns_ref.stream():
            if camp_doc.id == "cartera_activa":
                continue  # keep the canonical campaign
            self._delete_campaign_tree(camp_doc.id)
            deleted.append(camp_doc.id)

        return {"deleted": deleted, "kept": "cartera_activa"}

    def cleanup_old_data(self, days_to_keep: int = 90) -> dict:
        """
        Smart cleanup: delete old campaigns except ``cartera_activa``.

        A campaign is considered old when its ``fecha_distribucion`` or
        ``fecha_creacion`` is older than ``days_to_keep`` days.
        Campaigns without date metadata are preserved by default.
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        days = max(1, int(days_to_keep or 90))
        cutoff = datetime.now().replace(tzinfo=None) - timedelta(days=days)

        deleted: list[str] = []
        kept: list[str] = []

        for camp_doc in self.db.collection("campañas").stream():
            if camp_doc.id == "cartera_activa":
                kept.append(camp_doc.id)
                continue

            data = camp_doc.to_dict() or {}
            dt = data.get("fecha_distribucion") or data.get("fecha_creacion")
            if hasattr(dt, "replace"):
                try:
                    dt = dt.replace(tzinfo=None)
                except Exception:
                    pass

            if not isinstance(dt, datetime):
                kept.append(camp_doc.id)
                continue

            if dt < cutoff:
                self._delete_campaign_tree(camp_doc.id)
                deleted.append(camp_doc.id)
            else:
                kept.append(camp_doc.id)

        return {
            "days_to_keep": days,
            "deleted_campaigns": deleted,
            "kept_campaigns": kept,
        }

    def _delete_campaign_tree(self, campaign_id: str) -> tuple[int, int]:
        """Delete ``campañas/{campaign_id}`` with gestores/clientes subtree."""
        campaign_ref = self.db.collection("campañas").document(campaign_id)
        gestores_ref = campaign_ref.collection("gestores")
        deleted_clients = 0
        deleted_secciones = 0

        for gestor_doc in gestores_ref.stream():
            clients_ref = gestores_ref.document(gestor_doc.id).collection("clientes")
            batch = self.db.batch()
            count = 0
            section_count = 0
            for client_doc in clients_ref.stream():
                batch.delete(client_doc.reference)
                count += 1
                section_count += 1
                if count >= 400:
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            if count > 0:
                batch.commit()
            deleted_clients += section_count
            gestor_doc.reference.delete()
            deleted_secciones += 1

        campaign_ref.delete()
        return deleted_clients, deleted_secciones

    def delete_cartera_activa(self, progress_callback=None) -> dict:
        """
        Delete the 'cartera_activa' campaign and ALL its subcollections
        (gestores → clientes).  This is the nuclear cleanup option.

        Args:
            progress_callback: Optional callable(step, total, message).

        Returns:
            {"deleted_clients": int, "deleted_secciones": int, "campaign_deleted": bool}
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        campaign_ref = self.db.collection("campañas").document("cartera_activa")
        camp_doc = campaign_ref.get()
        if not camp_doc.exists:
            return {"deleted_clients": 0, "deleted_secciones": 0, "campaign_deleted": False}
        deleted_clients, deleted_secciones = self._delete_campaign_tree("cartera_activa")
        if progress_callback:
            progress_callback(1, 1, "Campaña eliminada")

        return {
            "deleted_clients": deleted_clients,
            "deleted_secciones": deleted_secciones,
            "campaign_deleted": True,
        }

    def test_connection(self) -> bool:
        """Test if the Firebase connection is working."""
        if not self._initialized:
            return False
        try:
            # Try to read a document (even if it doesn't exist)
            self.db.collection("_test_connection").document("ping").get()
            return True
        except Exception:
            return False
    
    def create_gestor_user(self, email: str, password: str, nombre: str, 
                           seccion: str = "", telefono: str = "", zona: str = "",
                           region: str = "", rol: str = "gestor",
                           secciones: list[str] | None = None,
                           canal: str = "campo") -> dict:
        """
        Create a Firebase Auth user + Firestore profile for a user.
        
        Args:
            email: User's email (used for login)
            password: Initial password
            nombre: Full name
            seccion: Assigned section letter (e.g., 'A', 'B') — legacy single
            telefono: Phone number
            zona: Coverage zone
            region: Region code (e.g., '01', '02')
            rol: User role ('gestor', 'asistente', 'supervisor', 'admin')
            secciones: List of composite keys (e.g., ['01_1211_H', '01_1211_C']).
                       If provided, overrides seccion/region/zona logic.
            canal: 'campo' (gestor territorial) o 'call' (call center tramo 1).
        
        Returns:
            dict with uid and success status
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")
        
        # Validate role
        valid_roles = ('gestor', 'asistente', 'supervisor', 'admin')
        if rol not in valid_roles:
            rol = 'gestor'

        canal = (canal or "campo").strip().lower()
        if canal not in ("campo", "call"):
            canal = "campo"
        
        # Normalize email to lowercase (Firebase Auth does this internally)
        normalized_email = email.strip().lower()
        normalized_seccion = seccion.strip().upper()

        # Build secciones list
        if canal == "call" and rol == "gestor":
            final_secciones = []  # se completa tras obtener UID
        elif secciones:
            final_secciones = sorted(set(secciones))
            # Derive region/zona/seccion from first key for backward compat
            if final_secciones:
                parts = final_secciones[0].split("_")
                if len(parts) == 3:
                    region = region or parts[0]
                    zona = zona or parts[1]
                    normalized_seccion = normalized_seccion or parts[2]
        else:
            if region and zona and normalized_seccion:
                final_secciones = [f"{region}_{zona}_{normalized_seccion}"]
            elif normalized_seccion:
                final_secciones = [normalized_seccion]
            else:
                final_secciones = []
        
        try:
            # Create Firebase Auth user
            user_record = auth.create_user(
                email=normalized_email,
                password=password,
                display_name=nombre,
            )
            
            if canal == "call" and rol == "gestor":
                call_section = f"_CALL_{user_record.uid}"
                final_secciones = [call_section]

            profile_data = {
                "nombre": nombre,
                "email": normalized_email,
                "seccion": normalized_seccion,
                "secciones": final_secciones,
                "telefono": telefono,
                "zona": zona,
                "region": region,
                "rol": rol,
                "canal": canal,
                "activo": True,
                "uid": user_record.uid,
                "fecha_creacion": _SERVER_TIMESTAMP,
            }
            
            # Create Firestore profile keyed by UID (canonical document)
            self.db.collection("usuarios").document(user_record.uid).set(profile_data)
            
            return {"uid": user_record.uid, "success": True, "error": None}
        except Exception as e:
            return {"uid": None, "success": False, "error": str(e)}
    
    def list_gestor_users(self) -> list:
        """List all gestor users from Firestore, deduplicating by UID."""
        if not self._initialized:
            return []
        try:
            docs = self.db.collection("usuarios").stream()
            seen_uids: set = set()
            result = []
            for d in docs:
                data = {"id": d.id, **d.to_dict()}
                uid = data.get("uid") or d.id
                if uid in seen_uids:
                    continue
                seen_uids.add(uid)
                result.append(data)
            return result
        except Exception:
            return []

    def list_campaign_sections(self, campaign_id: str = "cartera_activa") -> list:
        """List sections from a campaign's gestores subcollection.
        Returns list of dicts with id, region, zona, seccion, num_clientes.
        Falls back to 'cartera_activa' if the given campaign_id has no sections.
        """
        if not self._initialized:
            return []
        def _fetch(cid):
            docs = self.db.collection("campañas").document(cid).collection("gestores").stream()
            return sorted([{"id": d.id, **d.to_dict()} for d in docs], key=lambda x: x["id"])
        try:
            sections = _fetch(campaign_id)
            if not sections and campaign_id != "cartera_activa":
                sections = _fetch("cartera_activa")
            return sections
        except Exception:
            return []

    def list_all_sections(self) -> list:
        """Aggregate unique sections from territorial catalog + campaign + user profiles.
        Returns list of dicts with id, region, zona, seccion, num_clientes, source.
        """
        if not self._initialized:
            return []

        seen_keys: dict[str, dict] = {}

        # 1) Sections from territorial catalog (primary source)
        try:
            cat_doc = self.db.collection("estructura_territorial").document("catalogo").get()
            if cat_doc.exists:
                cat = cat_doc.to_dict() or {}
                for r, rdata in (cat.get("regiones") or {}).items():
                    for z, zdata in (rdata.get("zonas") or {}).items():
                        for s in (zdata.get("secciones") or []):
                            key = f"{r}_{z}_{s}"
                            seen_keys[key] = {
                                "id": key, "region": r, "zona": z,
                                "seccion": s, "num_clientes": 0,
                                "source": "catálogo",
                            }
        except Exception:
            pass

        # 2) Sections from active campaign (add client counts)
        try:
            docs = (self.db.collection("campañas")
                    .document("cartera_activa")
                    .collection("gestores").stream())
            for d in docs:
                data = d.to_dict() or {}
                key = d.id
                seen_keys[key] = {
                    "id": key,
                    "region": data.get("region", ""),
                    "zona": data.get("zona", ""),
                    "seccion": data.get("seccion", key.split("_")[-1] if "_" in key else key),
                    "num_clientes": data.get("num_clientes", 0),
                    "source": "campaña",
                }
        except Exception:
            pass

        # 3) Sections from existing user profiles (historical)
        try:
            for udoc in self.db.collection("usuarios").stream():
                udata = udoc.to_dict() or {}
                secciones = udata.get("secciones") or []
                if isinstance(secciones, list):
                    for sk in secciones:
                        if not isinstance(sk, str) or sk in seen_keys:
                            continue
                        parts = sk.split("_") if "_" in sk else []
                        if len(parts) == 3:
                            seen_keys[sk] = {
                                "id": sk, "region": parts[0],
                                "zona": parts[1], "seccion": parts[2],
                                "num_clientes": 0, "source": "usuario",
                            }
                r = udata.get("region", "")
                z = udata.get("zona", "")
                s = udata.get("seccion", "").upper()
                if r and z and s:
                    key = f"{r}_{z}_{s}"
                    if key not in seen_keys:
                        seen_keys[key] = {
                            "id": key, "region": r, "zona": z,
                            "seccion": s, "num_clientes": 0,
                            "source": "usuario",
                        }
        except Exception:
            pass

        return sorted(seen_keys.values(), key=lambda x: x["id"])

    def upload_estructura_territorial(self, hierarchy: dict) -> bool:
        """Upload the region/zona/seccion hierarchy as a catalog document.

        Args:
            hierarchy: Output of ``excel_parser.get_hierarchy(clients)``.

        Writes to ``estructura_territorial/catalogo`` in Firestore.
        Returns True on success.
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        regiones_map: dict = {}
        total_zonas = 0
        total_secciones = 0

        for region_key, region_data in hierarchy.get("regions", {}).items():
            zonas_map: dict = {}
            for zona_key, zona_data in region_data.get("zonas", {}).items():
                secciones_list = sorted(zona_data.get("secciones", {}).keys())
                zonas_map[zona_key] = {"secciones": secciones_list}
                total_secciones += len(secciones_list)
                total_zonas += 1
            regiones_map[region_key] = {"zonas": zonas_map}

        self.db.collection("estructura_territorial").document("catalogo").set({
            "regiones": regiones_map,
            "fecha_actualizacion": _SERVER_TIMESTAMP,
            "total_regiones": len(regiones_map),
            "total_zonas": total_zonas,
            "total_secciones": total_secciones,
        })
        return True

    def get_estructura_territorial(self) -> dict:
        """Read the territorial catalog from Firestore.

        Returns the ``regiones`` map, e.g.::

            {"01": {"zonas": {"1211": {"secciones": ["H","C"]}, ...}}, ...}

        Returns empty dict if catalog doesn't exist.
        """
        if not self._initialized:
            return {}
        try:
            doc = self.db.collection("estructura_territorial").document("catalogo").get()
            if doc.exists:
                return (doc.to_dict() or {}).get("regiones", {})
            return {}
        except Exception:
            return {}

    def delete_gestor_user(self, uid: str) -> bool:
        """Delete a gestor from both Auth and Firestore (including duplicate docs)."""
        if not self._initialized:
            return False
        try:
            # Read the user doc to get the email before deleting
            user_doc = self.db.collection("usuarios").document(uid).get()
            email = None
            if user_doc.exists:
                email = user_doc.to_dict().get("email", "")
            
            # Delete Firebase Auth account
            auth.delete_user(uid)
            
            # Delete the UID-keyed Firestore doc
            self.db.collection("usuarios").document(uid).delete()
            
            # Also delete the email-derived duplicate doc if it exists
            if email:
                email_key = email.strip().lower().replace('.', '_').replace('@', '_')
                if email_key != uid:
                    try:
                        self.db.collection("usuarios").document(email_key).delete()
                    except Exception:
                        pass  # May not exist
                
                # Also clean up any other docs with matching email
                try:
                    email_docs = self.db.collection("usuarios").where(
                        "email", "==", email.strip().lower()
                    ).stream()
                    for d in email_docs:
                        if d.id != uid:
                            d.reference.delete()
                except Exception:
                    pass
            
            return True
        except Exception as e:
            print(f"Error deleting user: {e}")
            return False

    def update_user(self, uid: str, updates: dict) -> dict:
        """
        Update a user's Firestore profile and optionally Auth data.

        Args:
            uid: Firebase Auth UID
            updates: Dict of fields to update. Supported keys:
                nombre, seccion, telefono, zona, rol, activo, password (optional)

        Returns:
            dict with success and optional error
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        try:
            # Separate password from profile fields (password goes to Auth, not Firestore)
            new_password = updates.pop("password", None)

            # Update Firebase Auth display name if nombre changed
            auth_updates = {}
            if "nombre" in updates:
                auth_updates["display_name"] = updates["nombre"]
            if new_password and new_password.strip():
                auth_updates["password"] = new_password.strip()

            if auth_updates:
                auth.update_user(uid, **auth_updates)

            # Update Firestore profile (UID-keyed doc)
            if updates:
                self.db.collection("usuarios").document(uid).update(updates)

                # Also update email-derived duplicate doc if it exists
                user_doc = self.db.collection("usuarios").document(uid).get()
                if user_doc.exists:
                    email = user_doc.to_dict().get("email", "")
                    if email:
                        email_key = email.strip().lower().replace(".", "_").replace("@", "_")
                        if email_key != uid:
                            try:
                                dup = self.db.collection("usuarios").document(email_key).get()
                                if dup.exists:
                                    self.db.collection("usuarios").document(email_key).update(updates)
                            except Exception:
                                pass

            return {"success": True, "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Alertas ──────────────────────────────────────────────────

    @staticmethod
    def _normalize_alert(data: dict, doc_id: str) -> dict:
        """Map Firestore alert fields to UI-friendly keys."""
        row = dict(data)
        row["id"] = doc_id
        estado = row.get("estado_alerta", "pendiente")
        row["revisada"] = estado == "revisada"
        row["estado_label"] = "Revisada" if row["revisada"] else "Pendiente"

        nota = (row.get("nota") or "").strip()
        cliente = (row.get("cliente_nombre") or "").strip()
        tipo_raw = row.get("tipo", "general")
        row["tipo_alerta"] = tipo_raw
        if not row.get("mensaje"):
            parts = [p for p in (cliente, nota) if p]
            row["mensaje"] = " — ".join(parts) if parts else tipo_raw.replace("_", " ").title()

        if not row.get("gestor_nombre"):
            row["gestor_nombre"] = (
                row.get("gestor_email")
                or (row.get("gestor_uid") or "")[:12]
                or "—"
            )

        fecha = row.get("fecha")
        if hasattr(fecha, "strftime"):
            row["fecha_str"] = fecha.strftime("%d/%m/%Y %H:%M")
        elif fecha:
            row["fecha_str"] = str(fecha)[:19]
        else:
            row["fecha_str"] = "—"
        row["fecha"] = row["fecha_str"]

        gps = row.get("gps")
        if isinstance(gps, dict) and gps.get("latitude") is not None:
            row["gps_lat"] = gps.get("latitude")
            row["gps_lng"] = gps.get("longitude")
        elif row.get("gps_latitud") is not None:
            row["gps_lat"] = row.get("gps_latitud")
            row["gps_lng"] = row.get("gps_longitud")

        return row

    def get_alerts(self, estado: str = "", limit: int = 100) -> list:
        """
        Read alerts from the 'alertas' collection.

        Args:
            estado: Filter by estado_alerta ('pendiente', 'revisada', or '' for all).
            limit: Max number of alerts to return.

        Returns:
            List of normalized alert dicts with 'id' field included.
        """
        if not self._initialized:
            return []
        try:
            ref = self.db.collection("alertas")
            if estado:
                docs = ref.where("estado_alerta", "==", estado).stream()
            else:
                docs = ref.stream()

            alerts = []
            for d in docs:
                alerts.append(self._normalize_alert(d.to_dict() or {}, d.id))

            alerts.sort(key=lambda x: x.get("fecha_str", ""), reverse=True)
            return alerts[:limit]
        except Exception as e:
            print(f"Error reading alerts: {e}")
            return []

    def get_pending_alert_count(self) -> int:
        """Return count of pending alerts."""
        if not self._initialized:
            return 0
        try:
            from google.cloud.firestore_v1.aggregation import AggregationQuery
            ref = self.db.collection("alertas").where("estado_alerta", "==", "pendiente")
            # Fallback: count by streaming
            count = 0
            for _ in ref.stream():
                count += 1
            return count
        except Exception:
            return 0

    def mark_alert_reviewed(self, alert_id: str) -> bool:
        """Mark an alert as reviewed."""
        if not self._initialized:
            return False
        try:
            self.db.collection("alertas").document(alert_id).update({
                "estado_alerta": "revisada",
                "fecha_revision": _SERVER_TIMESTAMP,
            })
            return True
        except Exception as e:
            print(f"Error marking alert reviewed: {e}")
            return False

    def mark_alerta_revisada(self, alert_id: str) -> bool:
        """Alias en español — misma operación que mark_alert_reviewed."""
        return self.mark_alert_reviewed(alert_id)

    def mark_alert_pending(self, alert_id: str) -> bool:
        """Revert alert to pending state."""
        if not self._initialized:
            return False
        try:
            self.db.collection("alertas").document(alert_id).update({
                "estado_alerta": "pendiente",
            })
            return True
        except Exception as e:
            print(f"Error reverting alert to pending: {e}")
            return False

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert document."""
        if not self._initialized or not alert_id:
            return False
        try:
            self.db.collection("alertas").document(alert_id).delete()
            return True
        except Exception as e:
            print(f"Error deleting alert: {e}")
            return False

    def pull_visit_data(self, campaign_id: str = "cartera_activa") -> dict:
        """
        Read all gestor visit data from Firebase for reverse-sync to SQLite.

        Optimized: reads client subcollections in parallel.

        Returns:
            dict keyed by seccion: {
                "A": [
                    {
                        "codigo_cliente": "...",
                        "estado_gestion": "visitado_habido",
                        "fecha_gestion": "...",
                        "nota_gestor": "...",
                        "gps_latitud": ...,
                        "gps_longitud": ...,
                        "gps_timestamp": "...",
                    },
                    ...
                ],
            }
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        campaign_ref = self.db.collection("campañas").document(campaign_id)

        def _read_section_visits(gestor_doc):
            sec_id = gestor_doc.id
            visits = []
            for cdoc in (campaign_ref.collection("gestores")
                         .document(sec_id)
                         .collection("clientes")
                         .stream()):
                c = cdoc.to_dict()
                estado = c.get("estado_gestion", "pendiente")
                has_contact_update = bool(c.get("fecha_actualizacion_contacto_iso"))
                uv = c.get("ubicacion_verificada") if isinstance(c.get("ubicacion_verificada"), dict) else {}
                has_verified_location = bool(float(uv.get("lat", 0) or 0))
                if (
                    (estado and estado != "pendiente")
                    or has_contact_update
                    or has_verified_location
                    or estado == "devolucion_pendiente"
                ):
                    gps = c.get("gps_gestor", {}) if isinstance(c.get("gps_gestor"), dict) else {}
                    historial_contacto = []
                    try:
                        hist_ref = (
                            campaign_ref.collection("gestores")
                            .document(sec_id)
                            .collection("clientes")
                            .document(cdoc.id)
                            .collection("historial_contacto")
                            .limit(50)
                        )
                        for hdoc in hist_ref.stream():
                            hd = hdoc.to_dict() or {}
                            hd["event_id"] = hdoc.id
                            historial_contacto.append(hd)
                    except Exception:
                        historial_contacto = []
                    historial_visitas = []
                    try:
                        vis_ref = (
                            campaign_ref.collection("gestores")
                            .document(sec_id)
                            .collection("clientes")
                            .document(cdoc.id)
                            .collection("historial_visitas")
                            .limit(100)
                        )
                        for vdoc in vis_ref.stream():
                            vd = vdoc.to_dict() or {}
                            vd["event_id"] = vdoc.id
                            historial_visitas.append(vd)
                    except Exception:
                        historial_visitas = []
                    etiquetas_raw = c.get("etiquetas")
                    if isinstance(etiquetas_raw, list):
                        etiquetas = [str(x) for x in etiquetas_raw if x]
                    else:
                        etiquetas = []
                    visits.append({
                        "codigo_cliente": cdoc.id,
                        "estado_gestion": estado,
                        "fecha_gestion": c.get("fecha_gestion", ""),
                        "nota_gestor": c.get("nota_gestor", ""),
                        "gps_latitud": gps.get("latitude", gps.get("lat", c.get("gps_latitud", 0))),
                        "gps_longitud": gps.get("longitude", gps.get("lng", c.get("gps_longitud", 0))),
                        "gps_timestamp": gps.get("timestamp", c.get("gps_timestamp", "")),
                        # Nivel fields
                        "nivel_1": c.get("nivel_1", ""),
                        "nivel_2": c.get("nivel_2", ""),
                        "nivel_3": c.get("nivel_3", ""),
                        "nivel_4": c.get("nivel_4", ""),
                        "canal_gestion": c.get("canal_gestion", ""),
                        "fecha_promesa_pago": c.get("fecha_promesa_pago", ""),
                        "monto_promesa_pago": c.get("monto_promesa_pago", 0),
                        # Contact updates
                        "direccion": c.get("direccion", ""),
                        "telefono_movil": c.get("telefono_movil", ""),
                        "ultima_nota_contacto": c.get("ultima_nota_contacto", ""),
                        "fecha_actualizacion_contacto_iso": c.get("fecha_actualizacion_contacto_iso", ""),
                        "actualizado_por_uid": c.get("actualizado_por_uid", ""),
                        "actualizado_por_nombre": c.get("actualizado_por_nombre", ""),
                        "actualizado_por_email": c.get("actualizado_por_email", ""),
                        "origen_actualizacion": c.get("origen_actualizacion", ""),
                        "ubicacion_verificada": uv,
                        "historial_contacto": historial_contacto,
                        "historial_visitas": historial_visitas,
                        "etiquetas": etiquetas,
                        "historial_zona": c.get("historial_zona") or [],
                        "motivo_devolucion": c.get("motivo_devolucion", ""),
                        "nota_devolucion": c.get("nota_devolucion", ""),
                        "fecha_devolucion_solicitud": c.get("devolucion_solicitada_at", ""),
                        "gestor_devolucion_uid": c.get("devolucion_gestor_uid", ""),
                        "gestor_devolucion_nombre": c.get("devolucion_gestor_nombre", ""),
                        "gestor_devolucion_seccion": c.get("devolucion_gestor_seccion", ""),
                        "seccion_key": sec_id,
                        "region": c.get("region", ""),
                        "zona": c.get("zona", ""),
                        "seccion": c.get("seccion", ""),
                    })
            return sec_id, visits

        result = {}
        try:
            gestores_list = list(campaign_ref.collection("gestores").stream())
            workers = min(len(gestores_list), 10) or 1
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_read_section_visits, gd) for gd in gestores_list]
                for fut in as_completed(futures):
                    sec_id, visits = fut.result()
                    if visits:
                        result[sec_id] = visits
        except Exception as e:
            print(f"Error pulling visit data: {e}")

        return result

    def upload_cartera_filtered(
        self,
        by_seccion: dict,
        campaign_id: str = "cartera_activa",
        tramo_info: dict | None = None,
        progress_callback=None,
    ) -> dict:
        """
        Upload cartera from SQLite data (filtered by section if requested).
        Includes tramo information in the upload.

        Args:
            by_seccion: Dict of seccion → list of client dicts (includes DNI).
            campaign_id: Firestore campaign document ID.
            tramo_info: Optional dict with campaign-level tramo metadata.
            progress_callback: Optional callback(current, total, message).

        Returns:
            Upload statistics dict.
        """
        # Delegate to existing upload method which handles visit preservation
        result = self.upload_cartera(
            by_seccion, campaign_id, progress_callback
        )

        # Optionally store tramo metadata at campaign level
        if tramo_info and self._initialized:
            try:
                campaign_ref = self.db.collection("campañas").document(campaign_id)
                campaign_ref.update({
                    "tramo_info": tramo_info,
                    "dia_campana": tramo_info.get("dia_actual", 0),
                    "por_etapa": tramo_info.get("por_etapa", {}),
                    "por_estado_ciclo": tramo_info.get("por_estado_ciclo", {}),
                    "fecha_sync": _SERVER_TIMESTAMP,
                })
            except Exception as e:
                result.setdefault("errors", []).append(
                    f"Error updating tramo info: {e}"
                )

        return result

    def upload_cartera_sections(
        self,
        by_seccion: dict,
        campaign_id: str = "cartera_activa",
        section_keys: set[str] | list[str] | None = None,
        tramo_info: dict | None = None,
        progress_callback=None,
    ) -> dict:
        """
        Upload only the given section keys (e.g. ``_CALL_{uid}`` after call reparto).
        """
        keys = set(section_keys or [])
        filtered = (
            {k: v for k, v in by_seccion.items() if k in keys}
            if keys
            else by_seccion
        )
        if not filtered:
            return {"uploaded": 0, "preserved": 0, "errors": [], "sections": 0}
        return self.upload_cartera_filtered(
            filtered,
            campaign_id=campaign_id,
            tramo_info=tramo_info,
            progress_callback=progress_callback,
        )

    # ── Campaign Configuration Sync ──────────────────────────────

    def sync_campaign_config(self, config_data: dict) -> bool:
        """Write campaign config to ``configuracion/campana`` in Firestore.

        This lets the gestor-app and flutter-app read dynamic tramo
        boundaries, carta schedule, and thresholds without a redeploy.

        Args:
            config_data: Dict from ``ConfigCampana.to_dict()``.

        Returns:
            True on success.
        """
        if not self._initialized:
            return False
        try:
            ref = self.db.collection("configuracion").document("campana")
            ref.set({
                **config_data,
                "fecha_sync": _SERVER_TIMESTAMP,
            })
            return True
        except Exception as e:
            print(f"Error syncing campaign config: {e}")
            return False

    # ── Zone Editing (Admin-only) ────────────────────────────────

    def update_client_zone(
        self,
        campaign_id: str,
        current_seccion_key: str,
        client_id: str,
        new_seccion_key: str,
        admin_email: str,
        admin_name: str = "",
        motivo: str = "edicion_manual",
        reset_gestion: bool = False,
        extra_fields: dict | None = None,
    ) -> dict:
        """
        Move a client from one zone/section to another.

        This performs a cross-document move: reads the client from the
        old section, writes it to the new section, and deletes the old doc.
        A ``historial_zona`` entry is appended for audit trail.

        Only admin/supervisor should call this (enforced by Firestore rules).

        Args:
            campaign_id: e.g. "cartera_activa"
            current_seccion_key: Composite key where the client currently lives
            client_id: The client's document ID (codigo_cliente)
            new_seccion_key: Composite key for the destination section
            admin_email: Email of the admin making the change
            admin_name: Name of the admin making the change

        Returns:
            dict with success status and details
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        if current_seccion_key == new_seccion_key:
            return {"success": False, "error": "La sección origen y destino son iguales."}

        campaign_ref = self.db.collection("campañas").document(campaign_id)

        try:
            # 1. Read client from current section
            old_ref = (
                campaign_ref.collection("gestores")
                .document(current_seccion_key)
                .collection("clientes")
                .document(str(client_id))
            )
            old_doc = old_ref.get()
            if not old_doc.exists:
                return {"success": False, "error": f"Cliente {client_id} no encontrado en sección {current_seccion_key}."}

            client_data = old_doc.to_dict()

            # 2. Parse new section components
            parts = new_seccion_key.split("_")
            new_region = parts[0] if len(parts) >= 1 else ""
            new_zona = parts[1] if len(parts) >= 2 else ""
            new_seccion_letter = parts[2] if len(parts) >= 3 else new_seccion_key

            # 3. Build zone change log entry
            now = datetime.now().isoformat()
            historial_entry = {
                "seccion_anterior": current_seccion_key,
                "seccion_nueva": new_seccion_key,
                "fecha": now,
                "admin_email": admin_email,
                "admin_name": admin_name,
                "motivo": motivo,
            }

            # Append to existing historial or create new
            historial = client_data.get("historial_zona", [])
            if not isinstance(historial, list):
                historial = []
            historial.append(historial_entry)

            # 4. Update client data with new section info
            client_data["seccion"] = new_seccion_letter
            client_data["seccion_key"] = new_seccion_key
            client_data["region"] = new_region
            client_data["zona"] = new_zona
            client_data["historial_zona"] = historial

            if extra_fields:
                client_data.update(extra_fields)

            if reset_gestion:
                client_data["estado_gestion"] = "pendiente"
                client_data["nota_gestor"] = ""
                client_data["fecha_gestion"] = ""
                client_data["nivel_1"] = ""
                client_data["nivel_2"] = ""
                client_data["nivel_3"] = ""
                client_data["nivel_4"] = ""
                client_data["canal_gestion"] = ""
                client_data["fecha_promesa_pago"] = ""
                client_data["monto_promesa_pago"] = 0
                for key in (
                    "motivo_devolucion", "nota_devolucion", "devolucion_solicitada_at",
                    "devolucion_gestor_uid", "devolucion_gestor_nombre",
                    "devolucion_gestor_seccion", "devolucion_gps_lat", "devolucion_gps_lng",
                ):
                    client_data.pop(key, None)

            # 5. Verify destination section exists (create if needed)
            new_gestor_ref = campaign_ref.collection("gestores").document(new_seccion_key)
            new_gestor_doc = new_gestor_ref.get()
            if not new_gestor_doc.exists:
                new_gestor_ref.set({
                    "seccion_key": new_seccion_key,
                    "seccion": new_seccion_letter,
                    "region": new_region,
                    "zona": new_zona,
                    "num_clientes": 0,
                    "deuda_asignada_total": 0,
                    "deuda_pendiente_total": 0,
                    "fecha_asignacion": _SERVER_TIMESTAMP,
                    "estado": "pendiente",
                })

            # 6. Write to new section and delete from old (transactional)
            new_client_ref = new_gestor_ref.collection("clientes").document(str(client_id))

            batch = self.db.batch()
            batch.set(new_client_ref, client_data)
            batch.delete(old_ref)
            batch.commit()

            # 7. Update client counts on both sections
            self._update_section_client_count(campaign_ref, current_seccion_key)
            self._update_section_client_count(campaign_ref, new_seccion_key)

            return {
                "success": True,
                "client_id": client_id,
                "client_name": client_data.get("nombre_completo", ""),
                "from_section": current_seccion_key,
                "to_section": new_seccion_key,
                "historial_entry": historial_entry,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_pending_returns(self, campaign_id: str = "cartera_activa") -> list:
        """List clients with estado_gestion=devolucion_pendiente across all sections."""
        if not self._initialized:
            return []
        results = self._list_pending_returns_query(campaign_id)
        if results is not None:
            return results
        return self._list_pending_returns_scan(campaign_id)

    def _list_pending_returns_query(self, campaign_id: str) -> list | None:
        """Fast path via collection group query; None → use scan fallback."""
        results: list = []
        campaign_marker = f"/campañas/{campaign_id}/gestores/"
        try:
            for cdoc in (
                self.db.collection_group("clientes")
                .where("estado_gestion", "==", "devolucion_pendiente")
                .stream()
            ):
                path = cdoc.reference.path.replace("\\", "/")
                if campaign_marker not in path:
                    continue
                parts = path.split("/")
                try:
                    gi = parts.index("gestores")
                    sec_id = parts[gi + 1]
                except (ValueError, IndexError):
                    continue
                if sec_id == POOL_REASIGNACION_SECTION:
                    continue
                data = cdoc.to_dict() or {}
                results.append({
                    **data,
                    "codigo_cliente": data.get("codigo_cliente") or cdoc.id,
                    "client_id": cdoc.id,
                    "seccion_key": sec_id,
                    "campaign_id": campaign_id,
                })
            results.sort(
                key=lambda r: str(
                    r.get("devolucion_solicitada_at") or r.get("fecha_gestion") or ""
                ),
                reverse=True,
            )
            return results
        except Exception as e:
            err = str(e).lower()
            if "index" in err or "failed precondition" in err:
                print(f"Pending returns: collection group index missing, using scan: {e}")
                return None
            print(f"Error listing pending returns (query): {e}")
            return []

    def _list_pending_returns_scan(self, campaign_id: str) -> list:
        """Fallback: scan gestores subcollections (slow on large carteras)."""
        results = []
        try:
            campaign_ref = self.db.collection("campañas").document(campaign_id)
            for gestor_doc in campaign_ref.collection("gestores").stream():
                sec_id = gestor_doc.id
                if sec_id == POOL_REASIGNACION_SECTION:
                    continue
                for cdoc in gestor_doc.reference.collection("clientes").stream():
                    data = cdoc.to_dict() or {}
                    if data.get("estado_gestion") != "devolucion_pendiente":
                        continue
                    results.append({
                        **data,
                        "codigo_cliente": data.get("codigo_cliente") or cdoc.id,
                        "client_id": cdoc.id,
                        "seccion_key": sec_id,
                        "campaign_id": campaign_id,
                    })
            results.sort(
                key=lambda r: str(
                    r.get("devolucion_solicitada_at") or r.get("fecha_gestion") or ""
                ),
                reverse=True,
            )
        except Exception as e:
            print(f"Error listing pending returns (scan): {e}")
        return results

    def list_pool_clients(self, campaign_id: str = "cartera_activa") -> list:
        """Clients in the reassignment pool section."""
        if not self._initialized:
            return []
        results = []
        try:
            pool_ref = (
                self.db.collection("campañas").document(campaign_id)
                .collection("gestores").document(POOL_REASIGNACION_SECTION)
                .collection("clientes")
            )
            for cdoc in pool_ref.stream():
                data = cdoc.to_dict() or {}
                results.append({
                    **data,
                    "codigo_cliente": data.get("codigo_cliente") or cdoc.id,
                    "client_id": cdoc.id,
                    "seccion_key": POOL_REASIGNACION_SECTION,
                    "campaign_id": campaign_id,
                })
        except Exception as e:
            print(f"Error listing pool clients: {e}")
        return results

    def move_client_to_pool(
        self,
        campaign_id: str,
        current_seccion_key: str,
        client_id: str,
        admin_email: str,
        admin_name: str = "",
    ) -> dict:
        """Move a pending-return client into the reassignment pool."""
        return self.update_client_zone(
            campaign_id=campaign_id,
            current_seccion_key=current_seccion_key,
            client_id=client_id,
            new_seccion_key=POOL_REASIGNACION_SECTION,
            admin_email=admin_email,
            admin_name=admin_name,
            motivo="zona_inaccesible_pool",
            reset_gestion=False,
        )

    def reassign_returned_client(
        self,
        campaign_id: str,
        current_seccion_key: str,
        client_id: str,
        new_seccion_key: str,
        admin_email: str,
        admin_name: str = "",
        notify: bool = True,
    ) -> dict:
        """Reassign a returned/pooled client to a gestor section as pendiente."""
        if new_seccion_key == POOL_REASIGNACION_SECTION:
            return {"success": False, "error": "Seleccione una sección de gestor válida."}
        result = self.update_client_zone(
            campaign_id=campaign_id,
            current_seccion_key=current_seccion_key,
            client_id=client_id,
            new_seccion_key=new_seccion_key,
            admin_email=admin_email,
            admin_name=admin_name,
            motivo="zona_inaccesible",
            reset_gestion=True,
        )
        if result.get("success") and notify:
            self.notify_gestor_client_reassigned(
                campaign_id=campaign_id,
                seccion_key=new_seccion_key,
                client_id=str(client_id),
                client_name=str(result.get("client_name") or client_id),
            )
        return result

    def reject_return_request(
        self,
        campaign_id: str,
        seccion_key: str,
        client_id: str,
        admin_email: str,
        admin_name: str = "",
        rejection_note: str = "",
    ) -> dict:
        """Reject a return request — client stays with original gestor as pendiente."""
        if not self._initialized:
            return {"success": False, "error": "Firebase no está inicializado."}
        try:
            ref = (
                self.db.collection("campañas").document(campaign_id)
                .collection("gestores").document(seccion_key)
                .collection("clientes").document(str(client_id))
            )
            doc = ref.get()
            if not doc.exists:
                return {"success": False, "error": "Cliente no encontrado."}
            data = doc.to_dict() or {}
            gestor_uid = str(data.get("devolucion_gestor_uid") or "")
            update = {
                "estado_gestion": "pendiente",
                "nota_gestor": rejection_note or "Devolución rechazada por central.",
                "devolucion_rechazada_at": datetime.now().isoformat(),
                "devolucion_rechazada_por": admin_email,
            }
            for key in (
                "motivo_devolucion", "nota_devolucion", "devolucion_solicitada_at",
                "devolucion_gestor_uid", "devolucion_gestor_nombre",
                "devolucion_gestor_seccion", "devolucion_gps_lat", "devolucion_gps_lng",
            ):
                update[key] = firestore.DELETE_FIELD
            ref.update(update)
            if gestor_uid:
                self.db.collection("notificaciones").add({
                    "tipo": "devolucion_rechazada",
                    "destinatario_uid": gestor_uid,
                    "seccion_key": seccion_key,
                    "titulo": "Devolución rechazada",
                    "mensaje": (
                        f"Su solicitud de devolución para el cliente {client_id} "
                        f"fue rechazada. Debe continuar la gestión."
                    ),
                    "detalles": {"cliente_id": str(client_id), "nota": rejection_note},
                    "leida": False,
                    "fecha": _SERVER_TIMESTAMP,
                    "campaign_id": campaign_id,
                })
            return {"success": True, "client_id": client_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def notify_gestor_client_reassigned(
        self,
        campaign_id: str,
        seccion_key: str,
        client_id: str,
        client_name: str = "",
    ) -> bool:
        """Notify the destination gestor about a reassigned client."""
        if not self._initialized:
            return False
        destinatario = ""
        try:
            for udoc in self.db.collection("usuarios").stream():
                udata = udoc.to_dict() or {}
                if not udata.get("activo", True):
                    continue
                if seccion_key in (udata.get("secciones") or []):
                    destinatario = udoc.id
                    break
            if not destinatario:
                return False
            self.db.collection("notificaciones").add({
                "tipo": "cliente_reasignado",
                "destinatario_uid": destinatario,
                "seccion_key": seccion_key,
                "titulo": "Nuevo cliente reasignado",
                "mensaje": (
                    f"Se le asignó el cliente {client_name or client_id} "
                    f"por reasignación (zona inaccesible previa)."
                ),
                "detalles": {"cliente_id": str(client_id), "cliente_nombre": client_name},
                "leida": False,
                "fecha": _SERVER_TIMESTAMP,
                "campaign_id": campaign_id,
            })
            return True
        except Exception as e:
            print(f"Error notifying gestor reassignment: {e}")
            return False

    def notify_call_repartition(
        self,
        *,
        campaign_id: str = "cartera_activa",
        motivo: str,
        tipo: str,
        by_gestor: dict[str, dict],
    ) -> dict:
        """
        Notify call-center gestores after a portfolio reparto.

        ``by_gestor`` maps gestor uid →
        ``{nombre, nuevas_cuentas, monto_nuevo, detalles: [{codigo, nombre, importe, razon}]}``
        """
        if not self._initialized:
            return {"sent": 0, "errors": ["Firebase no inicializado"]}

        sent = 0
        errors: list[str] = []
        for uid, info in by_gestor.items():
            if not uid:
                continue
            nuevas = int(info.get("nuevas_cuentas") or 0)
            if nuevas <= 0 and not info.get("detalles"):
                continue
            nombre = info.get("nombre") or uid
            monto = float(info.get("monto_nuevo") or 0)
            mensaje = (
                f"{motivo}. Se le asignaron {nuevas} cuenta(s) "
                f"por un total de S/ {monto:,.2f}."
            )
            detalles_raw = info.get("detalles") or []
            detalle_rows = [
                {
                    "tipo": "nuevo",
                    "codigo_cliente": str(c.get("codigo") or c.get("codigo_cliente") or ""),
                    "nombre": str(c.get("nombre") or c.get("nombre_completo") or ""),
                    "mensaje": str(c.get("razon") or c.get("mensaje") or ""),
                }
                for c in detalles_raw[:50]
            ]
            try:
                self.db.collection("notificaciones").add({
                    "tipo": "reparto_call",
                    "destinatario_uid": uid,
                    "titulo": "Nueva cartera call center",
                    "mensaje": mensaje,
                    "detalles": detalle_rows,
                    "leida": False,
                    "fecha": _SERVER_TIMESTAMP,
                    "campaign_id": campaign_id,
                })
                sent += 1
            except Exception as e:
                errors.append(f"{nombre}: {e}")
        return {"sent": sent, "errors": errors}

    def _update_section_client_count(self, campaign_ref, seccion_key: str):
        """Recount clients in a section and update the gestor doc."""
        try:
            clients_ref = (
                campaign_ref.collection("gestores")
                .document(seccion_key)
                .collection("clientes")
            )
            count = 0
            deuda_total = 0.0
            deuda_pendiente = 0.0
            for cdoc in clients_ref.stream():
                c = cdoc.to_dict()
                count += 1
                deuda_total += float(c.get("importe_deuda_asignada", 0) or 0)
                deuda_pendiente += float(c.get("importe_deuda_pendiente", 0) or 0)

            campaign_ref.collection("gestores").document(seccion_key).update({
                "num_clientes": count,
                "deuda_asignada_total": round(deuda_total, 2),
                "deuda_pendiente_total": round(deuda_pendiente, 2),
            })
        except Exception:
            pass  # Non-critical

    def get_client_detail(
        self, campaign_id: str, seccion_key: str, client_id: str
    ) -> dict | None:
        """Read a single client document from Firestore."""
        if not self._initialized:
            return None
        try:
            doc = (
                self.db.collection("campañas")
                .document(campaign_id)
                .collection("gestores")
                .document(seccion_key)
                .collection("clientes")
                .document(str(client_id))
                .get()
            )
            if doc.exists:
                data = doc.to_dict()
                data["_id"] = doc.id
                data["seccion_key"] = seccion_key
                return data
            return None
        except Exception:
            return None

    # ── GPS Tracking ─────────────────────────────────────────────

    def get_tracking_summary(self) -> list:
        """
        Get latest position summary for all gestors.
        Returns list of dicts from ubicaciones_gestores collection.
        """
        if not self._initialized:
            return []
        try:
            docs = self.db.collection("ubicaciones_gestores").stream()
            result = []
            for doc in docs:
                data = doc.to_dict()
                data["uid"] = doc.id
                result.append(data)
            return result
        except Exception as e:
            print(f"Error getting tracking summary: {e}")
            return []

    def get_tracking_points(self, gestor_uid: str, limit: int = 200,
                            fecha_inicio: str | None = None) -> list:
        """
        Get tracking trail points for a specific gestor.

        Args:
            gestor_uid: The gestor's Firebase UID.
            limit: Max points to retrieve.
            fecha_inicio: Optional ISO date string to filter from.

        Returns:
            List of point dicts sorted by timestamp.
        """
        if not self._initialized:
            return []
        try:
            ref = (self.db.collection("ubicaciones_gestores")
                   .document(gestor_uid)
                   .collection("puntos"))

            query = ref.order_by("timestamp", direction=BaseQuery.DESCENDING)

            if fecha_inicio:
                # Filter points from this date onwards
                from datetime import datetime as dt
                try:
                    start_dt = dt.fromisoformat(fecha_inicio)
                    query = ref.where("fecha", ">=", fecha_inicio).order_by("fecha", direction=BaseQuery.DESCENDING)
                except ValueError:
                    pass

            query = query.limit(limit)
            docs = query.stream()
            points = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                # Convert Firestore Timestamp
                if "timestamp" in data and data["timestamp"]:
                    try:
                        data["timestamp_str"] = data["timestamp"].strftime(
                            "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        data["timestamp_str"] = str(data.get("fecha", ""))
                else:
                    data["timestamp_str"] = str(data.get("fecha", ""))
                points.append(data)

            points.reverse()  # Oldest first
            return points
        except Exception as e:
            print(f"Error getting tracking points for {gestor_uid}: {e}")
            return []

    # ── Cartera Update & Notifications ──────────────────────────

    def read_current_cartera(
        self, campaign_id: str = "cartera_activa"
    ) -> dict[str, dict[str, dict]]:
        """
        Read ALL current client data from Firestore for diff comparison.

        Returns:
            Dict of seccion_key → { codigo_cliente → client_data_dict }
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        campaign_ref = self.db.collection("campañas").document(campaign_id)

        def _read_section(gestor_doc):
            sec_id = gestor_doc.id
            clients = {}
            for cdoc in (campaign_ref.collection("gestores")
                         .document(sec_id)
                         .collection("clientes")
                         .stream()):
                clients[cdoc.id] = cdoc.to_dict()
            return sec_id, clients

        result = {}
        try:
            gestores_list = list(campaign_ref.collection("gestores").stream())
            workers = min(len(gestores_list), 10) or 1
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_read_section, gd) for gd in gestores_list]
                for fut in as_completed(futures):
                    sec_id, clients = fut.result()
                    if clients:
                        result[sec_id] = clients
        except Exception as e:
            print(f"Error reading current cartera: {e}")

        return result

    @staticmethod
    def _cartera_lifecycle_fields(
        *,
        activo: bool,
        motivo_baja: str = "",
        ultimo_excel: str = "",
    ) -> dict:
        fields = {
            "activo_en_cartera": activo,
            "motivo_baja": motivo_baja if not activo else "",
        }
        if not activo:
            fields["fecha_baja"] = _SERVER_TIMESTAMP
        if ultimo_excel:
            fields["ultimo_excel"] = ultimo_excel
        return fields

    def upload_cartera_update(
        self,
        by_seccion: dict,
        change_report,
        campaign_id: str = "cartera_activa",
        progress_callback=None,
        *,
        excel_by_seccion: dict | None = None,
        ultimo_excel: str = "",
        tramo_info: dict | None = None,
    ) -> dict:
        """
        Upload updated cartera to Firestore, only writing changed documents.
        Preserves gestor visit data for existing clients.

        Args:
            by_seccion: Dict of seccion_key → list of client dicts (SQLite payload).
            change_report: ChangeReport from diff_engine.
            campaign_id: Firestore campaign ID.
            progress_callback: Optional callback(current, total, message).
            excel_by_seccion: Parsed Excel by section for accurate section totals.
            ultimo_excel: Source filename for archive metadata.

        Returns:
            dict with upload statistics.
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        excel_by_seccion = excel_by_seccion or by_seccion
        total_to_write = (
            change_report.total_new
            + change_report.total_updated
            + change_report.total_removed
        )
        written = 0
        preserved = 0
        archived = 0
        errors = []

        try:
            campaign_ref = self.db.collection("campañas").document(campaign_id)

            for seccion_key, section_changes in change_report.sections.items():
                if not section_changes.has_changes:
                    continue

                # Read existing visit data to preserve
                existing_visits = self._read_existing_visit_data(
                    campaign_ref, seccion_key
                )

                gestor_ref = campaign_ref.collection("gestores").document(seccion_key)

                # Index new data for this section
                new_clients_list = by_seccion.get(seccion_key, [])
                new_clients_map = {
                    c.get("codigo_cliente", ""): c for c in new_clients_list
                }

                batch = self.db.batch()
                batch_count = 0

                def _commit_batch_if_needed():
                    nonlocal batch, batch_count
                    if batch_count >= 400:
                        batch.commit()
                        batch = self.db.batch()
                        batch_count = 0

                # Write NEW clients
                for client_data in section_changes.new_clients:
                    client_id = client_data.get("codigo_cliente", "")
                    if not client_id:
                        continue
                    client_ref = gestor_ref.collection("clientes").document(str(client_id))
                    full = dict(new_clients_map.get(client_id) or client_data)
                    contactos_seed = full.pop("contactos_seed", None) or []
                    doc = {
                        **full,
                        "estado_gestion": full.get("estado_gestion", "pendiente"),
                        "fecha_subida": _SERVER_TIMESTAMP,
                        "seccion_key": seccion_key,
                        **self._cartera_lifecycle_fields(activo=True, ultimo_excel=ultimo_excel),
                    }
                    alt_sections = self._sections_for_visit_lookup(seccion_key, full)
                    prev = self._read_visit_for_client_cross_sections(
                        campaign_ref, str(client_id), alt_sections,
                    )
                    if prev:
                        doc.update(prev)
                        preserved += 1
                    batch.set(client_ref, doc)
                    batch_count += 1
                    batch_count += self._seed_contactos_to_batch(batch, client_ref, contactos_seed)
                    written += 1
                    _commit_batch_if_needed()

                    if progress_callback:
                        progress_callback(
                            written, total_to_write,
                            f"Nuevo: {full.get('nombre_completo', '')}"
                        )

                # Write UPDATED clients (preserve visit data)
                for client_change in section_changes.updated_clients:
                    code = client_change.codigo_cliente
                    new_data_raw = new_clients_map.get(code)
                    if not new_data_raw:
                        continue
                    client_ref = gestor_ref.collection("clientes").document(str(code))
                    new_data = dict(new_data_raw)
                    contactos_seed = new_data.pop("contactos_seed", None) or []
                    doc = {
                        **new_data,
                        "estado_gestion": new_data.get("estado_gestion", "pendiente"),
                        "fecha_subida": _SERVER_TIMESTAMP,
                        "seccion_key": seccion_key,
                        **self._cartera_lifecycle_fields(activo=True, ultimo_excel=ultimo_excel),
                    }

                    alt_sections = self._sections_for_visit_lookup(seccion_key, new_data)
                    prev = self._read_visit_for_client_cross_sections(
                        campaign_ref, str(code), alt_sections,
                    )
                    if not prev:
                        prev = existing_visits.get(str(code))
                    if prev:
                        doc.update(prev)
                        preserved += 1

                    batch.set(client_ref, doc)
                    batch_count += 1
                    batch_count += self._seed_contactos_to_batch(batch, client_ref, contactos_seed)
                    written += 1
                    _commit_batch_if_needed()

                    if progress_callback:
                        progress_callback(
                            written, total_to_write,
                            f"Actualizado: {new_data.get('nombre_completo', '')}"
                        )

                # Archive REMOVED clients (absent from new Excel)
                for removed_data in section_changes.removed_clients:
                    code = str(removed_data.get("codigo_cliente", "")).strip()
                    if not code:
                        continue
                    client_ref = gestor_ref.collection("clientes").document(code)
                    doc = {
                        **removed_data,
                        "seccion_key": seccion_key,
                        **self._cartera_lifecycle_fields(
                            activo=False,
                            motivo_baja=MOTIVO_BAJA_EXCEL_BANCO,
                            ultimo_excel=ultimo_excel,
                        ),
                    }
                    prev = existing_visits.get(code)
                    if prev:
                        doc.update(prev)
                        preserved += 1
                    batch.set(client_ref, doc, merge=True)
                    batch_count += 1
                    written += 1
                    archived += 1
                    _commit_batch_if_needed()

                    if progress_callback:
                        progress_callback(
                            written, total_to_write,
                            f"Archivado: {removed_data.get('nombre_completo', code)}"
                        )

                if batch_count > 0:
                    batch.commit()

                # Section totals from Excel (active cartera only)
                all_clients = excel_by_seccion.get(seccion_key, [])
                deuda_total = sum(
                    float(c.get("importe_deuda_asignada", 0) or 0)
                    for c in all_clients
                )
                deuda_pendiente = sum(
                    float(c.get("importe_deuda_pendiente", 0) or 0)
                    for c in all_clients
                )
                clientes_con_coordenadas = sum(
                    1 for c in all_clients
                    if float(c.get("coordenada_y", 0) or 0) != 0
                    and float(c.get("coordenada_x", 0) or 0) != 0
                )
                sample = all_clients[0] if all_clients else {}
                gestor_ref.set({
                    "seccion_key": seccion_key,
                    "seccion": sample.get("seccion", ""),
                    "region": sample.get("region", ""),
                    "zona": sample.get("zona", ""),
                    "num_clientes": len(all_clients),
                    "clientes_con_coordenadas": clientes_con_coordenadas,
                    "deuda_asignada_total": round(deuda_total, 2),
                    "deuda_pendiente_total": round(deuda_pendiente, 2),
                    "fecha_actualizacion": _SERVER_TIMESTAMP,
                    "estado": "pendiente",
                }, merge=True)

            # Campaign-level metadata from Excel sections
            total_clients = sum(len(v) for v in excel_by_seccion.values())
            total_clientes_con_coordenadas = sum(
                sum(
                    1 for c in clients
                    if float(c.get("coordenada_y", 0) or 0) != 0
                    and float(c.get("coordenada_x", 0) or 0) != 0
                )
                for clients in excel_by_seccion.values()
            )
            campaign_update = {
                "total_clientes": total_clients,
                "total_secciones": len(excel_by_seccion),
                "secciones": list(excel_by_seccion.keys()),
                "total_clientes_con_coordenadas": total_clientes_con_coordenadas,
                "fecha_actualizacion": _SERVER_TIMESTAMP,
            }
            if tramo_info:
                campaign_update["tramo_info"] = tramo_info
                campaign_update["dia_campana"] = tramo_info.get("dia_actual", 0)
                campaign_update["por_etapa"] = tramo_info.get("por_etapa", {})
                campaign_update["por_estado_ciclo"] = tramo_info.get(
                    "por_estado_ciclo", {}
                )
            campaign_ref.set(campaign_update, merge=True)

        except Exception as e:
            errors.append(str(e))

        return {
            "campaign_id": campaign_id,
            "total_written": written,
            "total_expected": total_to_write,
            "preserved_visits": preserved,
            "archived_clients": archived,
            "errors": errors,
            "success": len(errors) == 0,
        }

    def create_admin_alert(
        self,
        *,
        tipo: str,
        titulo: str,
        mensaje: str,
        seccion: str = "",
        campaign_id: str = "cartera_activa",
    ) -> bool:
        """Create an operational alert for admin/supervisor inbox."""
        if not self._initialized:
            return False
        try:
            self.db.collection("alertas").add({
                "tipo": tipo,
                "campaña_id": campaign_id,
                "seccion": seccion,
                "cliente_id": "",
                "cliente_nombre": titulo,
                "cliente_dni": "",
                "nota": mensaje,
                "estado_alerta": "pendiente",
                "fecha": _SERVER_TIMESTAMP,
            })
            return True
        except Exception as e:
            print(f"Error creating admin alert: {e}")
            return False

    # ── Admin inbox (notificaciones back-office) ─────────────────

    ADMIN_NOTIFICATION_TIPOS = ("base_actualizada_admin", "campana_cargada_admin")
    MAX_ADMIN_DETALLES = 500

    @staticmethod
    def _build_section_client_detalles(section, seccion_key: str = "") -> list[dict]:
        """Build per-client detail entries for a section change set."""
        detalles: list[dict] = []
        sk_field = {"seccion_key": seccion_key} if seccion_key else {}

        for c in section.new_clients:
            detalles.append({
                "tipo": "nuevo",
                "codigo_cliente": c.get("codigo_cliente", ""),
                "nombre": c.get("nombre_completo", ""),
                "mensaje": (
                    f"Nuevo cliente asignado "
                    f"(deuda: S/ {float(c.get('importe_deuda_asignada', 0) or 0):,.2f})"
                ),
                **sk_field,
            })

        for cc in section.updated_clients:
            cambios_texto = []
            for fc in cc.important_changes:
                cambios_texto.append(f"{fc.label}: {fc.format_values()}")
            if not cambios_texto:
                cambios_texto = [f"{len(cc.changes)} campo(s) actualizado(s)"]
            detalles.append({
                "tipo": "actualizado",
                "codigo_cliente": cc.codigo_cliente,
                "nombre": cc.nombre_completo,
                "mensaje": "; ".join(cambios_texto),
                **sk_field,
            })

        for c in section.removed_clients:
            detalles.append({
                "tipo": "removido",
                "codigo_cliente": c.get("codigo_cliente", ""),
                "nombre": c.get("nombre_completo", ""),
                "mensaje": "Ya no está en cartera activa (ausente en Excel del banco)",
                **sk_field,
            })

        return detalles

    @classmethod
    def change_report_to_admin_payload(
        cls,
        change_report,
        *,
        max_detalles: int | None = None,
    ) -> tuple[dict, list[dict]]:
        """Serialize a ChangeReport into resumen + detalles for admin notifications."""
        limit = max_detalles if max_detalles is not None else cls.MAX_ADMIN_DETALLES
        all_detalles: list[dict] = []
        for seccion_key, section in change_report.sections.items():
            if not section.has_changes:
                continue
            all_detalles.extend(
                cls._build_section_client_detalles(section, seccion_key)
            )

        total_entries = len(all_detalles)
        truncated = total_entries > limit
        if truncated:
            all_detalles = all_detalles[:limit]

        resumen = {
            "total_new": change_report.total_new,
            "total_updated": change_report.total_updated,
            "total_removed": change_report.total_removed,
            "total_unchanged": change_report.total_unchanged,
            "secciones_afectadas": len(change_report.affected_sections),
            "truncated": truncated,
            "detalles_omitidos": max(0, total_entries - limit) if truncated else 0,
        }
        return resumen, all_detalles

    def _get_admin_supervisor_uids(self) -> list[str]:
        """Return UIDs of active admin and supervisor users."""
        if not self._initialized:
            return []
        uids: list[str] = []
        try:
            for udoc in self.db.collection("usuarios").stream():
                udata = udoc.to_dict() or {}
                if not udata.get("activo", True):
                    continue
                if udata.get("rol") in ("admin", "supervisor"):
                    uids.append(udoc.id)
        except Exception as e:
            print(f"Error reading admin users for notifications: {e}")
        return uids

    def send_admin_base_update_notification(
        self,
        change_report,
        *,
        campaign_id: str = "cartera_activa",
        archivo: str = "",
        created_by: dict | None = None,
        firestore_was_empty: bool = False,
    ) -> int:
        """
        Create consolidated admin notifications after a successful base update.
        One document per admin/supervisor user.
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        admin_uids = self._get_admin_supervisor_uids()
        if not admin_uids:
            return 0

        resumen, detalles = self.change_report_to_admin_payload(change_report)
        n_sec = resumen["secciones_afectadas"]
        mensaje = (
            f"{resumen['total_new']} nuevos, {resumen['total_updated']} actualizados, "
            f"{resumen['total_removed']} removidos en {n_sec} sección(es)"
        )
        if resumen["truncated"]:
            mensaje += f" (… y {resumen['detalles_omitidos']} cambios más en detalle)"
        if resumen["total_removed"] > 0:
            mensaje += (
                ". Los clientes removidos se archivaron (ya no aparecen "
                "en cartera activa del gestor)"
            )
        if firestore_was_empty:
            mensaje += ". Nota: no había cartera previa en Firebase; todo aparece como nuevo"

        created_by = created_by or {}
        payload_base = {
            "tipo": "base_actualizada_admin",
            "titulo": "Base actualizada",
            "mensaje": mensaje,
            "archivo": archivo,
            "campaign_id": campaign_id,
            "resumen": resumen,
            "detalles": detalles,
            "leida": False,
            "fecha": _SERVER_TIMESTAMP,
            "created_by_uid": created_by.get("uid", ""),
            "created_by_nombre": created_by.get("nombre", ""),
        }

        count = 0
        for uid in admin_uids:
            try:
                self.db.collection("notificaciones").add({
                    **payload_base,
                    "destinatario_uid": uid,
                })
                count += 1
            except Exception as e:
                print(f"Error creating admin update notification for {uid}: {e}")
        return count

    def send_admin_campaign_loaded_notification(
        self,
        summary: dict,
        *,
        by_seccion: dict,
        campaign_id: str = "cartera_activa",
        campana_local_id: str = "",
        archivo: str = "",
        created_by: dict | None = None,
    ) -> int:
        """
        Notify admin/supervisor users when a new campaign is loaded from Excel.
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        admin_uids = self._get_admin_supervisor_uids()
        if not admin_uids:
            return 0

        total_clientes = int(summary.get("total_clientes", 0))
        total_secciones = int(summary.get("total_secciones", 0))
        deuda = float(summary.get("deuda_total_asignada", 0) or 0)

        detalles = []
        for seccion_key, clients in sorted(by_seccion.items()):
            n = len(clients) if clients else 0
            deuda_sec = sum(
                float(c.get("importe_deuda_asignada", 0) or 0) for c in (clients or [])
            )
            detalles.append({
                "tipo": "seccion",
                "seccion_key": seccion_key,
                "mensaje": f"{n} cliente(s), deuda S/ {deuda_sec:,.2f}",
                "cantidad": n,
            })

        mensaje = (
            f"Campaña cargada: {total_clientes} clientes en {total_secciones} "
            f"sección(es), deuda total S/ {deuda:,.2f}"
        )
        created_by = created_by or {}
        payload_base = {
            "tipo": "campana_cargada_admin",
            "titulo": "Campaña cargada",
            "mensaje": mensaje,
            "archivo": archivo,
            "campaign_id": campaign_id,
            "campana_local_id": campana_local_id,
            "resumen": {
                "total_clientes": total_clientes,
                "total_secciones": total_secciones,
                "deuda_total_asignada": deuda,
            },
            "detalles": detalles,
            "leida": False,
            "fecha": _SERVER_TIMESTAMP,
            "created_by_uid": created_by.get("uid", ""),
            "created_by_nombre": created_by.get("nombre", ""),
        }

        count = 0
        for uid in admin_uids:
            try:
                self.db.collection("notificaciones").add({
                    **payload_base,
                    "destinatario_uid": uid,
                })
                count += 1
            except Exception as e:
                print(f"Error creating campaign loaded notification for {uid}: {e}")
        return count

    def list_admin_notifications(
        self,
        uid: str,
        limit: int = 50,
    ) -> list[dict]:
        """List admin inbox notifications for the given user, newest first."""
        if not self._initialized or not uid:
            return []

        merged: list[dict] = []
        per_tipo = max(limit, 25)
        for tipo in self.ADMIN_NOTIFICATION_TIPOS:
            try:
                docs = (
                    self.db.collection("notificaciones")
                    .where("destinatario_uid", "==", uid)
                    .where("tipo", "==", tipo)
                    .order_by("fecha", direction=BaseQuery.DESCENDING)
                    .limit(per_tipo)
                    .stream()
                )
                for doc in docs:
                    data = doc.to_dict() or {}
                    data["id"] = doc.id
                    merged.append(data)
            except Exception as e:
                print(f"Error listing admin notifications ({tipo}): {e}")

        def _fecha_key(item: dict) -> datetime:
            f = item.get("fecha")
            if f is None:
                return datetime.min
            if hasattr(f, "timestamp"):
                return datetime.fromtimestamp(f.timestamp())
            return datetime.min

        merged.sort(key=_fecha_key, reverse=True)
        return merged[:limit]

    def count_unread_admin_notifications(self, uid: str) -> int:
        """Count unread admin notifications for badge display."""
        if not self._initialized or not uid:
            return 0
        total = 0
        for tipo in self.ADMIN_NOTIFICATION_TIPOS:
            try:
                docs = (
                    self.db.collection("notificaciones")
                    .where("destinatario_uid", "==", uid)
                    .where("tipo", "==", tipo)
                    .where("leida", "==", False)
                    .stream()
                )
                total += sum(1 for _ in docs)
            except Exception as e:
                print(f"Error counting unread admin notifications ({tipo}): {e}")
        return total

    def mark_notification_read(self, notif_id: str) -> bool:
        """Mark a notification document as read."""
        if not self._initialized or not notif_id:
            return False
        try:
            self.db.collection("notificaciones").document(notif_id).update(
                {"leida": True}
            )
            return True
        except Exception as e:
            print(f"Error marking notification read: {e}")
            return False

    def send_update_notifications(
        self,
        change_report,
        campaign_id: str = "cartera_activa",
    ) -> dict:
        """
        Create notification documents in the 'notificaciones' collection,
        one per affected section, targeted at the gestor who owns that section.

        Args:
            change_report: ChangeReport from diff_engine.
            campaign_id: Campaign ID for context.

        Returns:
            dict with notifications_sent, sections_without_gestor, warnings.
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        count = 0
        sections_without_gestor: list[str] = []
        warnings: list[str] = []

        seccion_to_uid = {}
        try:
            users_docs = self.db.collection("usuarios").stream()
            for udoc in users_docs:
                udata = udoc.to_dict()
                if not udata.get("activo", True):
                    continue
                secciones = udata.get("secciones", [])
                for sk in secciones:
                    seccion_to_uid[str(sk)] = udoc.id
        except Exception as e:
            print(f"Error reading users for notifications: {e}")

        for seccion_key, section in change_report.sections.items():
            if not section.has_changes:
                continue

            destinatario = seccion_to_uid.get(seccion_key, "")
            if not destinatario:
                sections_without_gestor.append(seccion_key)
                warnings.append(
                    f"Sección {seccion_key}: sin gestor asignado; "
                    f"no se envió notificación al campo."
                )
                self.create_admin_alert(
                    tipo="seccion_sin_gestor",
                    titulo=f"Sección sin gestor: {seccion_key}",
                    mensaje=(
                        "Hay cambios de cartera en esta sección pero ningún "
                        "usuario activo tiene esa sección en su perfil. "
                        "Asigne un gestor en Equipo antes de la próxima actualización."
                    ),
                    seccion=seccion_key,
                    campaign_id=campaign_id,
                )
                continue

            detalles = self._build_section_client_detalles(section)
            mensaje = section.summary_text
            if section.removed_clients:
                mensaje = (
                    f"{len(section.removed_clients)} cliente(s) ya no están en el "
                    f"Excel del banco. {mensaje}"
                )

            try:
                self.db.collection("notificaciones").add({
                    "tipo": "base_actualizada",
                    "seccion_key": seccion_key,
                    "destinatario_uid": destinatario,
                    "titulo": "Base de datos actualizada",
                    "mensaje": mensaje,
                    "detalles": detalles,
                    "leida": False,
                    "fecha": _SERVER_TIMESTAMP,
                    "campaign_id": campaign_id,
                })
                count += 1
            except Exception as e:
                print(f"Error creating notification for {seccion_key}: {e}")
                warnings.append(f"Error notificación {seccion_key}: {e}")

        return {
            "notifications_sent": count,
            "sections_without_gestor": sections_without_gestor,
            "warnings": warnings,
        }

    def notify_letters_published(
        self,
        *,
        campaign_id: str,
        distribution: dict,
        numero_carta: int | None = None,
        published_cards: list[int] | None = None,
        tramo: int | None = None,
        total_letters: int = 0,
    ) -> dict:
        """
        Create notification documents in ``notificaciones`` for gestores affected
        by a letter publication batch.
        """
        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        by_gestor = distribution.get("by_gestor") or {}
        if not by_gestor:
            return {"sent": 0, "errors": []}

        summary = distribution.get("summary") or {}
        cartas = sorted(
            {
                int(c)
                for c in (published_cards or summary.get("cartas") or [])
                if c is not None
            }
        )
        if numero_carta is not None and numero_carta not in cartas:
            cartas.append(int(numero_carta))
            cartas.sort()
        tramos = sorted(
            {
                int(t)
                for t in (summary.get("tramos") or [])
                if t not in (None, 0)
            }
        )
        if tramo is not None and tramo not in tramos:
            tramos.append(int(tramo))
            tramos.sort()

        total_clientes = int(summary.get("total_clientes", 0))
        total_cartas = int(summary.get("total_cartas", 0) or total_letters or 0)
        if total_letters > 0:
            total_cartas = int(total_letters)

        if len(cartas) == 1:
            mensaje = (
                f"Se publicaron {total_cartas} carta(s) JPG de la carta {cartas[0]} "
                f"para {total_clientes} cliente(s). Revise la APK para descargar e imprimir."
            )
        else:
            cartas_txt = ", ".join(str(c) for c in cartas) if cartas else "pendientes"
            mensaje = (
                f"Se publicaron {total_cartas} carta(s) JPG pendientes "
                f"({cartas_txt}) para {total_clientes} cliente(s). "
                "Revise la APK para descargar e imprimir."
            )

        payload_base = {
            "tipo": "cartas_publicadas",
            "campaign_id": campaign_id,
            "numero_carta": int(numero_carta) if numero_carta is not None else None,
            "cartas": cartas,
            "tramo": int(tramo) if tramo is not None else None,
            "tramos": tramos,
            "cantidad": total_cartas,
            "total_clientes": total_clientes,
            "titulo": "Cartas publicadas",
            "mensaje": mensaje,
            "leida": False,
            "fecha": _SERVER_TIMESTAMP,
        }

        sent = 0
        errors: list[str] = []
        for gestor_uid in by_gestor.keys():
            try:
                self.db.collection("notificaciones").add({
                    **payload_base,
                    "destinatario_uid": gestor_uid,
                })
                sent += 1
            except Exception as e:
                errors.append(f"{gestor_uid}: {e}")

        return {"sent": sent, "errors": errors}

    @staticmethod
    def haversine_km(lat1, lng1, lat2, lng2):
        """Calculate distance in km between two lat/lng points."""
        import math
        R = 6371.0
        dLat = math.radians(lat2 - lat1)
        dLng = math.radians(lng2 - lng1)
        a = (math.sin(dLat / 2) ** 2 +
             math.cos(math.radians(lat1)) *
             math.cos(math.radians(lat2)) *
             math.sin(dLng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # ── Catálogo de Niveles (Gestión) ────────────────────────────

    def upload_catalogo_niveles(self, catalogo: dict) -> bool:
        """Upload the Niveles 1-4 catalog to Firestore.

        Structure in Firestore:
            configuracion/catalogo_niveles → { version, pais, canales, niveles[] }

        Args:
            catalogo: Full catalog dict (from catalogo_niveles_PE.json).

        Returns:
            True on success.
        """
        if not self._initialized:
            return False
        try:
            ref = self.db.collection("configuracion").document("catalogo_niveles")
            ref.set({
                **catalogo,
                "fecha_sync": _SERVER_TIMESTAMP,
            })
            return True
        except Exception as e:
            print(f"Error uploading catalogo niveles: {e}")
            return False

    def get_catalogo_niveles(self) -> dict | None:
        """Read the Niveles catalog from Firestore."""
        if not self._initialized:
            return None
        try:
            ref = self.db.collection("configuracion").document("catalogo_niveles")
            doc = ref.get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            print(f"Error reading catalogo niveles: {e}")
            return None

    def upload_catalogo_etiquetas(self, catalogo: dict) -> bool:
        """Upload the etiquetas catalog to Firestore configuracion/etiquetas."""
        if not self._initialized:
            return False
        try:
            ref = self.db.collection("configuracion").document("etiquetas")
            ref.set({
                **catalogo,
                "fecha_sync": _SERVER_TIMESTAMP,
            })
            return True
        except Exception as e:
            print(f"Error uploading catalogo etiquetas: {e}")
            return False

    def get_catalogo_etiquetas(self) -> dict | None:
        """Read the etiquetas catalog from Firestore."""
        if not self._initialized:
            return None
        try:
            ref = self.db.collection("configuracion").document("etiquetas")
            doc = ref.get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            print(f"Error reading catalogo etiquetas: {e}")
            return None

    def update_client_etiquetas_firestore(
        self,
        campaign_id: str,
        seccion_key: str,
        codigo_cliente: str,
        etiquetas: list[str],
    ) -> bool:
        """Push etiquetas update for a single client to Firestore."""
        if not self._initialized:
            return False
        try:
            ref = (
                self.db.collection("campañas").document(campaign_id)
                .collection("gestores").document(seccion_key)
                .collection("clientes").document(codigo_cliente)
            )
            ref.update({"etiquetas": etiquetas})
            return True
        except Exception as e:
            print(f"Error updating client etiquetas: {e}")
            return False

    # ── Full Cartera Download (for new PC / full sync) ───────────

    def download_full_cartera(
        self,
        campaign_id: str = "cartera_activa",
        progress_callback=None,
    ) -> dict:
        """Download the entire cartera from Firestore, including visit data.

        This is used to restore a local SQLite database on a new PC
        or after data loss.

        Returns:
            {
                "metadata": { campaign-level fields },
                "by_seccion": {
                    "01_1211_H": [
                        { ...all client fields including visits, niveles, promesa... },
                    ],
                },
                "total_clients": int,
            }
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not self._initialized:
            raise RuntimeError("Firebase no está inicializado.")

        campaign_ref = self.db.collection("campañas").document(campaign_id)

        # Read campaign metadata
        camp_doc = campaign_ref.get()
        if not camp_doc.exists:
            raise ValueError(f"No se encontró la campaña '{campaign_id}' en Firebase.")
        metadata = camp_doc.to_dict()

        # Read all sections + clients in parallel
        gestores_list = list(campaign_ref.collection("gestores").stream())

        def _read_section_full(gestor_doc):
            sec_id = gestor_doc.id
            clients = []
            for cdoc in (campaign_ref.collection("gestores")
                         .document(sec_id)
                         .collection("clientes")
                         .stream()):
                c = cdoc.to_dict()
                c["_doc_id"] = cdoc.id
                # Normalise GPS: gestor-app writes gps_gestor object,
                # flutter-app writes flat fields. Merge into flat format.
                gps_obj = c.pop("gps_gestor", None)
                if isinstance(gps_obj, dict):
                    if not c.get("gps_latitud"):
                        c["gps_latitud"] = gps_obj.get("latitude", gps_obj.get("lat", 0))
                    if not c.get("gps_longitud"):
                        c["gps_longitud"] = gps_obj.get("longitude", gps_obj.get("lng", 0))
                    if not c.get("gps_timestamp"):
                        c["gps_timestamp"] = str(gps_obj.get("timestamp", ""))
                clients.append(c)
            return sec_id, clients

        by_seccion = {}
        total = 0
        workers = min(len(gestores_list), 10) or 1

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_read_section_full, gd): gd for gd in gestores_list}
            for i, fut in enumerate(as_completed(futures)):
                sec_id, clients = fut.result()
                by_seccion[sec_id] = clients
                total += len(clients)
                if progress_callback:
                    progress_callback(
                        i + 1, len(gestores_list),
                        f"Sección {sec_id}: {len(clients)} clientes"
                    )

        return {
            "metadata": metadata,
            "by_seccion": by_seccion,
            "total_clients": total,
        }


# Singleton instance
firebase_service = FirebaseService()
