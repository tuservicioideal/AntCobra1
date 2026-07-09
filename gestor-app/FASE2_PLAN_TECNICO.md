# FASE 2 — Plan Técnico: Mejoras UX Gestor Web App + PWA

## Decisiones Técnicas Tomadas (Post-Investigación)

### 1. Offline-First: Firestore Persistent Cache (sin Service Worker custom)
- **Firebase Web SDK v12** soporta `persistentLocalCache()` nativo.
- Se usa `initializeFirestore()` con `persistentLocalCache({tabManager: persistentSingleTabManager()})`.
- Esto cachea automáticamente documentos leídos en IndexedDB y sincroniza al volver online.
- **Decisión**: NO crear Service Worker custom para datos — Firestore lo maneja internamente.
- Se agrega hook `useOnlineStatus` para mostrar indicador visual de conectividad.

### 2. PWA: vite-plugin-pwa (Workbox)
- Se instala `vite-plugin-pwa` con `registerType: 'autoUpdate'` para precachear shell de la app.
- Genera manifest.webmanifest automáticamente con los íconos y config PWA.
- El Service Worker de Workbox cachea archivos estáticos (JS, CSS, HTML, fuentes).
- **Firestore maneja sus propios datos offline** — el SW solo cachea el shell.
- Se agregan los meta tags PWA requeridos en `index.html`.

### 3. GPS Obligatorio: Bloqueo de botones hasta captura exitosa
- Se elimina el `try/catch` que permitía continuar sin GPS.
- El sistema captura GPS automáticamente al abrir el modal.
- Si GPS falla (permiso denegado, timeout), los botones de estado se deshabilitan.
- Se muestra mensaje claro al gestor de por qué necesita activar GPS.

### 4. Nuevos Estados: suplantación + pago_no_registrado
- Se agregan 2 botones nuevos al modal de detalle de cliente.
- **Suplantación** (rojo intenso): El DNI no corresponde a la persona.
- **Pago no registrado** (azul): El deudor dice que ya pagó pero no consta.
- Ambos estados disparan una **alerta en tiempo real** a la colección `alertas` de Firestore.

### 5. Códigos Rápidos (Atajos Numéricos)
- Se implementan teclas 1-5 como atajos (escuchando eventos `keydown`).
- `1` = Visitado Habido, `2` = Visitado No Habido, `3` = Fallecido/Inubicable,
  `4` = Suplantación, `5` = Pago No Registrado.
- Se muestra indicador visual de los códigos junto a cada botón.

### 6. Indicador de Deuda Alta (> S/ 500)
- Badge visual naranja/rojo en la lista de clientes y en el modal.
- Ícono de fuego (🔥) para deudas de alto valor.

### 7. Alertas en Tiempo Real
- Al reportar suplantación o pago no registrado, se escribe un documento en:
  `alertas/{auto-id}` con tipo, cliente, gestor, GPS, timestamp.
- La administración puede ver estas alertas desde StatsPage (indicador de alertas
  pendientes).

### 8. Información de Tramo en Dashboard
- Se lee `tramo_info` y `dia_campana` del documento de campaña en Firestore.
- Se muestra en el dashboard: "Día X de 60 — Tramo Y".

### 9. Rol Asistente
- Nuevo rol "asistente" en el select de AdminPage.
- En App.jsx y DashboardPage: el asistente ve todo excepto montos financieros.
- Las tarjetas de deuda se ocultan para rol asistente.

---

## Archivos a Crear

1. `gestor-app/src/services/alertService.js` — Escritura de alertas a Firestore
2. `gestor-app/src/hooks/useOnlineStatus.js` — Hook para detectar conectividad
3. `gestor-app/public/pwa-192x192.png` — Ícono PWA 192px (placeholder)
4. `gestor-app/public/pwa-512x512.png` — Ícono PWA 512px (placeholder)

## Archivos a Modificar

1. `gestor-app/src/services/firebase.js` — Habilitar persistencia offline
2. `gestor-app/src/components/ClientDetailModal.jsx` — GPS obligatorio, nuevos estados, códigos rápidos, indicador alto valor
3. `gestor-app/src/pages/DashboardPage.jsx` — Indicador alto valor, nuevos estados, info tramo, indicador online
4. `gestor-app/src/pages/StatsPage.jsx` — Nuevos estados en gráficos y tablas
5. `gestor-app/src/pages/AdminPage.jsx` — Rol asistente en select
6. `gestor-app/src/App.jsx` — Soporte rol asistente, indicador online
7. `gestor-app/vite.config.js` — Agregar vite-plugin-pwa
8. `gestor-app/index.html` — Meta tags PWA
9. `gestor-app/package.json` — Dependencia vite-plugin-pwa

---

## Estructura de Alertas en Firestore

```
alertas/{auto-id}/
  tipo: "suplantacion" | "pago_no_registrado"
  cliente_codigo: "..."
  cliente_nombre: "..."
  seccion: "A"
  gestor_email: "..."
  gestor_nombre: "..."
  gps: { latitude, longitude, accuracy, timestamp }
  nota: "..."
  fecha: SERVER_TIMESTAMP
  estado_alerta: "pendiente"  // pendiente / revisada
  campaign_id: "cartera_activa"
```
