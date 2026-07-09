# 19 — Sistema de Diseño UI

## Paleta de colores (replicar en nuevo app)

```typescript
// Design tokens del admin-app original
const colors = {
  // Backgrounds
  sidebar_bg:    "#0F172A",   // Sidebar oscuro (Slate 900)
  bg:            "#F1F5F9",   // Fondo principal (Slate 100)
  card_bg:       "#FFFFFF",   // Cards

  // Accents
  accent:        "#6366F1",   // Indigo 500 (botones primarios, tab activo)
  accent_hover:  "#4F46E5",   // Indigo 600 (hover)
  accent_light:  "#EEF2FF",   // Indigo 50 (fondos sutiles)

  // Sidebar
  sidebar_hover: "#1E293B",   // Slate 800
  sidebar_text:  "#94A3B8",   // Slate 400
  sidebar_text_active: "#FFFFFF",

  // Text
  text_primary:  "#0F172A",   // Slate 900
  text_secondary:"#64748B",   // Slate 500
  text_muted:    "#94A3B8",   // Slate 400

  // Borders
  border:        "#E2E8F0",   // Slate 200

  // Status
  success:       "#10B981",   // Emerald 500
  warning:       "#F59E0B",   // Amber 500
  error:         "#EF4444",   // Red 500
  info:          "#3B82F6",   // Blue 500
  white:         "#FFFFFF",
}
```

---

## Sidebar

```
┌─────────────┐
│  🏠 AntCob  │  ← Logo/título
├─────────────┤
│  Dashboard  │  ← Item activo (accent bg)
│  Campaña    │
│  Monitor    │
│  Equipo     │
│  Documentos │
│  Exportar   │
│  Sync       │
│  Alertas 🔴3│  ← Badge con conteo
│  Tracking   │
│  Config     │
├─────────────┤
│  Usuario    │  ← Footer con nombre/rol
│  Cerrar     │
└─────────────┘
```

Ancho: `220px`. Colapsable a `60px` (solo íconos).

---

## Componentes clave

### KPICard
```tsx
<KPICard
  icon="👥"
  label="Total Clientes"
  value="234"
  delta="+12 hoy"        // opcional
  color="accent"         // optional color accent
/>
```

### SectionHeader
```tsx
<SectionHeader
  title="Gestión de Equipo"
  subtitle="Administra usuarios y distribución"
  actions={<Button>Nuevo</Button>}
/>
```

### StatusBadge
```tsx
<StatusBadge status="visitado_habido" />
// → Verde, texto "Visitado"

<StatusBadge status="pendiente" />
// → Gris, texto "Pendiente"
```

Mapa de estados:

| Estado | Color | Etiqueta |
|--------|-------|---------|
| pendiente | Gris | Pendiente |
| visitado_habido | Verde | Visitado |
| visitado_no_habido | Amarillo | No Habido |
| fallecido_inubicable | Rojo oscuro | Fallecido/Inubicable |
| suplantacion | Naranja | Suplantación |
| pago_no_registrado | Púrpura | Pago No Reg. |

### RolBadge

| Rol | Color |
|-----|-------|
| admin | Rojo/rosa |
| supervisor | Naranja |
| asistente | Azul |
| gestor | Verde |

---

## Barra de campaña activa (header)

Siempre visible en la parte superior del contenido:

```
📋 [Nombre Campaña]  |  Día 12 de 60  |  48 días restantes  |  234 clientes  |  [Tramo 1]
```

---

## Tipografía

- Familia: **Inter** (o system-ui fallback)
- Tamaños:
  - `xs`: 11px
  - `sm`: 12px
  - `base`: 13px
  - `md`: 14px
  - `lg`: 16px
  - `xl`: 18px
  - `2xl`: 22px
  - `3xl`: 28px

---

## Layout de páginas

```
┌──────────────────────────────────────────────────────┐
│ Sidebar (220px)  │  Header (campaign bar)             │
│                  ├───────────────────────────────────┤
│                  │  [SectionHeader con título+acciones]│
│                  │                                    │
│                  │  [KPI strip]                       │
│                  │                                    │
│                  │  [Contenido scrollable]            │
│                  │                                    │
└──────────────────┴────────────────────────────────────┘
```
