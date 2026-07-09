# 20 — Configuración del Sistema (SettingsPage)

## Descripción

Página de configuración accesible solo para `admin`. Permite ajustar los parámetros del motor de tramos, umbrales monetarios y datos de la empresa.

---

## Secciones de configuración

### 1. Parámetros de campaña (ConfigCampana)

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| Duración campaña | 60 días | Días totales del ciclo |
| Tramo 1: Inicio | Día 1 | |
| Tramo 1: Fin | Día 8 | |
| Tramo 2: Inicio | Día 9 | |
| Tramo 2: Fin | Día 43 | |
| Tramo 3: Inicio | Día 44 | |
| Tramo 3: Fin | Día 60 | |

### 2. Calendario de cartas

| Carta | Default | |
|-------|---------|--|
| Carta 1 (E1-1) | Día 1 | |
| Carta 2 (E1-2) | Día 9 | |
| Carta 3 (E2-1) | Día 11 | |
| Carta 4 (E2-2) | Día 35 | |
| Carta 5 (E3-1) | Día 44 | |

### 3. Umbrales monetarios

| Umbral | Default | Descripción |
|--------|---------|-------------|
| Mínimo gestión | S/ 10.00 | Saldo mínimo para incluir en cobranza activa |
| Umbral carta física | S/ 40.00 | Saldo mínimo para cartas 2-5 |
| Alto valor | S/ 500.00 | Marcador de cliente de alto valor |

### 4. Datos de la empresa

| Campo | Default |
|-------|---------|
| Nombre proveedor | "PERECAUDOL" |
| Nombre empresa | |
| Teléfono empresa | |
| Dirección empresa | |
| Logo (ruta archivo) | |

### 5. Firebase / Credenciales

| Campo | Descripción |
|-------|-------------|
| Service Account Key | Ruta al JSON de credenciales Firebase Admin |
| Verificar conexión | Botón para probar la conexión |

### 6. Base de datos

| Opción | Descripción |
|--------|-------------|
| Ruta SQLite | Dónde se guarda `antcobranzas.db` |
| Hacer backup | Exportar copia de la BD |
| Restaurar backup | Importar BD desde backup |

---

## Firebase Config (hardcodeada, no editable por usuario)

```typescript
export const FIREBASE_CONFIG = {
  apiKey: "AIzaSyBubpxyyN2YvcPaU6WUJkrF2IQUOzFVYWg",
  authDomain: "clase-001.firebaseapp.com",
  projectId: "clase-001",
  storageBucket: "clase-001.firebasestorage.app",
  messagingSenderId: "445584901998",
  appId: "1:445584901998:web:5c3087ceb65418619ee37f",
  measurementId: "G-LV7V8QBRKM"
}
```

El `SERVICE_ACCOUNT_KEY_PATH` sí es configurable (el archivo JSON de Admin SDK).

---

## Persistencia de settings

Los settings se guardan en:
1. **ConfigCampana** en SQLite (parámetros de tramos/cartas/umbrales)
2. **electron-store** o `app.getPath('userData')/settings.json` para settings de app (rutas, empresa)
3. Las credenciales Firebase se referencian por ruta, el archivo JSON no se modifica

---

## Página DatabasePage (visualizar datos locales)

Sub-página de Settings para inspeccionar la BD local:
- Lista de campañas en SQLite
- Conteo de clientes por campaña
- Tamaño de la BD
- Botón para limpiar campañas antiguas (>90 días cerradas)
