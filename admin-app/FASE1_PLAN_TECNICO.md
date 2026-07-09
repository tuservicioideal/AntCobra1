# FASE 1 — Plan Técnico: Motor Estático y Lógica de Tramos

## Decisiones Técnicas Tomadas (Post-Investigación)

### 1. Base de Datos Local: SQLAlchemy 2.0 + SQLite
- **SQLAlchemy 2.0** con `DeclarativeBase` y anotaciones `Mapped[]` (estándar actual).
- **SQLite** como archivo local (`data/antcobranzas.db`) — single-user desktop app.
- **Sin Alembic**: Para una app de escritorio single-user, usamos `Base.metadata.create_all()` 
  con una tabla `schema_version` para migraciones manuales simples. Alembic sería innecesario.

### 2. Motor de Tramos: Reglas puras (sin librería de state machine)
- Se investigaron `transitions` (6.4k stars) y `python-statemachine` (v3.0.0).
- **Decisión**: NO usar state machine externas. Los tramos son **evaluación por fecha** 
  (lineal, determinista), no transiciones por eventos. Un motor de reglas puro es más 
  simple, testeable, y no agrega dependencias.

### 3. Generación de Cartas: python-docx mejorado con plantillas por tramo
- Ya existe `word_generator.py`. Se extenderá con 4 plantillas (una por carta/tramo).
- Regla estricta: solo generar carta física si `saldo_pendiente > S/ 40.00`.

### 4. Flujo de datos
```
Excel del Banco → parse_excel() → SQLite (fuente de verdad)
                                     ↓
                              TramoEngine evalúa reglas
                                     ↓
                              Genera cartas (filtrando por monto)
                                     ↓
                              Sync a Firebase (datos esenciales, sin DNI)
```

---

## Modelos de Base de Datos

### Tabla: `campanas`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | TEXT PK | Identificador único |
| nombre | TEXT | Nombre descriptivo |
| fecha_inicio | DATE | Día 1 de la campaña |
| fecha_fin | DATE | Día 60 (calculado) |
| estado | TEXT | activa / cerrada / pausada |
| archivo_origen | TEXT | Ruta del Excel original |
| total_clientes | INT | Conteo total |
| fecha_creacion | DATETIME | Timestamp |

### Tabla: `clientes`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INT PK | Autoincrement |
| campana_id | TEXT FK | Referencia a campaña |
| codigo_cliente | TEXT | Código del banco |
| numero_documento | TEXT | DNI (solo local, NO se sube a Firebase) |
| nombre_completo | TEXT | Nombre concatenado |
| seccion | TEXT | Sección/gestor asignado |
| tramo_actual | INT | 1, 2 o 3 |
| estado_gestion | TEXT | pendiente/visitado_habido/visitado_no_habido/fallecido |
| importe_deuda_asignada | REAL | Monto original |
| importe_deuda_pendiente | REAL | Monto pendiente actual |
| dias_atraso | INT | Días de mora |
| direccion | TEXT | Dirección completa |
| distrito | TEXT | Distrito |
| provincia | TEXT | Provincia |
| departamento | TEXT | Departamento |
| telefono_movil | TEXT | Celular |
| coordenada_x | REAL | Longitud |
| coordenada_y | REAL | Latitud |
| ... | ... | (todos los campos del Excel) |

### Tabla: `historial_tramos`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INT PK | Autoincrement |
| cliente_id | INT FK | Referencia a cliente |
| campana_id | TEXT FK | Referencia a campaña |
| tramo_anterior | INT | 0/1/2/3 |
| tramo_nuevo | INT | 1/2/3 |
| fecha_transicion | DATETIME | Cuándo se hizo el cambio |
| motivo | TEXT | Evaluación automática / manual |
| saldo_al_momento | REAL | Saldo cuando se evaluó |

### Tabla: `cartas_generadas`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | INT PK | Autoincrement |
| cliente_id | INT FK | Referencia a cliente |
| campana_id | TEXT FK | Referencia a campaña |
| numero_carta | INT | 1, 2, 3 o 4 |
| tramo | INT | En qué tramo se generó |
| fecha_generacion | DATETIME | Cuándo se generó |
| archivo_path | TEXT | Ruta al .docx |
| fue_impresa | BOOL | Si fue enviada a impresión |
| omitida_por_monto | BOOL | True si saldo < 40 y se omitió |

### Tabla: `gestores`
| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | TEXT PK | UID de Firebase |
| nombre | TEXT | Nombre completo |
| email | TEXT | Correo |
| seccion | TEXT | Sección asignada |
| telefono | TEXT | Teléfono |
| zona | TEXT | Zona de cobertura |
| activo | BOOL | Si está activo |

---

## Reglas del Motor de Tramos

### Tramo 1: Cobranza Normal (Días 1-8)
- **Día 1**: Se emite Carta 1 para TODOS los clientes.
- **Día 9**: Se evalúan saldos:
  - Si `saldo_pendiente >= 10.00` → Pasa a Tramo 2
  - Si `saldo_pendiente < 10.00` → Se cierra gestión (pagó o monto insignificante)

### Tramo 2: Seguimiento Medio (Días 9-43)
- **Día 9**: Se emite Carta 2 (SOLO si `saldo_pendiente > 40.00`)
- **Día 38**: Se emite Carta 3 (SOLO si `saldo_pendiente > 40.00`)
- Los clientes con `10.00 <= saldo < 40.00` avanzan de tramo pero NO consumen carta física.
- **Día 44**: Si `saldo_pendiente >= 10.00` → Pasa a Tramo 3

### Tramo 3: Cierre de Gestión (Días 44-60)
- **Día 44**: Se emite Carta 4 (SOLO si `saldo_pendiente > 40.00`)
- **Día 60**: Cierre. Se consolida historial completo → Informe Final de Campaña.

---

## Archivos a Crear/Modificar

### Nuevos:
1. `admin-app/services/database.py` — Motor SQLAlchemy, modelos ORM, sesiones
2. `admin-app/services/tramo_engine.py` — Motor de reglas de tramos
3. `admin-app/services/campaign_manager.py` — Orquestador de campañas

### Modificar:
1. `admin-app/services/excel_parser.py` — Que también inserte en SQLite
2. `admin-app/services/firebase_service.py` — Que lea de SQLite y filtre datos sensibles
3. `admin-app/services/word_generator.py` — 4 plantillas diferentes por carta
4. `admin-app/ui/app.py` — Nuevos botones y vistas para campaña/tramos
5. `admin-app/config.py` — Agregar rutas de BD y configuración
6. `admin-app/requirements.txt` — Agregar sqlalchemy
