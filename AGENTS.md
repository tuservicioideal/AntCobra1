# AntCobranzas — Guía para agentes de código

Monorepo de cobranzas bancarias (ciclo ~60 días, 3 tramos, gestores de campo). **App canónica:** `admin-app` (Python). Ver [NOTA-FOCO-PROYECTO.md](NOTA-FOCO-PROYECTO.md).

**Datos:** el DNI (`numero_documento`) se guarda en SQLite y se publica en Firestore para gestores call/campo (`include_sensitive=True` en upload).

## Apps y puntos de entrada

| App | Stack | Entrada principal |
|-----|-------|-------------------|
| `admin-app/` | CustomTkinter, SQLAlchemy, Firebase Admin | `admin-app/ui/app.py` |
| `flutter-app/` | Flutter (APK + **Web en Hosting**) | `flutter-app/lib/main.dart` |
| `gestor-app/` | React 19 (legado, sin deploy) | `gestor-app/src/App.jsx` |
| Raíz | Firebase `clase-001` | `firestore.rules`, `firebase.json` |

`electron-app/` es legado — no modificar salvo petición explícita.

## Spec funcional

Documentación modular: [electron-app-docs/00_INDICE.md](electron-app-docs/00_INDICE.md) (Excel, tramos, sync, cartas, export, GPS, reglas Firestore).

## Skills del proyecto (`.cursor/skills/`)

| Skill | Uso |
|-------|-----|
| `firebase-expert` | Firestore, reglas, Auth, deploy, Admin SDK, Flutter Firebase |
| `antcobranzas-admin-app` | Cambios en back-office Python |
| `antcobranzas-sync` | Sincronización visitas Firestore ↔ SQLite |
| `antcobranzas-tramos-cartas` | Tramos, cartas Word/PDF, export Excel banco |
| `pyinstaller-customtkinter` | Build EXE con PyInstaller |
| `premium-frontend-ui` | UI premium en `gestor-app` (no CustomTkinter) |
| `shadcn` | Solo invocación manual (`/shadcn`) |

Skills por app (auto-scope al directorio):

| Ruta | Skill |
|------|-------|
| `flutter-app/.cursor/skills/flutter-field-gestor` | Gestores: APK + Flutter Web (Hosting) |
| `gestor-app/.cursor/skills/gestor-pwa` | Legado React (referencia; ver [HOSTING-DEPLOY.md](HOSTING-DEPLOY.md)) |

## Reglas Cursor (`.cursor/rules/`)

- `admin-app-python-only.mdc` — prioriza `admin-app`
- `flutter-apk-build.mdc` — recompilar APK tras cambios en Flutter
- `skill-activation-router.mdc` — enrutamiento obligatorio a skills

## Plugin Firebase (global)

Fallback si no aplica `firebase-expert`: `firebase-basics`, `firebase-firestore-standard`, `firebase-auth-basics`, `firebase-hosting-basics`.

## Skills legacy

Las carpetas en `.github/skills/` están deprecadas; usar `.cursor/skills/`.
