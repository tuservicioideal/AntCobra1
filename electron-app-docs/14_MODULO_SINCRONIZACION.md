# 14 — Módulo Sincronización (SyncPage)

## Descripción

Sincroniza los datos de gestión registrados por los gestores en Firebase hacia la base de datos SQLite local.

---

## Flujo de sincronización

```
Firebase Firestore
  campañas/cartera_activa/gestores/{seccion}/clientes/{codigo}
        ↓ (lectura Admin SDK en Main process)
SQLite local
  clientes WHERE codigo_cliente = {codigo}
        ↓ (UPDATE campos de gestión)
```

---

## Campos que se sincronizan (Firebase → SQLite)

```typescript
const SYNC_FIELDS = [
  "estado_gestion",
  "nota_gestor",
  "fecha_gestion",
  "gps_latitud",
  "gps_longitud",
  "gps_timestamp",
  "nivel_1", "nivel_2", "nivel_3", "nivel_4",
  "canal_gestion",
  "fecha_promesa_pago",
  "monto_promesa_pago",
  "ultima_nota_contacto",
  "fecha_actualizacion_contacto_iso",
  "actualizado_por_uid",
  "actualizado_por_nombre",
  "actualizado_por_email",
  "origen_actualizacion"
]
```

---

## Lógica de merge

- Si el cliente ya tiene `fecha_gestion` en SQLite → solo sobreescribir si la de Firebase es más reciente
- La sincronización es **one-way**: Firebase → SQLite (los gestores nunca editan desde el desktop)
- Coincidencia por `codigo_cliente` (doc ID en Firestore = codigo_cliente)

---

## Estadísticas del resultado

```typescript
interface SyncStats {
  seccionesProcessed: number
  clientesProcessed: number
  clientesUpdated: number
  clientesSinCambio: number
  errors: string[]
  duration: number   // ms
  timestamp: Date
}
```

---

## UI de SyncPage

- Botón "Sincronizar Ahora"
- Barra de progreso durante sync
- Log de última sincronización:
  - Timestamp
  - Secciones procesadas
  - Clientes actualizados
  - Errores (si los hay)
- Historial de sincronizaciones (tabla del `sync_log`)
- Auto-sync: opción de sincronizar cada N minutos (configurable)

---

## Diff Engine (detección de cambios en re-subida)

El `DiffEngine` compara la cartera nueva (Excel parseado) contra la existente en Firestore para detectar:

- **Clientes nuevos**: presentes en nuevo Excel, ausentes en Firestore
- **Clientes eliminados**: presentes en Firestore, ausentes en nuevo Excel → se archivan (`activo_en_cartera: false`, `motivo_baja: ausente_en_excel_banco`) y se notifica al gestor; no se borran documentos ni historial de visitas
- **Clientes modificados**: campo a campo, con campos importantes marcados

### Campos comparados (solo datos bancarios)

```typescript
const COMPARE_FIELDS = [
  "nombre_completo", "telefono_movil", "correo", "direccion",
  "coordenada_x", "coordenada_y",
  "importe_deuda_asignada", "importe_deuda_pendiente", "dias_atraso",
  // ... más campos bancarios
]
```

### Campos "importantes" (generan notificación destacada)

```typescript
const IMPORTANT_FIELDS = new Set([
  "importe_deuda_asignada", "importe_deuda_pendiente",
  "dias_atraso", "direccion", "telefono_movil", "nombre_completo"
])
```
