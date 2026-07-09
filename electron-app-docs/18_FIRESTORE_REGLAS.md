# 18 — Reglas de Seguridad Firestore

## Resumen de reglas por colección

### `usuarios/{uid}`
- **Leer**: usuario autenticado puede leer su propio perfil
- **Leer (lista)**: admin/supervisor pueden listar todos
- **Escribir**: solo admin/supervisor (para crear/editar gestores)

### `campañas/{campanaId}/gestores/{seccion}/clientes/{clienteId}`
- **Leer**: usuario con la sección en su array `secciones`
- **Escribir**: solo el gestor asignado a esa sección (para actualizar estado_gestion, niveles, GPS)
- **Admin write**: admin/supervisor pueden escribir cualquier sección

### `estructura_territorial/catalogo`
- **Leer**: cualquier usuario activo
- **Escribir**: admin/supervisor

### `cartas_generadas/{docId}`
- **Leer**: admin/supervisor/asistente
- **Escribir**: admin/supervisor (lo escribe el desktop app via Admin SDK, saltea reglas)

---

## Helper functions usadas en reglas

```javascript
function isAuthenticated() {
  return request.auth != null;
}

function isActiveUser() {
  return isAuthenticated()
    && get(/databases/$(database)/documents/usuarios/$(request.auth.uid)).data.activo == true;
}

function getUserRole() {
  return get(/databases/$(database)/documents/usuarios/$(request.auth.uid)).data.rol;
}

function isAdminOrSupervisor() {
  return isActiveUser() && getUserRole() in ['admin', 'supervisor'];
}

function isGestorForSection(seccionKey) {
  let userData = get(/databases/$(database)/documents/usuarios/$(request.auth.uid)).data;
  return isActiveUser()
    && (seccionKey in userData.get('secciones', [])
        || userData.get('seccion', '') == seccionKey.split('_')[2]);
}
```

---

## Notas importantes para Electron

- El **Admin SDK** (proceso Main de Electron) **saltea todas las reglas de Firestore**
- Las subidas masivas, creación de usuarios y sincronizaciones usan Admin SDK → no están limitadas por estas reglas
- El SDK cliente (si se usa en Renderer para listeners en tiempo real) sí está sujeto a las reglas
- Las reglas protegen a los apps móvil/web (Flutter app, gestor-app)
