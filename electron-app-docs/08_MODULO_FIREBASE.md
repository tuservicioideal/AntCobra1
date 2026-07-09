# 08 — Módulo Firebase (Firestore + Storage)

## Descripción

Maneja toda la comunicación con Firebase. En Electron, el Admin SDK corre en el proceso Main (tiene credenciales). El SDK cliente (auth REST, Firestore reads en tiempo real) puede correr en Renderer.

---

## Inicialización (proceso Main)

```typescript
// firebase-admin.service.ts
import * as admin from 'firebase-admin'
import serviceAccount from '../../../clase-001-firebase-adminsdk-fbsvc-ee190f0bcc.json'

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  projectId: "clase-001",
  storageBucket: "clase-001.firebasestorage.app"
})

const db = admin.firestore()
const storage = admin.storage()
```

---

## Estructura de Firestore

```
campañas/cartera_activa/
  (metadata doc):
    fecha_creacion: Timestamp
    total_clientes: number
    total_secciones: number
    secciones: string[]          ← array de composite keys
    estado: "activa"

  gestores/{seccion_key}/
    seccion_key: string          ← "01_1211_H"
    seccion: string              ← "H" (letra para display)
    region: string
    zona: string
    num_clientes: number
    deuda_total: number
    deuda_pendiente: number
    clientes_con_coordenadas: number

    clientes/{codigo_cliente}/
      (todos los campos de ClientData excepto numero_documento)
      estado_gestion: string
      tramo_actual: number
      nivel_1: string
      nivel_2: string
      nivel_3: string
      nivel_4: string
      canal_gestion: string
      fecha_promesa_pago: string
      monto_promesa_pago: number
      nota_gestor: string
      fecha_gestion: Timestamp
      gps_latitud: number
      gps_longitud: number
      ultima_nota_contacto: string
      fecha_actualizacion_contacto_iso: string
      actualizado_por_uid: string
      actualizado_por_nombre: string
      actualizado_por_email: string
      origen_actualizacion: string

usuarios/{uid}/
  nombre: string
  email: string
  rol: string
  activo: boolean
  seccion: string          ← legacy (letra)
  secciones: string[]      ← composite keys array
  zona: string
  region: string
  telefono: string
  canal: string

estructura_territorial/catalogo
  regiones: {
    "01": {
      zonas: {
        "1211": {
          secciones: ["H", "C", "G"]
        }
      }
    }
  }

cartas_generadas/{doc_id}
  campaign_id: string
  numero_carta: number
  cliente_id: string
  seccion_key: string
  gestor_uid: string
  nombre_archivo: string
  mime_type: string
  storage_path: string
  size_bytes: number
  estado: "disponible"
  created_at: Timestamp
```

---

## Subida de cartera (upload_cartera) — comportamiento

1. Crea/actualiza doc metadata de campaña
2. Para cada sección:
   - **Lee datos de visita existentes** antes de sobreescribir (preserva campos de gestores)
   - Escribe doc del gestor (info de sección)
   - Escribe cada cliente con batch writes
   - Si el cliente ya tenía visita registrada → **merge** de los campos de visita
3. Sube jerarquía territorial a `estructura_territorial/catalogo`
4. Retorna estadísticas: `{ uploaded, preserved, errors }`

### Campos de visita preservados en re-subida

```typescript
const VISIT_FIELDS = [
  "estado_gestion", "fecha_gestion", "nota_gestor", "gps_gestor",
  "ubicacion_verificada", "historial_zona",
  "gps_latitud", "gps_longitud", "gps_timestamp",
  "nivel_1", "nivel_2", "nivel_3", "nivel_4",
  "canal_gestion", "fecha_promesa_pago", "monto_promesa_pago",
  "direccion", "telefono_movil", "ultima_nota_contacto",
  "fecha_actualizacion_contacto_iso",
  "actualizado_por_uid", "actualizado_por_nombre", "actualizado_por_email",
  "origen_actualizacion"
]
```

---

## Sync de visitas (Firebase → SQLite)

```typescript
async function syncVisitsFromFirebase(campanaId: string) {
  const secciones = await db.collection("campañas").doc(campanaId)
    .get().then(d => d.data()?.secciones ?? [])

  for (const seccionKey of secciones) {
    const clientesSnap = await db
      .collection("campañas").doc(campanaId)
      .collection("gestores").doc(seccionKey)
      .collection("clientes").get()

    for (const doc of clientesSnap.docs) {
      const data = doc.data()
      // Actualizar SQLite por codigo_cliente
      updateLocalCliente(doc.id, {
        estado_gestion: data.estado_gestion,
        nota_gestor: data.nota_gestor,
        fecha_gestion: data.fecha_gestion,
        gps_latitud: data.gps_latitud,
        gps_longitud: data.gps_longitud,
        nivel_1: data.nivel_1, nivel_2: data.nivel_2,
        nivel_3: data.nivel_3, nivel_4: data.nivel_4,
        canal_gestion: data.canal_gestion,
        fecha_promesa_pago: data.fecha_promesa_pago,
        monto_promesa_pago: data.monto_promesa_pago,
        // ... resto de campos de visita
      })
    }
  }
}
```

---

## Gestión de usuarios Firebase

```typescript
// Crear usuario gestor
async function createGestorUser(params: {
  email: string
  password: string
  nombre: string
  rol: string
  seccion: string          // letra (legacy)
  secciones: string[]      // composite keys
  zona: string
  region: string
  telefono: string
  canal: string
}) {
  // 1. Firebase Auth: crear usuario
  const user = await admin.auth().createUser({ email, password, displayName: nombre })
  // 2. Firestore: crear perfil
  await db.collection("usuarios").doc(user.uid).set({
    ...params, activo: true, uid: user.uid
  })
}

// Actualizar usuario
async function updateGestorUser(uid: string, updates: Partial<UserProfile>)

// Desactivar usuario (no eliminar)
async function deactivateUser(uid: string)

// Listar usuarios activos
async function listUsers(): Promise<UserProfile[]>
```

---

## Firebase Storage (cartas generadas)

- Path: `cartas_generadas/{campaign_id}/{seccion_key}/{gestor_uid}/{filename}`
- Se registra metadata en Firestore `cartas_generadas/{doc_id}`
- Proceso: Main genera el .docx → lo sube a Storage → guarda metadata en Firestore
