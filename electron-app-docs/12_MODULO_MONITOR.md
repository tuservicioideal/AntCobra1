# 12 — Módulo Monitor (MonitorPage)

## Descripción

Vista en tiempo real del estado de visitas de los gestores. Se actualiza automáticamente cada 30 segundos leyendo desde Firestore.

---

## Información mostrada

### KPIs globales (strip superior)
- Total clientes en campaña
- Visitados (habido + no habido)
- Pendientes
- % de avance

### Tabla de gestores
Por cada gestor/sección:

| Sección | Gestor | Total | Visitados | Pendientes | Progreso |
|---------|--------|-------|-----------|-----------|---------|
| H | Juan Pérez | 45 | 32 | 13 | 71% |
| C | María Ríos | 38 | 20 | 18 | 53% |

### Detalle por sección (expandible)
Al hacer clic en una sección, muestra la lista de clientes con su estado:
- 🟢 visitado_habido
- 🟡 visitado_no_habido
- ⚪ pendiente
- 🔴 fallecido_inubicable
- 🟠 suplantacion
- 💜 pago_no_registrado

---

## Auto-refresh

- Intervalo: 30 segundos
- Indicador visual de "última actualización"
- Botón "Actualizar ahora"
- Se detiene al navegar fuera de la página (`stop()`)

---

## Fuente de datos

Lee directamente de Firestore en tiempo real (no de SQLite local) para mostrar datos frescos:

```typescript
// Para cada sección de la campaña activa
const snap = await db
  .collection("campañas").doc("cartera_activa")
  .collection("gestores").doc(seccionKey)
  .collection("clientes")
  .get()

const visitados = snap.docs.filter(d =>
  d.data().estado_gestion !== "pendiente"
).length
```

---

## Filtros

- Por sección
- Por estado de gestión
- Por gestor

---

## Implementación con Firebase real-time listener (opción)

Se puede usar `onSnapshot` para actualizaciones en tiempo real sin polling:

```typescript
const unsubscribe = db
  .collection("campañas").doc("cartera_activa")
  .collection("gestores")
  .onSnapshot(snap => {
    // actualizar estado
  })

// Cleanup al desmontar
return () => unsubscribe()
```
