# 11 — Módulo Exportación (ExportPage)

## Descripción

Exporta los resultados de gestión a un archivo Excel en el formato requerido por el banco para la liquidación de cartera.

---

## Columnas de salida (formato banco)

| Col | Cabecera | Campo origen | Notas |
|-----|---------|--------------|-------|
| A | Etapa | `etapa_deuda` | Del Excel original |
| B | Nombre proveedor | configurable | Default: "PERECAUDOL" |
| C | Numero campaña | `campana_banco` | |
| D | Codigo cliente | `codigo_cliente` | |
| E | Fecha gestion | `fecha_gestion` (parte fecha) | Formato: `dd/mm/yyyy` |
| F | Hora gestion | `fecha_gestion` (parte hora) | Formato: `HH:MM:SS` |
| G | Nivel 1 | `nivel_1` | |
| H | Nivel 2 | `nivel_2` | |
| I | Nivel 3 | `nivel_3` | |
| J | Nivel 4 | `nivel_4` | |
| K | Fecha promesa pago | `fecha_promesa_pago` | |
| L | Monto promesa pago | `monto_promesa_pago` | |
| M | Observación | `nota_gestor` | |

---

## Opciones de exportación

- **Filtro de sección**: exportar una sección específica o todas
- **Filtro de estado**: solo gestionados, todos, pendientes
- **Filtro de fecha**: rango de fecha_gestion
- **Solo con nivel asignado**: excluir clientes sin gestión registrada
- **Nombre proveedor**: configurable (default "PERECAUDOL")

---

## Estilos del Excel exportado

- Fila de cabecera: fondo azul marino, texto blanco, negrita
- Columnas con anchos predefinidos (ver tabla arriba)
- Bordes en todas las celdas
- Auto-filter en cabecera
- Freeze de fila de cabecera

---

## Parsing de fecha/hora de gestión

El campo `fecha_gestion` puede llegar en varios formatos:

```typescript
function parseFechaHora(rawFechaGestion: any): { fecha: string; hora: string } {
  // Maneja: Date, ISO string ("2023-03-07 12:03:49"), Firestore Timestamp
  // Retorna: { fecha: "07/03/2023", hora: "12:03:49" }
}
```

Formatos reconocidos:
- `"YYYY-MM-DD HH:MM:SS"`
- `"YYYY-MM-DDTHH:MM:SS"`
- `"DD/MM/YYYY HH:MM:SS"`
- objetos `Date`
- Firestore Timestamp (con `.toDate()`)

---

## Función principal

```typescript
async function exportToExcel(params: {
  campanaId: string
  outputPath: string
  seccionFilter?: string        // null = todas
  nombreProveedor?: string      // default "PERECAUDOL"
  soloGestionados?: boolean     // default false
}): Promise<{ totalRows: number; outputPath: string }>
```

---

## Página de exportación (UI)

Permite:
1. Seleccionar carpeta destino
2. Configurar filtros
3. Preview de cuántas filas se exportarán
4. Botón "Exportar Excel"
5. Abrir carpeta destino al terminar
