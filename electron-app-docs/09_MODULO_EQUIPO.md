# 09 — Módulo Equipo (TeamPage)

## Descripción

Gestión de usuarios del equipo y configuración de distribución de secciones. Requiere conexión Firebase activa.

---

## Pestañas de la página

1. **Usuarios** — CRUD de gestores/asistentes/supervisores
2. **Distribución** — Asignar secciones a gestores (cuando hay cartera cargada)

---

## Tab: Usuarios

### Lista de usuarios
- Tabla con: Nombre, Email, Rol, Sección(es), Estado (activo/inactivo)
- Filtro por rol
- Acciones: Editar, Activar/Desactivar
- Botón "Nuevo Usuario"

### Crear/Editar usuario

Formulario con campos:
- Nombre completo
- Email
- Contraseña (solo en creación)
- Rol: `admin` / `supervisor` / `asistente` / `gestor`
- Canal (solo gestores): `CAM` (campo) / `TEL` (call)
- Teléfono
- **Selector de secciones en cascada** (para gestores):

```
Región  [dropdown] → Zona [dropdown] → Sección [dropdown] → [Agregar]

Chips de secciones asignadas:
  [01_1211_H ×]  [01_1211_C ×]  [02_1305_B ×]
```

El selector en cascada usa la jerarquía de `estructura_territorial/catalogo`.

### Datos del usuario en Firestore

```typescript
{
  uid: string
  nombre: string
  email: string
  rol: "admin" | "supervisor" | "asistente" | "gestor"
  activo: boolean
  canal: "CAM" | "TEL"   // gestores
  seccion: string         // letra legacy
  secciones: string[]     // composite keys
  zona: string
  region: string
  telefono: string
}
```

---

## Tab: Distribución

Permite asignar qué gestor atiende qué sección de la cartera actual.

### Vista

| Sección (composite key) | Letra | # Clientes | Deuda | Gestor asignado |
|-------------------------|-------|-----------|-------|-----------------|
| 01_1211_H | H | 45 | S/ 12,340 | [dropdown] |
| 01_1211_C | C | 38 | S/ 9,870 | [dropdown] |

- El dropdown muestra gestores activos por nombre
- Al guardar: actualiza `secciones` array en el documento del usuario en Firestore
- Un gestor puede tener múltiples secciones

---

## KPIs del equipo (strip superior)

- Total usuarios
- Gestores activos
- Secciones asignadas / Total secciones
- Gestores sin sección

---

## Permisos

Solo `admin` y `supervisor` pueden acceder a esta página.
