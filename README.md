# AntCobranzas (monorepo)

Sistema de cobranzas: back-office de escritorio, app de gestores en campo y Firebase compartido.

## Back-office oficial: `electron-app`

La operación administrativa migra del EXE Python (`admin-app`) a **AntCobranzas Desktop** (Electron + SQLite + Firebase Admin SDK).

- Desarrollo: ver [electron-app/README.md](./electron-app/README.md)
- **admin-app** queda **deprecado**; no eliminar del repo hasta cerrar el piloto de corte.

### Documentación Fase 3 (corte EXE)

| Documento | Contenido |
|-----------|-----------|
| [electron-app/docs/FIREBASE-CLASE-001.md](./electron-app/docs/FIREBASE-CLASE-001.md) | Checklist consola Firebase, reglas, relación gestor-app |
| [electron-app/docs/UAT-PILOTO.md](./electron-app/docs/UAT-PILOTO.md) | Matriz UAT EXE vs Electron |
| [electron-app/docs/CORTE-EXE.md](./electron-app/docs/CORTE-EXE.md) | Backup, instalación, import BD, rollback |

Proyecto Firebase: **clase-001**. Cuenta consola / CLI: **tuservicioideal.com@gmail.com**. No commitear service account ni `.env`.

## Otras carpetas

| Carpeta | Rol |
|---------|-----|
| `gestor-app/` | PWA gestores (Firebase Hosting) |
| `flutter-app/` | App móvil gestores |
| `admin-app/` | EXE Python legacy (deprecado) |
| `electron-app-docs/` | Especificación funcional por módulos |

## Verificación Firebase Admin (local)

```bash
set FIREBASE_SERVICE_ACCOUNT_PATH=C:\ruta\service-account.json
node scripts/verify-firebase-admin.mjs
```

Requiere `npm install` en `electron-app`.
