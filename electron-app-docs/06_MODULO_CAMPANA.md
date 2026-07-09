# 06 — Módulo Campaña (CampaignPage)

## Descripción

Página central para cargar el Excel del banco, visualizar la jerarquía de cartera, evaluar tramos y distribuir secciones a gestores.

---

## Flujo: Excel → SQLite → Firebase

```
1. Usuario abre diálogo de archivo → selecciona .xlsx
2. [Main] Excel Parser procesa el archivo
3. Previsualización en UI: summary, secciones, jerarquía territorial
4. Usuario confirma → [Main] CampaignManager.createCampaignFromExcel()
   - Crea registro Campana en SQLite
   - Inserta todos los clientes
   - Asigna tramo inicial según día actual
5. Usuario hace clic "Distribuir / Subir a Firebase"
   - Se abren asignaciones de sección → gestor
   - [Main] Firebase Admin SDK sube cartera
   - Preserva datos de visita existentes (idempotente)
   - Sube jerarquía territorial a estructura_territorial/catalogo
```

## Flujo: actualización periódica del banco (re-subida)

Ubicación en admin-app: **Inicio** (tarjeta "Actualización del banco") o pestaña **Campaña** → **Aplicar Excel del banco y notificar gestores**.

```
1. Pull visitas Firestore → SQLite (no pisar gestión reciente)
2. Diff Excel vs cartera en Firestore (DiffEngine)
3. SQLite: upsert filas del Excel; archivar ausentes (activo_en_cartera=false)
4. Confirmar → upload_cartera_update + notificaciones gestores/admin
5. Flutter: notificación tipo removido/actualizado/nuevo; listas filtran activo_en_cartera
```

---

## Vista de jerarquía territorial

Árbol expandible: Region → Zona → Sección → clientes

```
01 (Región)
  └── 1211 (Zona)
        ├── H — 45 clientes | S/ 12,340.50
        ├── C — 38 clientes | S/ 9,870.00
        └── G — 52 clientes | S/ 15,100.25
```

---

## Distribución de secciones

- Cada sección (composite key) se asigna a un gestor
- Un gestor puede tener **múltiples secciones**
- El admin selecciona gestor por sección en una tabla editable
- Al guardar: `firebase_service.create_gestor_user()` actualiza `secciones` array en Firestore

---

## Barra de campaña activa

Siempre visible en el header de la app:
```
📋 Campaña Activa | Día 12 de 60 | 48 días restantes | 234 clientes
```

---

## Métodos principales (CampaignManager)

```typescript
class CampaignManager {
  // 1. Excel → SQLite
  createCampaignFromExcel(filePath: string, nombre: string): Promise<Campaign>

  // 2. Evaluación de tramos
  evaluateTramos(campanaId: string): Promise<EvaluationResult>

  // 3. SQLite → Firebase (datos operativos, incluye DNI)
  uploadToFirebase(campanaId: string, onProgress: ProgressCallback): Promise<UploadStats>

  // 4. Firebase → SQLite (sync de visitas)
  syncVisitsFromFirebase(campanaId: string): Promise<SyncStats>

  // 5. Obtener jerarquía territorial
  getHierarchy(campanaId: string): TerritorialHierarchy

  // 6. Summary de secciones
  getSeccionSummary(campanaId: string): SeccionSummary[]
}
```

---

## Estado de UI (CampaignStore)

```typescript
interface CampaignState {
  activeCampaign: Campaign | null
  parseResult: ParseResult | null
  uploadProgress: { current: number; total: number; message: string } | null
  isUploading: boolean
  isEvaluating: boolean
  lastEvaluation: EvaluationResult | null
}
```

---

## Datos operativos en Firebase

El DNI (`numero_documento`) **sí se sincroniza** a Firestore para que gestores call y campo identifiquen al deudor. La política vigente (jun/2026) está en `admin-app` → `get_firebase_payload(include_sensitive=True)`.
