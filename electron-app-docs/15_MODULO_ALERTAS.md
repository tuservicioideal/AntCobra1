# 15 — Módulo Alertas (AlertsPage)

## Descripción

Sistema de alertas para eventos importantes de la campaña y del equipo.

---

## Tipos de alertas

| Tipo | Descripción | Origen |
|------|-------------|--------|
| `tramo_cambio` | Cliente cambió de tramo | Motor de tramos |
| `carta_pendiente` | Carta pendiente de generación | Motor de tramos |
| `visita_sin_gestion` | Gestor con clientes sin visitar pasado X días | Monitor |
| `deuda_alta` | Cliente con deuda > S/ 500 sin gestionar | Sistema |
| `promesa_vencida` | Fecha de promesa de pago pasada sin pago registrado | Sistema |
| `cliente_nuevo` | Cliente nuevo detectado en re-subida | DiffEngine |
| `cliente_eliminado` | Cliente removido en re-subida | DiffEngine |
| `datos_modificados` | Cambios en datos bancarios del cliente | DiffEngine |
| `sync_completado` | Sincronización Firebase completada | SyncService |

---

## Estructura de alerta

```typescript
interface Alert {
  id: string
  tipo: AlertType
  titulo: string
  mensaje: string
  clienteId?: string
  codigoCliente?: string
  seccionKey?: string
  severidad: "info" | "warning" | "error" | "success"
  leida: boolean
  timestamp: Date
}
```

---

## UI de AlertsPage

- Lista de alertas ordenadas por timestamp (más recientes primero)
- Filtros: por tipo, por severidad, leídas/no leídas, por sección
- Marcar como leída / Marcar todas como leídas
- Eliminar alertas antiguas (> 30 días)
- Badge en el sidebar con conteo de no leídas

---

## Colores por severidad

| Severidad | Color |
|-----------|-------|
| info | Azul |
| warning | Amarillo/naranja |
| error | Rojo |
| success | Verde |

---

## Persistencia

Las alertas se guardan en SQLite local (tabla `alertas`).
Acciones del DiffEngine generan alertas automáticamente al re-subir cartera.
