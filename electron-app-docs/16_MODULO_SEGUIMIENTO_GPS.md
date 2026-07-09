# 16 — Módulo Seguimiento GPS (TrackingPage)

## Descripción

Visualización de rutas GPS de los gestores. Muestra en un mapa canvas/interactivo los puntos visitados y las rutas recorridas.

---

## Datos GPS disponibles por cliente

```typescript
{
  coordenada_x: number    // longitud (del Excel del banco — ubicación domicilio)
  coordenada_y: number    // latitud  (del Excel del banco — ubicación domicilio)
  gps_latitud: number     // latitud registrada por el gestor al visitar
  gps_longitud: number    // longitud registrada por el gestor al visitar
  gps_timestamp: string   // ISO timestamp de la visita GPS
  estado_gestion: string  // estado al momento del registro GPS
}
```

---

## Vista del mapa

- **Puntos de domicilio**: marcadores en coordenadas del Excel (ubicación teórica del cliente)
- **Puntos de visita**: marcadores en coordenadas GPS del gestor (donde físicamente fue)
- **Línea de ruta**: conecta los puntos de visita en orden cronológico por `gps_timestamp`
- **Color por estado**:
  - Verde: visitado_habido
  - Amarillo: visitado_no_habido
  - Gris: pendiente

---

## Filtros

- Por sección
- Por gestor
- Por fecha de visita
- Solo clientes con coordenadas
- Mostrar/ocultar domicilios del banco vs ubicaciones GPS

---

## Tecnología sugerida

Usar **Leaflet.js** + `react-leaflet` para el mapa en el renderer:

```typescript
import { MapContainer, TileLayer, Marker, Polyline, Popup } from 'react-leaflet'

// Mapa con tiles de OpenStreetMap (sin costo)
```

O bien un canvas HTML5 simple para una implementación más ligera sin dependencias de tiles.

---

## Estadísticas de cobertura GPS

- % de clientes con coordenadas disponibles en el Excel
- % de visitas con GPS registrado
- Distancia total recorrida por gestor (aproximada)
