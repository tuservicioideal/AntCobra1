# 05 — Módulo Base de Datos Local (SQLite)

## Descripción

SQLite es la **fuente de verdad local**. Todos los datos del banco, estados de gestión y configuración se guardan aquí primero. Firebase es el espejo de nube operativo (incluye DNI para gestores call y campo).

---

## Tablas

### `schema_version`
Control de migraciones.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER PK | |
| version | INTEGER | Número de versión |
| applied_at | DATETIME | Cuándo se aplicó |
| description | VARCHAR(200) | |

---

### `campanas`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | VARCHAR(100) PK | Generado: `YYYYMMDD_nombre_uuid6` |
| nombre | VARCHAR(200) | |
| fecha_inicio | DATE | |
| fecha_fin | DATE | inicio + 60 días |
| estado | VARCHAR(20) | `activa` / `pausada` / `cerrada` |
| archivo_origen | VARCHAR(500) | Path al Excel original |
| total_clientes | INTEGER | |
| total_secciones | INTEGER | |
| deuda_total_asignada | FLOAT | |
| deuda_total_pendiente | FLOAT | |
| fecha_creacion | DATETIME | |
| notas | TEXT | |

**Propiedades calculadas**:
- `dia_actual`: días desde `fecha_inicio` (1-60)
- `dias_restantes`: días hasta `fecha_fin`

---

### `clientes`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INTEGER PK auto | |
| campana_id | FK campanas.id | CASCADE DELETE |
| codigo_cliente | VARCHAR(50) | Índice |
| digito_control | VARCHAR(10) | |
| numero_documento | VARCHAR(20) | DNI — local y Firestore (gestores) |
| nombres | VARCHAR(100) | |
| apellido_paterno | VARCHAR(100) | |
| apellido_materno | VARCHAR(100) | |
| nombre_completo | VARCHAR(300) | |
| genero | VARCHAR(10) | |
| edad | INTEGER | |
| telefono_fijo | VARCHAR(30) | |
| telefono_trabajo | VARCHAR(30) | |
| telefono_movil | VARCHAR(30) | |
| correo | VARCHAR(100) | |
| departamento | VARCHAR(60) | |
| provincia | VARCHAR(60) | |
| distrito | VARCHAR(60) | |
| direccion | TEXT | |
| referencia | TEXT | |
| coordenada_x | FLOAT | Longitud |
| coordenada_y | FLOAT | Latitud |
| segmentacion | VARCHAR(50) | |
| segmento_cartera | VARCHAR(50) | |
| etapa_deuda | VARCHAR(50) | |
| cobrador | VARCHAR(100) | |
| campana_banco | VARCHAR(100) | |
| region | VARCHAR(50) | |
| zona | VARCHAR(50) | |
| seccion | VARCHAR(10) | Letra de sección (índice) |
| territorio | VARCHAR(50) | |
| perfil_score | VARCHAR(50) | |
| fecha_documento | VARCHAR(20) | |
| fecha_vencimiento | VARCHAR(20) | |
| fecha_asignacion | VARCHAR(20) | |
| fecha_cierre | VARCHAR(20) | |
| dias_atraso | INTEGER | |
| importe_deuda_original | FLOAT | |
| importe_abonos_anteriores | FLOAT | |
| importe_deuda_asignada | FLOAT | |
| importe_deuda_pendiente | FLOAT | |
| tramo_actual | INTEGER | 0=ninguno, 1, 2, 3 |
| estado_gestion | VARCHAR(30) | Ver enum abajo |
| nota_gestor | TEXT | |
| fecha_gestion | DATETIME | |
| gps_latitud | FLOAT | |
| gps_longitud | FLOAT | |
| gps_timestamp | VARCHAR(30) | |
| nivel_1 | VARCHAR(100) | Clasificación jerárquica |
| nivel_2 | VARCHAR(100) | |
| nivel_3 | VARCHAR(100) | |
| nivel_4 | VARCHAR(100) | |
| canal_gestion | VARCHAR(10) | `CAM` o `TEL` |
| fecha_promesa_pago | VARCHAR(20) | |
| monto_promesa_pago | FLOAT | |
| ultima_nota_contacto | TEXT | |
| fecha_actualizacion_contacto_iso | VARCHAR(40) | |
| actualizado_por_uid | VARCHAR(100) | |
| actualizado_por_nombre | VARCHAR(200) | |
| actualizado_por_email | VARCHAR(120) | |
| origen_actualizacion | VARCHAR(20) | |
| sincronizado_firebase | BOOLEAN | |
| fecha_creacion | DATETIME | |
| fecha_actualizacion | DATETIME | |

**Índices**:
- `ix_clientes_campana_seccion` (campana_id, seccion)
- `ix_clientes_campana_tramo` (campana_id, tramo_actual)

**Propiedades calculadas**:
- `es_alto_valor`: `importe_deuda_pendiente > 500`
- `requiere_carta_fisica`: `importe_deuda_pendiente > 40`
- `sigue_en_gestion`: `importe_deuda_pendiente >= 10`

---

### `historial_tramos`

Registro de cada cambio de tramo.

| Campo | Tipo |
|-------|------|
| id | INTEGER PK |
| campana_id | FK |
| cliente_id | FK |
| tramo_anterior | INTEGER |
| tramo_nuevo | INTEGER |
| dia_campana | INTEGER |
| fecha_transicion | DATETIME |
| motivo | VARCHAR(200) |

---

### `cartas_generadas`

| Campo | Tipo |
|-------|------|
| id | INTEGER PK |
| campana_id | FK |
| cliente_id | FK |
| numero_carta | INTEGER (1-5) |
| tramo | INTEGER |
| dia_campana | INTEGER |
| fecha_generacion | DATETIME |
| archivo_path | VARCHAR(500) |
| saldo_al_generar | FLOAT |
| omitida_por_monto | BOOLEAN |

---

### `sync_log`

Log de sincronizaciones con Firestore.

| Campo | Tipo |
|-------|------|
| id | INTEGER PK |
| timestamp | DATETIME |
| tipo | VARCHAR(50) |
| registros_procesados | INTEGER |
| registros_actualizados | INTEGER |
| errores | INTEGER |
| detalle | TEXT |

---

### `config_campana`

Configuración editable por admin.

| Campo | Tipo | Default |
|-------|------|---------|
| id | INTEGER PK | |
| tramo1_inicio | INTEGER | 1 |
| tramo1_fin | INTEGER | 8 |
| tramo2_inicio | INTEGER | 9 |
| tramo2_fin | INTEGER | 43 |
| tramo3_inicio | INTEGER | 44 |
| tramo3_fin | INTEGER | 60 |
| carta1_dia | INTEGER | 1 |
| carta2_dia | INTEGER | 9 |
| carta3_dia | INTEGER | 11 |
| carta4_dia | INTEGER | 35 |
| carta5_dia | INTEGER | 44 |
| umbral_minimo_gestion | FLOAT | 10.0 |
| umbral_carta_fisica | FLOAT | 40.0 |
| nombre_proveedor | VARCHAR(100) | "PERECAUDOL" |

---

## Enums

### EstadoGestion
- `pendiente`
- `visitado_habido`
- `visitado_no_habido`
- `fallecido_inubicable`
- `suplantacion`
- `pago_no_registrado`

### TramoEnum
- `0` = Sin asignar
- `1` = Tramo 1 (Días 1-8)
- `2` = Tramo 2 (Días 9-43)
- `3` = Tramo 3 (Días 44-60)

---

## Ubicación de la BD

```
electron-app/
└── userData/              ← app.getPath('userData')
    └── antcobranzas.db
```

La base se crea automáticamente si no existe. Se puede configurar ubicación en Settings.
