# 02 — Arquitectura Electron

## Stack tecnológico propuesto

| Capa | Tecnología |
|------|-----------|
| Shell | **Electron** (Node.js + Chromium) |
| Frontend | **React 18 + TypeScript** |
| Estilos | **Tailwind CSS** (o shadcn/ui) |
| Estado global | **Zustand** (o Redux Toolkit) |
| Base de datos local | **SQLite** via `better-sqlite3` (proceso Main) |
| Firebase | `firebase` SDK v10 (proceso Renderer) + `firebase-admin` en Main para admin SDK |
| Documentos Word | `docx` npm package |
| Excel | `xlsx` (SheetJS) o `exceljs` |
| Routing | **React Router v6** |
| Build | **electron-builder** |

---

## Arquitectura IPC (Main ↔ Renderer)

```
┌─────────────────────────────────────────────────────────┐
│  MAIN PROCESS (Node.js)                                  │
│  ├── sqlite.service.ts    (better-sqlite3)               │
│  ├── firebase-admin.service.ts  (firebase-admin SDK)     │
│  ├── excel-parser.service.ts    (xlsx / exceljs)         │
│  ├── word-generator.service.ts  (docx)                   │
│  ├── excel-exporter.service.ts                           │
│  └── ipc-handlers.ts      (expone API a renderer)        │
│                                                          │
│  RENDERER PROCESS (React)                               │
│  ├── firebase SDK cliente (auth REST / Firestore read)   │
│  ├── páginas / componentes                               │
│  └── llama a Main via window.electronAPI.xxx()           │
└─────────────────────────────────────────────────────────┘
```

### Canales IPC principales

| Canal | Dirección | Descripción |
|-------|-----------|-------------|
| `db:query` | R→M | Ejecutar query SQLite |
| `excel:parse` | R→M | Parsear archivo Excel del banco |
| `excel:export` | R→M | Exportar resultados a Excel |
| `word:generate` | R→M | Generar carta Word |
| `firebase-admin:upload` | R→M | Subir cartera a Firestore (Admin SDK) |
| `firebase-admin:create-user` | R→M | Crear usuario Firebase Auth |
| `firebase-admin:sync-visits` | R→M | Leer visitas de Firestore |
| `app:open-file-dialog` | R→M | Abrir diálogo de archivo |
| `app:get-version` | R→M | Obtener versión del app |

---

## Estructura de carpetas sugerida

```
electron-app/
├── package.json
├── electron.vite.config.ts
├── src/
│   ├── main/                     ← proceso Main (Node.js)
│   │   ├── index.ts              ← punto de entrada
│   │   ├── ipc-handlers.ts       ← registro de todos los handlers
│   │   └── services/
│   │       ├── sqlite.service.ts
│   │       ├── firebase-admin.service.ts
│   │       ├── excel-parser.service.ts
│   │       ├── excel-exporter.service.ts
│   │       ├── word-generator.service.ts
│   │       ├── tramo-engine.service.ts
│   │       └── campaign-manager.service.ts
│   ├── preload/
│   │   └── index.ts              ← contextBridge (expone electronAPI)
│   └── renderer/                 ← proceso Renderer (React)
│       ├── App.tsx
│       ├── main.tsx
│       ├── firebase.ts           ← init Firebase SDK cliente
│       ├── config.ts             ← constantes
│       ├── store/                ← Zustand stores
│       │   ├── auth.store.ts
│       │   ├── campaign.store.ts
│       │   └── ui.store.ts
│       ├── services/             ← wrappers IPC del renderer
│       │   ├── db.service.ts
│       │   ├── firebase.service.ts
│       │   └── auth.service.ts
│       ├── pages/
│       │   ├── LoginPage.tsx
│       │   ├── DashboardPage.tsx
│       │   ├── CampaignPage.tsx
│       │   ├── MonitorPage.tsx
│       │   ├── StatsPage.tsx
│       │   ├── TeamPage.tsx
│       │   ├── DocumentsPage.tsx
│       │   ├── ExportPage.tsx
│       │   ├── SyncPage.tsx
│       │   ├── AlertsPage.tsx
│       │   ├── TrackingPage.tsx
│       │   └── SettingsPage.tsx
│       └── components/
│           ├── Sidebar.tsx
│           ├── KPICard.tsx
│           ├── SectionHeader.tsx
│           ├── StatusBadge.tsx
│           └── ...
└── resources/
    └── templates/                ← plantillas Word base
```

---

## Seguridad

- `contextIsolation: true` siempre
- `nodeIntegration: false` en renderer
- Todo acceso a FS/DB/Admin SDK pasa por IPC handlers en Main
- Credenciales Firebase Admin SDK solo en proceso Main, nunca expuestas al renderer
- DNI en SQLite y Firestore (apps gestor); el admin desktop puede enmascararlo en pantalla si aplica
