# UAT — Actualización periódica de Excel (banco)

Prueba manual del flujo desktop → Firestore → APK Flutter.

## Precondiciones

| Componente | Requisito |
|------------|-----------|
| admin-app | Sesión admin/supervisor, Firebase conectado, campaña activa en SQLite |
| Firestore | Documento `campañas/cartera_activa` con gestores y clientes |
| Flutter APK | Gestor de prueba con `usuarios/{uid}.secciones` que incluya la sección del cliente de prueba |
| Índices | Desplegar `firestore.indexes.json` (`firebase deploy --only firestore:indexes`) |

## Datos de prueba

- **Excel A**: export con al menos 2 clientes en la misma sección (anotar `codigo_cliente` de uno como `CLIENTE_TEST`).
- **Excel B**: igual que A pero **sin** `CLIENTE_TEST` (simula pago / baja de cartera).

## Pasos

### 1. Carga inicial

1. En admin-app: Inicio → Campaña → Cargar archivo Excel → **Excel A**.
2. **Distribuir a Gestores** y esperar éxito.
3. En Flutter (gestor de esa sección): verificar que `CLIENTE_TEST` aparece en la lista del dashboard.

### 2. Actualización con baja

1. En admin-app: Inicio → tarjeta **Actualización del banco** → **Aplicar Excel del banco y notificar gestores**.
2. Seleccionar **Excel B**.
3. Revisar resumen: debe mostrar **1 removido** (o más según el diff).
4. Confirmar checklist y aplicar.
5. Verificar mensaje de éxito (archivados, notificaciones gestor/admin).

### 3. Firestore

En `campañas/cartera_activa/gestores/{seccion}/clientes/{CLIENTE_TEST}`:

- `activo_en_cartera` = `false`
- `motivo_baja` = `ausente_en_excel_banco`
- `fecha_baja` presente
- Campos de visita (`estado_gestion`, GPS, etc.) **conservados** si existían antes

### 4. Flutter

1. Abrir **Notificaciones** en el APK: debe existir entrada `base_actualizada` con detalle tipo **removido** para `CLIENTE_TEST`.
2. Volver al dashboard: `CLIENTE_TEST` **no** debe aparecer en la lista activa.
3. Otros clientes de Excel B siguen visibles.

### 5. Regresión — cambio de deuda

1. Excel C = Excel B pero con deuda pendiente distinta en un cliente activo.
2. Repetir actualización: notificación **actualizado**; visita del gestor preservada en Firestore.

### 6. Admin inbox

1. admin-app → Notificaciones (campana): documento `base_actualizada_admin` con resumen de removidos/actualizados.

## Criterios de aceptación

- [ ] Removidos se archivan en Firestore y SQLite, no se eliminan documentos.
- [ ] Gestor recibe notificación y deja de ver cliente archivado en listas/mapa.
- [ ] Totales de sección/campaña coinciden con conteo del Excel activo.
- [ ] Sección sin gestor asignado genera alerta `seccion_sin_gestor` (no notificación con UID vacío).

## Sección sin gestor (opcional)

Quitar temporalmente la sección del array `secciones` del gestor, aplicar un Excel con cambios en esa sección: debe crearse alerta en colección `alertas`, sin notificación `destinatario_uid` vacío.

## 7. Afinidad call center (plan de reparto)

### Precondiciones adicionales

- Al menos 2 gestores call activos (`canal: call`) en Firestore `usuarios`.
- `CLIENTE_CALL` en Excel A: tramo 1, asignado a asesor call X tras primera distribución.

### Pasos

1. **Excel A** → distribuir → en modal **Plan de Reparto** confirmar → publicar.
2. Verificar en Firestore: documento del cliente en `gestores/_CALL_{uid_X}/clientes/{CLIENTE_CALL}`.
3. **Excel B** = mismo `CLIENTE_CALL` (reaparece sin cambio de sección).
4. Actualizar base → confirmar diff → revisar modal Plan de Reparto: badge **Mantiene** con asesor X.
5. Confirmar y publicar.
6. Desactivar asesor X en Firestore (`activo: false`), re-subir Excel B.
7. Plan de Reparto debe mostrar **Reasignado** (LPT a otro asesor activo).
8. Tras publicar: no debe quedar duplicado activo en sección territorial; visitas conservadas en `_CALL_` destino.

### Criterios

- [ ] Panel **Plan de Reparto** accesible desde sidebar (solo lectura entre cargas).
- [ ] Re-subida mantiene `call_gestor_uid` si el asesor sigue activo.
- [ ] Asesor inactivo → reasignación LPT antes de publicar.
- [ ] Secciones `_CALL_*` consistentes con SQLite tras actualización.
