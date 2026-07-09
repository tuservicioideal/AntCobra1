# 04 — Módulo Excel Parser (Carga de Cartera del Banco)

## Descripción

Lee el archivo Excel que entrega el banco con la cartera de deudores. Extrae y normaliza los datos de cada cliente, construye la clave de sección compuesta y agrupa por sección.

---

## Mapeo de columnas Excel (0-indexed)

| Campo | Columna Excel | Índice | Tipo |
|-------|--------------|--------|------|
| segmentacion | A | 0 | string |
| segmento_cartera | B | 1 | string |
| etapa_deuda | C | 2 | string |
| cobrador | D | 3 | string |
| campana_banco | E | 4 | string |
| **region** | F | 5 | string |
| **zona** | G | 6 | string |
| **seccion** | H | 7 | string ← clave de asignación gestor |
| territorio | I | 8 | string |
| **codigo_cliente** | J | 9 | string ← ID principal |
| digito_control | K | 10 | string |
| nombres | L | 11 | string |
| apellido_paterno | M | 12 | string |
| apellido_materno | N | 13 | string |
| genero | O | 14 | string |
| edad | P | 15 | int |
| **numero_documento** (DNI) | X | 23 | string ← SQLite y Firestore |
| telefono_fijo | Z | 25 | string |
| telefono_trabajo | AA | 26 | string |
| **telefono_movil** | AB | 27 | string |
| correo | AC | 28 | string |
| departamento | AD | 29 | string |
| provincia | AE | 30 | string |
| distrito | AF | 31 | string |
| **direccion** | AH | 33 | string |
| referencia | AI | 34 | string |
| **coordenada_x** (longitud) | AJ | 35 | float |
| **coordenada_y** (latitud) | AK | 36 | float |
| fecha_documento | AM | 38 | string |
| fecha_vencimiento | AN | 39 | string |
| fecha_asignacion | AO | 40 | string |
| fecha_cierre | AP | 41 | string |
| **dias_atraso** | AQ | 42 | int |
| importe_deuda_original | AR | 43 | float |
| importe_abonos_anteriores | AS | 44 | float |
| **importe_deuda_asignada** | AT | 45 | float |
| **importe_deuda_pendiente** | AY | 50 | float |
| perfil_score | CA | 78 | string |

---

## Clave de sección compuesta

```typescript
function makeSeccionKey(region: string, zona: string, seccion: string): string {
  const r = region.trim() || "SR"
  const z = zona.trim() || "SZ"
  const s = seccion.trim().toUpperCase() || "SS"
  return `${r}_${z}_${s}`  // Ej: "01_1211_H"
}
```

**Propósito**: La misma letra de sección (H, C, G) puede repetirse en distintas zonas/regiones. La clave compuesta garantiza unicidad.

---

## Resultado del parser

```typescript
interface ParseResult {
  allClients: ClientData[]
  bySeccion: Record<string, ClientData[]>  // keyed by composite key
  summary: {
    totalClientes: number
    totalSecciones: number
    secciones: Record<string, number>       // key → count
    totalDeudaAsignada: number
    totalDeudaPendiente: number
    departamentos: string[]
  }
  headers: string[]
}
```

---

## Objeto cliente (ClientData)

```typescript
interface ClientData {
  // Identificación
  codigo_cliente: string
  digito_control: string
  numero_documento: string  // DNI — SQLite y Firestore
  nombres: string
  apellido_paterno: string
  apellido_materno: string
  nombre_completo: string   // construido: nombres + apellidos
  genero: string
  edad: number

  // Contacto
  telefono_fijo: string
  telefono_trabajo: string
  telefono_movil: string
  correo: string

  // Ubicación
  departamento: string
  provincia: string
  distrito: string
  direccion: string
  referencia: string
  coordenada_x: number   // longitud
  coordenada_y: number   // latitud

  // Clasificación bancaria
  segmentacion: string
  segmento_cartera: string
  etapa_deuda: string
  cobrador: string
  campana_banco: string
  region: string
  zona: string
  seccion: string         // letra normalizada en MAYÚSCULAS
  seccion_key: string     // clave compuesta: region_zona_seccion
  territorio: string
  perfil_score: string

  // Fechas
  fecha_documento: string
  fecha_vencimiento: string
  fecha_asignacion: string
  fecha_cierre: string

  // Montos
  dias_atraso: number
  importe_deuda_original: number
  importe_abonos_anteriores: number
  importe_deuda_asignada: number
  importe_deuda_pendiente: number
}
```

---

## Jerarquía territorial (para vista de campaña)

El parser también construye la jerarquía `Region → Zona → Sección`:

```typescript
interface TerritorialHierarchy {
  regions: Record<string, {
    zonas: Record<string, {
      secciones: Record<string, {
        num_clientes: number
        deuda_asignada: number
        deuda_pendiente: number
      }>
      num_clientes: number
    }>
    num_clientes: number
  }>
  totals: { num_clientes: number; deuda_asignada: number; deuda_pendiente: number }
}
```

Esta jerarquía se sube a Firestore en `estructura_territorial/catalogo` para que los apps la usen en los selectores en cascada.

---

## Reglas de limpieza de datos

- Filas con `codigo_cliente` vacío → ignorar
- Sección vacía → `"SIN_SECCION"`, region vacía → `"SR"`, zona vacía → `"SZ"`
- Sección normalizada a MAYÚSCULAS
- Valores monetarios: reemplazar comas por punto antes de parsear float
- Fechas: convertir datetime a string `YYYY-MM-DD`
- `nombre_completo = nombres + " " + apellido_paterno + " " + apellido_materno`
