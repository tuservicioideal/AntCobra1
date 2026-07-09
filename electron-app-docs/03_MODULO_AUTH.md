# 03 — Módulo de Autenticación

## Descripción

Login con email/password contra Firebase Auth REST API. Tras autenticar, se carga el perfil del usuario desde Firestore para determinar rol y permisos.

---

## Flujo de autenticación

```
1. Usuario ingresa email + password en LoginPage
2. POST https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}
   Body: { email, password, returnSecureToken: true }
3. Respuesta: { localId (uid), idToken, refreshToken }
4. Leer Firestore: usuarios/{uid}
5. Validar que activo === true
6. Guardar en estado global: uid, email, nombre, rol, secciones, idToken
```

---

## Estructura del documento de usuario en Firestore

```
usuarios/{uid}/
  nombre: string
  email: string
  rol: "admin" | "supervisor" | "asistente" | "gestor"
  activo: boolean
  seccion: string          ← letra legacy (backward compat)
  secciones: string[]      ← array de composite keys ej. ["01_1211_H", "01_1211_C"]
  zona: string
  region: string
  telefono: string
  canal: "CAM" | "TEL"     ← solo gestores
```

---

## Roles y permisos

| Permiso | admin | supervisor | asistente | gestor |
|---------|:-----:|:----------:|:---------:|:------:|
| Cargar Excel | ✅ | ✅ | ❌ | ❌ |
| Subir a Firebase | ✅ | ✅ | ❌ | ❌ |
| Gestionar usuarios | ✅ | ✅ | ❌ | ❌ |
| Distribuir secciones | ✅ | ✅ | ❌ | ❌ |
| Ver estadísticas | ✅ | ✅ | ✅ | ❌ |
| Monitor de visitas | ✅ | ✅ | ✅ | ❌ |
| Generar cartas | ✅ | ✅ | ❌ | ❌ |
| Exportar Excel banco | ✅ | ✅ | ✅ | ❌ |
| Ver configuración | ✅ | ❌ | ❌ | ❌ |

---

## Errores de autenticación (mapeo amigable)

| Código Firebase | Mensaje usuario |
|----------------|-----------------|
| `EMAIL_NOT_FOUND` | Correo electrónico no registrado |
| `INVALID_PASSWORD` | Contraseña incorrecta |
| `USER_DISABLED` | Cuenta desactivada por el administrador |
| `INVALID_LOGIN_CREDENTIALS` | Credenciales inválidas |
| `TOO_MANY_ATTEMPTS_TRY_LATER` | Demasiados intentos. Intente más tarde |
| `INVALID_EMAIL` | Formato de correo inválido |

---

## Implementación en Electron

```typescript
// En renderer (auth.service.ts)
const API_KEY = "AIzaSyBubpxyyN2YvcPaU6WUJkrF2IQUOzFVYWg"

async function signIn(email: string, password: string) {
  const res = await fetch(
    `https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${API_KEY}`,
    {
      method: "POST",
      body: JSON.stringify({ email, password, returnSecureToken: true }),
      headers: { "Content-Type": "application/json" }
    }
  )
  const data = await res.json()
  if (!res.ok) throw mapError(data.error.message)

  // Cargar perfil desde Firestore
  const profile = await getDoc(doc(db, "usuarios", data.localId))
  return { ...data, ...profile.data() }
}
```

---

## Estado global (Zustand store sugerido)

```typescript
interface AuthState {
  uid: string | null
  email: string
  nombre: string
  rol: "admin" | "supervisor" | "asistente" | "gestor" | null
  secciones: string[]
  idToken: string
  isAuthenticated: boolean
  // Helpers de permisos
  canUpload: boolean      // admin | supervisor
  canManageUsers: boolean // admin | supervisor
  canViewStats: boolean   // admin | supervisor | asistente
  canGenerateLetters: boolean // admin | supervisor
}
```
