# 13 — Módulo Estadísticas (StatsPage)

## Descripción

Visualización de KPIs y gráficos de la campaña activa. En **admin-app** los datos vienen de SQLite; en **Flutter APK** (roles admin/supervisor/asistente) y **gestor-app PWA** desde Firestore.

---

## KPIs principales

| KPI | Descripción |
|-----|-------------|
| Total clientes | Clientes en campaña activa |
| Deuda total asignada | Suma `importe_deuda_asignada` |
| Deuda total pendiente | Suma `importe_deuda_pendiente` |
| Recuperación banco | `asignada − pendiente` (datos Excel del banco) |
| Recuperación % banco | `recuperado_banco / asignada × 100` |
| Deuda gestionada | Suma asignada donde `estado_gestion != pendiente` |
| Promesas de pago | Clientes con `fecha_promesa_pago` o `monto_promesa_pago` |
| Monto comprometido | Suma `monto_promesa_pago` |
| Ganancia estimada jefe | `recuperado_banco × (porcentaje_comision_jefe / 100)` |
| Proyección lineal | `recuperado × (duracion_dias / dias_transcurridos)`, tope = deuda asignada |
| Proyección promesas | `recuperado_banco + monto_prometido`, tope = deuda asignada |
| Visitados hoy | Gestiones del día actual |
| Cobertura GPS | Clientes con coordenadas o `ubicacion_verificada` |

---

## Configuración: comisión del responsable

- Campo SQLite / Firestore: `porcentaje_comision_jefe` (0–100, default 15).
- Editado en **admin-app → Configuración → Comisión del responsable**.
- Sincronizado a `configuracion/campana` en Firestore para lectura en APK/PWA.

---

## Flutter APK — panel ejecutivo (admin)

Pestañas:

1. **Resumen** — gauges (avance, recuperación banco, GPS), KPIs, progreso, dona por estado, embudo.
2. **Finanzas** — recuperación mixta, ganancia jefe, proyecciones dual, cobertura de deuda, tramos.
3. **Equipo** — Top 10 gestores por recuperación banco (atribución `actualizado_por_uid` o sección).
4. **Territorio** — tabla por sección, top departamentos (cuentas y deuda), top distritos.

Gestores de campo: resumen en Perfil + «Mis estadísticas» (sin comisión jefe ni ranking global).

---

## Gráficos

### Distribución por estado de gestión (Pie chart)
- pendiente
- visitado_habido
- visitado_no_habido
- fallecido_inubicable
- suplantacion
- pago_no_registrado

### Distribución por tramo (Bar chart)
- Tramo 1 / Tramo 2 / Tramo 3 / Sin tramo

### Avance por sección (Bar horizontal)
- Eje Y: secciones
- Eje X: % visitados

### Evolución diaria (Line chart — si hay historial)
- Días vs clientes gestionados acumulados

---

## Tabla de deudas

Tabla de clientes filtrable con:
- Código cliente
- Nombre
- Sección
- Estado gestión
- Tramo
- Deuda asignada
- Deuda pendiente
- Nivel 1-4
- Fecha promesa / Monto promesa

Ordenable por columna. Paginada (50 filas por página).

---

## Filtros disponibles

- Por sección
- Por estado de gestión
- Por tramo
- Por canal (CAM/TEL)
- Por rango de deuda
- Búsqueda por nombre/código

---

## Librería de gráficos sugerida

**Recharts** (React, gestor-app) / **fl_chart** (Flutter APK) / CustomTkinter (admin desktop)
