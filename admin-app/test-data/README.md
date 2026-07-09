# Datos de prueba — Admin-App AntCobranzas

Excels sintéticos con el **mismo layout de columnas** que el export del banco (`config.EXCEL_COLUMNS` / `excel_parser.py`). Sirven para probar carga de campaña, actualización periódica, tramos, call center, export y sincronización sin depender de archivos reales del banco.

## Regenerar archivos

```powershell
cd admin-app
python test-data/generate_test_excels.py
```

Los `.xlsx` se escriben en `test-data/excels/`.

---

## Análisis resumido del Admin-App

### Módulos y flujos que consumen Excel

| Módulo (menú) | Función principal | Relación con Excel |
|---------------|-------------------|-------------------|
| **Inicio → Campaña** | Cargar cartera, jerarquía región/zona/sección, subir a Firebase | **Entrada:** Excel del banco |
| **Inicio → Actualización del banco** | Diff cartera (nuevos / actualizados / removidos) | **Entrada:** Excel posterior |
| **Base de Datos** | Ficha cliente, filtros, historial | Datos cargados desde Excel |
| **Equipo** | Alta gestores, asignación de secciones | Secciones salen del Excel parseado |
| **Call Center** | Reparto LPT tramo 1 por monto | Clientes con `fecha_asignacion` y saldo ≥ S/ 10 |
| **Documentos** | Cartas Word/PDF por tramo | Umbrales: S/ 10 gestión, S/ 40 carta física |
| **Exportar** | Excel de gestión al banco | **Salida** (no usa estos archivos de entrada) |
| **Sincronización** | Pull visitas Firestore → SQLite | Tras tener campaña cargada |
| **GPS** | Mapa de visitas | Clientes con coordenadas del Excel |

### Clave de sección (asignación gestor)

```
{region}_{zona}_{seccion}   →   ejemplo: 01_1211_H
```

La misma letra (`H`) en otra región/zona es **otra sección** (p. ej. `02_1211_H`).

### Ciclo por cuenta (tramos)

- **59 días** desde `fecha_asignacion` del Excel.
- Tramo 1: días 1–10 · Tramo 2: 11–43 · Tramo 3: 44–59.
- Saldo pendiente **&lt; S/ 10**: excluido de avance de tramo.
- Cartas físicas 2–5: saldo **&gt; S/ 40**.

### Actualización banco (diff)

Compara por `codigo_cliente`:

- **Removidos:** en SQLite/Firestore pero no en el nuevo Excel.
- **Nuevos:** en Excel pero no en cartera activa.
- **Actualizados:** mismos campos bancarios con cambios (deuda, teléfono, dirección, etc.).

Cliente ancla para pruebas: **`CTEST001`**.

---

## Catálogo de Excels

### `01_carga_inicial.xlsx`

**Uso:** Primera carga de campaña + distribución a gestores + smoke de jerarquía territorial.

| Dato | Valor |
|------|--------|
| Clientes | 12 |
| Secciones | `01_1211_H`, `01_1211_A`, `02_1305_C`, `02_1211_H` (4 claves compuestas) |
| Cliente test | `CTEST001` (MARIA LOPEZ) en `01_1211_H` |
| Casos extra | `CLI-A-003` con S/ 8 (bajo umbral tramo); `CLI-H-R2-*` misma letra H, región 02 |

**Pasos sugeridos**

1. Inicio → Campaña → Cargar Excel → este archivo.
2. Revisar resumen (clientes, secciones, deuda).
3. Distribuir a gestores / Subir a Firebase (si Firebase configurado).
4. Equipo: asignar gestores a las secciones listadas.

---

### `02_actualizacion_sin_cliente.xlsx`

**Uso:** Flujo **Actualización del banco** — simula pago o baja de cartera.

Igual que `01` **sin** `CTEST001`. Tras cargar `01` y publicar, aplicar este archivo desde Inicio → Actualización del banco.

**Resultado esperado:** 1 removido (`CTEST001`), resto sin cambios. Ver también `docs/UAT-ACTUALIZACION-EXCEL.md`.

---

### `03_actualizacion_con_cambios.xlsx`

**Uso:** Diff con **actualizaciones** y **alta** de cliente.

| Código | Cambio |
|--------|--------|
| `CTEST002` | Deuda 180 → 95.50, teléfono, dirección, días atraso |
| `CTEST003` | Cliente **nuevo** en `01_1211_H` |

**Secuencia:** cargar `01` → aplicar `03` (no hace falta el `02` si se quiere probar todo en un solo diff).

---

### `04_tramos_umbrales.xlsx`

**Uso:** Tramos, cartas y reparto call center.

| Código | Propósito |
|--------|-----------|
| `TRAMO-SALDO-BAJO` | Pendiente S/ 5 — excluido de tramo |
| `TRAMO-SALDO-MEDIO` | S/ 25 — gestión sí, sin carta física alta |
| `TRAMO-SALDO-ALTO` | S/ 450 — elegible cartas físicas |
| `TRAMO-DIA-01/15/45` | Días 1, 15 y 45 del ciclo (según fecha de hoy) |
| `TRAMO-CALL-01` … `05` | Montos decrecientes para reparto LPT en Call Center |

**Pasos:** cargar campaña → evaluar tramos (Documentos / motor tramos) → Call Center → repartir tramo 1.

---

### `05_minimo_smoke.xlsx`

**Uso:** Prueba rápida (2 clientes, sección `01_1211_X`). Ideal para validar instalación, parser y UI sin esperar cargas grandes.

---

### `06_bordes_parser.xlsx`

**Uso:** Robustez del parser.

- GPS en cero
- Teléfono móvil vacío
- Fila sin `codigo_cliente` (debe ignorarse)
- Importe con formato `1.234,56`

No debe fallar la carga; revisar que solo se importen 3 clientes válidos.

---

## Matriz de pruebas recomendada

| # | Excel(s) | Qué validar |
|---|----------|-------------|
| 1 | `05_minimo_smoke` | Parser + creación campaña |
| 2 | `01_carga_inicial` | Jerarquía, secciones, totales, Firebase |
| 3 | `01` → `02` | Remoción `CTEST001`, notificaciones |
| 4 | `01` → `03` | Cambios campo + cliente nuevo |
| 5 | `04_tramos_umbrales` | Umbrales S/ 10 y S/ 40, días de ciclo |
| 6 | `04` + gestores call | Reparto LPT y balances |
| 7 | `06_bordes_parser` | Filas vacías y formatos raros |
| 8 | Cualquiera + sync | Pull visitas desde APK/gestores |
| 9 | `07_multi_campana_banco` | Filtro por Nº campaña banco (Monitor, Call, Stats) |
| 10 | `08_devoluciones_gestion` | Devoluciones, pool, gestión especial |
| 11 | `09_call_center_volumen` | Reparto LPT con 20 cuentas call |
| 12 | `01` → `10_actualizacion_mixta` | Actualización con cambios parciales + altas |

---

## Excels adicionales (07–10)

### `07_multi_campana_banco.xlsx`

**Uso:** Probar el filtro **Nº campaña banco** cuando hay más de una campaña en la cartera.

| Campaña banco | Clientes | Sección |
|---------------|----------|---------|
| BANCO-2026-01 | MCB-001, MCB-002 | 01_1211_H |
| BANCO-2026-02 | MCB-003, MCB-004 | 01_1211_A |
| BANCO-2026-03 | MCB-005, MCB-006 | 02_1305_C |

---

### `08_devoluciones_gestion.xlsx`

**Uso:** Flujo **Devoluciones** (solicitud desde APK), pool de reasignación y gestión especial.

| Código | Sección | Notas |
|--------|---------|-------|
| DEV-H-001 / DEV-H-002 | 01_1211_H | Direcciones difíciles — zona inaccesible |
| DEV-A-001 / DEV-A-002 | 01_1211_A | Riesgo / reasignación |
| DEV-C-001 / DEV-C-002 | 02_1305_C | Gestión especial |
| DEV-G-001 | 01_1211_G | Sección extra para reasignar |

**Pasos:** cargar → publicar a Firebase → gestor solicita devolución en APK → admin en Devoluciones.

---

### `09_call_center_volumen.xlsx`

**Uso:** Reparto equitativo LPT con **20 cuentas** (montos de S/ 1200 a S/ 45), sección `01_1211_T`.

---

### `10_actualizacion_mixta.xlsx`

**Uso:** Actualización del banco tras haber cargado `01_carga_inicial`.

- Sin `CTEST001` (baja)
- Cambios en `CLI-A-001` y `CLI-C-001`
- Altas `ACT-NEW-001` y `ACT-NEW-002`

---

## Gestores de prueba (Firebase)

Para ver clientes en Flutter/APK, crear usuarios con `secciones` que incluyan las claves del Excel, por ejemplo:

- Campo: `01_1211_H`, `01_1211_A`, `02_1305_C`, `02_1211_H`, `01_1211_T`, `01_1211_E`, `01_1211_X`
- Call: sección virtual `_CALL_{uid}` tras reparto

---

## Referencias en código

- Columnas: `admin-app/config.py` → `EXCEL_COLUMNS`
- Parser: `admin-app/services/excel_parser.py`
- Diff: `admin-app/services/diff_engine.py`
- UAT actualización: `admin-app/docs/UAT-ACTUALIZACION-EXCEL.md`
- Spec: `electron-app-docs/04_MODULO_EXCEL_PARSER.md`
