"""
Authentication Service for Desktop Admin App.

Uses the Firebase Auth REST API to authenticate users with email/password,
since firebase-admin SDK is server-side and does not support signIn.
After authentication, reads the user profile from Firestore to determine
the role and access level.

Firebase Auth REST endpoint:
  POST https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}
"""

import requests
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import FIREBASE_CONFIG

# API key from the Firebase project configuration
_API_KEY = FIREBASE_CONFIG.get("apiKey", "")


class AuthResult:
    """Result of an authentication attempt."""

    def __init__(self, success: bool, uid: str = "", email: str = "",
                 nombre: str = "", rol: str = "", seccion: str = "",
                 telefono: str = "", zona: str = "", region: str = "",
                 activo: bool = True, error: str = ""):
        self.success = success
        self.uid = uid
        self.email = email
        self.nombre = nombre
        self.rol = rol
        self.seccion = seccion
        self.telefono = telefono
        self.zona = zona
        self.region = region
        self.activo = activo
        self.error = error

    # Role helpers (same as Flutter/Web)
    @property
    def can_manage_users(self) -> bool:
        return self.rol in ("admin", "supervisor")

    @property
    def can_view_stats(self) -> bool:
        return self.rol in ("admin", "supervisor", "asistente")

    @property
    def can_upload(self) -> bool:
        return self.rol in ("admin", "supervisor")

    @property
    def can_generate_letters(self) -> bool:
        return self.rol in ("admin", "supervisor")

    @property
    def display_role(self) -> str:
        return {
            "admin": "Administrador",
            "supervisor": "Supervisor",
            "asistente": "Asistente",
            "gestor": "Gestor",
        }.get(self.rol, self.rol.capitalize() if self.rol else "Sin rol")


class AuthService:
    """
    Handles email/password login via Firebase Auth REST API,
    then reads the user's Firestore profile for role information.
    """

    AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"

    def __init__(self):
        self.current_user: AuthResult | None = None
        self._id_token: str = ""
        self._refresh_token: str = ""

    def sign_in(self, email: str, password: str, firebase_service=None) -> AuthResult:
        """
        Authenticate with Firebase Auth REST API, then load Firestore profile.

        Args:
            email: User email
            password: User password
            firebase_service: Initialized FirebaseService instance for Firestore reads

        Returns:
            AuthResult with success/error info and user profile
        """
        email = email.strip().lower()

        if not _API_KEY:
            return AuthResult(success=False, error="API Key de Firebase no configurada")

        # ── Step 1: Authenticate via REST API ──
        try:
            resp = requests.post(
                f"{self.AUTH_URL}?key={_API_KEY}",
                json={
                    "email": email,
                    "password": password,
                    "returnSecureToken": True,
                },
                timeout=15,
            )
        except requests.exceptions.ConnectionError:
            return AuthResult(success=False, error="Sin conexión a Internet")
        except requests.exceptions.Timeout:
            return AuthResult(success=False, error="Tiempo de espera agotado")
        except Exception as e:
            return AuthResult(success=False, error=f"Error de conexión: {e}")

        data = resp.json()

        if resp.status_code != 200:
            error_msg = data.get("error", {}).get("message", "Error desconocido")
            friendly = {
                "EMAIL_NOT_FOUND": "Correo electrónico no registrado",
                "INVALID_PASSWORD": "Contraseña incorrecta",
                "USER_DISABLED": "Cuenta desactivada por el administrador",
                "INVALID_LOGIN_CREDENTIALS": "Credenciales inválidas",
                "TOO_MANY_ATTEMPTS_TRY_LATER": "Demasiados intentos. Intente más tarde",
                "INVALID_EMAIL": "Formato de correo inválido",
            }.get(error_msg, f"Error de autenticación: {error_msg}")
            return AuthResult(success=False, error=friendly)

        uid = data.get("localId", "")
        self._id_token = data.get("idToken", "")
        self._refresh_token = data.get("refreshToken", "")

        if not uid:
            return AuthResult(success=False, error="No se obtuvo el ID de usuario")

        # ── Step 2: Load user profile from Firestore ──
        profile = self._load_profile(uid, email, firebase_service)

        if profile is None:
            return AuthResult(
                success=False, uid=uid, email=email,
                error="Tu perfil no está configurado. Contacte al administrador."
            )

        if not profile.get("activo", True):
            return AuthResult(
                success=False, uid=uid, email=email,
                error="Cuenta desactivada. Contacte al administrador."
            )

        rol = (profile.get("rol") or "").strip()
        if not rol:
            return AuthResult(
                success=False, uid=uid, email=email,
                error="Tu perfil no tiene rol asignado. Contacte al administrador."
            )

        result = AuthResult(
            success=True,
            uid=uid,
            email=email,
            nombre=profile.get("nombre", email),
            rol=rol,
            seccion=profile.get("seccion", ""),
            telefono=profile.get("telefono", ""),
            zona=profile.get("zona", ""),
            region=profile.get("region", ""),
            activo=profile.get("activo", True),
        )

        self.current_user = result
        return result

    def _load_profile(self, uid: str, email: str, firebase_service) -> dict | None:
        """
        Multi-source profile resolution (same as Flutter/Web):
        1. Try usuarios/{uid} (canonical — always preferred)
        2. Query by email field
        3. Try email-derived doc ID

        Syncs legacy docs to usuarios/{uid} via Admin SDK when found.
        Returns None if no profile exists (never invents rol=gestor).
        """
        if firebase_service is None or not firebase_service.is_initialized():
            return None

        db = firebase_service.db

        def _sync_canonical(data: dict) -> dict:
            payload = {**data, "uid": uid, "email": email}
            if "activo" not in payload:
                payload["activo"] = True
            try:
                db.collection("usuarios").document(uid).set(payload, merge=True)
            except Exception:
                pass
            return payload

        # 1. Try canonical UID doc
        try:
            doc = db.collection("usuarios").document(uid).get()
            if doc.exists:
                data = doc.to_dict() or {}
                if not data.get("uid"):
                    try:
                        db.collection("usuarios").document(uid).update({"uid": uid})
                    except Exception:
                        pass
                    data["uid"] = uid
                return data
        except Exception:
            pass

        # 2. Try query by email
        try:
            query = db.collection("usuarios").where("email", "==", email).limit(1).stream()
            for d in query:
                return _sync_canonical(d.to_dict() or {})
        except Exception:
            pass

        # 3. Try email-derived doc ID
        email_key = email.replace(".", "_").replace("@", "_")
        try:
            doc = db.collection("usuarios").document(email_key).get()
            if doc.exists:
                return _sync_canonical(doc.to_dict() or {})
        except Exception:
            pass

        return None

    def sign_out(self):
        """Clear authentication state."""
        self.current_user = None
        self._id_token = ""
        self._refresh_token = ""

    @property
    def is_signed_in(self) -> bool:
        return self.current_user is not None and self.current_user.success
