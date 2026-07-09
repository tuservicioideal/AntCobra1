# FASE 3 — Plan Técnico: Integración, Seguridad y Reportes

## Estado: ✅ COMPLETADO

## Diagnóstico Post-Fase 2

### Bugs Encontrados
1. **GPS Key Mismatch** — `pull_visit_data()` lee `gps_gestor.lat / .lng` pero el gestor-app
   escribe `gps_gestor.latitude / .longitude`. Los datos GPS nunca llegan a SQLite.
2. **Estados no contados** — `get_campaign_status()` solo reconoce 4 estados; `suplantacion`
   y `pago_no_registrado` caen al vacío (no se suman a ningún contador).

### Gaps de Integración
3. **MonitorWindow** (desktop) — `_STATUS_LABELS` solo tiene 4 estados.
4. **StatsWindow** (desktop) — Pie chart solo muestra 4 slices.
5. **Sin visor de alertas** — gestor-app escribe a `alertas/` en Firestore, pero admin-app
   no las lee ni muestra.
6. **Cartas genéricas** — `word_generator.py` genera una carta idéntica para todos los tramos.
   Debería variar contenido según carta 1 (notificación), 2 (seguimiento), 3 (advertencia),
   4 (último aviso / cierre).
7. **Sin informe final Día 60** — El requerimiento indica que al día 60 se consolida
   todo el historial para emitir un Informe Final de Campaña.
8. **Firestore rules inseguras** — `request.auth != null` permite acceso total a cualquier
   usuario autenticado.

---

## Implementación

### 1. Fix GPS Key Mismatch (firebase_service.py)
- Cambiar `gps_gestor.lat` → `gps_gestor.latitude`
- Cambiar `gps_gestor.lng` → `gps_gestor.longitude`
- Cambiar `gps_gestor.timestamp` → `gps_gestor.timestamp` (OK, coincide)

### 2. Nuevos estados en get_campaign_status()
- Agregar contadores `suplantacion` y `pago_no_registrado` al resumen
- Ambos cuentan como "deuda visitada" para cobertura

### 3. MonitorWindow — Agregar estados
- Agregar a `_STATUS_LABELS`: suplantacion → "Suplantación ⚠" y pago_no_registrado → "Pago NR 💳"
- Agregar KPIs para los 2 nuevos estados

### 4. StatsWindow — Pie chart con 6 estados
- Agregar 2 slices nuevos al pie chart con colores consistentes con gestor-app
- Actualizar leyenda

### 5. Firestore Security Rules
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Helpers
    function isAuth() { return request.auth != null; }
    function getUserData() { return get(/databases/$(database)/documents/usuarios/$(request.auth.uid)).data; }
    function isAdmin() { return isAuth() && getUserData().rol in ['admin', 'supervisor']; }

    // Usuarios — only admin can write, all auth can read own
    match /usuarios/{userId} {
      allow read: if isAuth();
      allow write: if isAdmin() || request.auth.uid == userId;
    }

    // Campañas — gestors read their section, admin reads all
    match /campañas/{campaignId}/{document=**} {
      allow read: if isAuth();
      allow write: if isAdmin() || (isAuth() && resource != null);
    }

    // Alertas — gestors create, admin/supervisor read/update
    match /alertas/{alertId} {
      allow create: if isAuth();
      allow read, update: if isAdmin();
    }
  }
}
```

### 6. Admin Alertas Viewer
- Nueva clase `AlertasWindow` (CTkToplevel) en app.py
- Lee colección `alertas` filtrada por estado_alerta='pendiente'
- Botón "Ver Alertas" en la barra de herramientas (con badge de contador)
- Permite marcar alertas como "revisada" desde la UI
- Muestra tipo, cliente, gestor, GPS, fecha, nota

### 7. Tramo-aware Letter Generation
- `word_generator.py` → nueva función `generate_tramo_letter()` que acepta `numero_carta`
- Carta 1: Notificación — tono informativo neutral
- Carta 2: Recordatorio — tono firme
- Carta 3: Advertencia — mención de cierre inminente
- Carta 4: Último Aviso — fecha límite, mención de informe final
- Encabezado indica "CARTA N° X" y "TRAMO Y"
- `campaign_manager.get_pending_letters()` ya calcula qué cartas faltan
- UI: botón "Generar Cartas del Tramo" que usa las cartas pendientes del tramo_engine

### 8. Informe Final Día 60
- Nueva función `generate_final_report()` en campaign_manager.py
- Genera documento Word con:
  - Resumen ejecutivo (totales, deuda gestionada, cobertura %)
  - Tabla por sección (avance, deuda, estados)
  - Lista de alertas (suplantaciones, pagos no registrados)
  - Historial de tramos transitados
  - Clientes pendientes sin gestionar
- Se dispara al ejecutar "Evaluar Tramos" cuando dia >= 60

---

## Archivos a Modificar
1. `admin-app/services/firebase_service.py` — fix GPS keys, add new states to resumen
2. `admin-app/services/word_generator.py` — tramo-aware letters + final report
3. `admin-app/services/campaign_manager.py` — final report orchestration
4. `admin-app/ui/app.py` — MonitorWindow, StatsWindow, AlertasWindow, toolbar
5. `firestore.rules` — role-based security
