---
name: firebase-expert
description: 'Expert in Firebase and Firestore. USE FOR: Firestore data modeling, security rules, queries, indexes, real-time listeners; Firebase Auth (custom claims, roles); Firebase CLI (deploy, emulators, login, init, hosting); Firebase Admin SDK (Python, Node.js); Flutter Firebase integration (firebase_core, firebase_auth, cloud_firestore); Firebase Hosting deployment; cost optimization; debugging permission-denied errors; composite indexes; subcollection patterns. USE ALSO FOR: firestore.rules authoring and testing, .firebaserc configuration, multi-environment projects, offline persistence, pagination with cursors, batch writes and transactions.'
argument-hint: 'Describe the Firebase/Firestore task: e.g. "add security rule for X", "model collection Y", "deploy to hosting", "fix permission denied"'
---

# Firebase Expert Skill

## Workspace Context (AntCobranzas)

This project has three apps sharing a single Firebase project:

| App | Tech | Firebase usage |
|-----|------|----------------|
| `admin-app/` | Python | Admin SDK — campaign load, user management |
| `flutter-app/` | Flutter/Dart | Auth + Firestore (gestor field app) |
| `gestor-app/` | React/Vite | Web console, deployed to Firebase Hosting |

Key files:
- [`firebase.json`](../../../firebase.json) — Hosting target (`gestor-app/dist`) + Firestore rules path
- [`firestore.rules`](../../../firestore.rules) — Role-based rules (admin, supervisor, asistente, gestor)
- [`admin-app/services/firebase_service.py`](../../../admin-app/services/firebase_service.py) — Admin SDK wrapper
- [`flutter-app/lib/services/`](../../../flutter-app/lib/services/) — Flutter Firebase services

Firestore collection hierarchy:
```
campañas/{campaignId}
  └── gestores/{seccionId}
        └── clientes/{clienteId}
usuarios/{userId}
```

Roles (stored in `usuarios/{uid}.rol`): `admin`, `supervisor`, `asistente`, `gestor`

---

## 1  Firestore Data Modeling

### Principles
- **Flatten for reads** — embed data you always read together; subcollection only when data is accessed independently or grows unboundedly.
- **One document ≤ 1 MB** — keep arrays/maps bounded; move large lists to subcollections.
- **Avoid deep nesting** — 3 levels max (this project: campañas → gestores → clientes).
- **Prefix collections by domain** — use singular names consistently.

### Patterns used in this project
```
// Batch-load all clients for a section
db.collection('campañas').doc(campaignId)
  .collection('gestores').doc(seccionId)
  .collection('clientes')

// User profile lookup (used in security rules)
db.collection('usuarios').doc(uid)
```

### Timestamps
Always use `FieldValue.serverTimestamp()` (JS/Dart) or `firestore.SERVER_TIMESTAMP` (Python Admin SDK) — never the client clock.

---

## 2  Security Rules

### Template (role-based, matches this project)
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    function isAuth() { return request.auth != null; }

    function userDoc() {
      return get(/databases/$(database)/documents/usuarios/$(request.auth.uid)).data;
    }

    function hasRole(roles) { return isAuth() && userDoc().rol in roles; }

    function isAdmin()           { return hasRole(['admin']); }
    function isAdminOrSupervisor() { return hasRole(['admin','supervisor']); }
    function isActiveUser()      { return isAuth() && userDoc().activo == true; }
    function getUserSection()    { return userDoc().seccion; }

    // ---------- Rules ----------
    match /usuarios/{uid} {
      allow read:  if isAuth();
      allow write: if isAuth() && (request.auth.uid == uid || isAdminOrSupervisor());
    }

    match /campañas/{campaignId}/gestores/{seccionId}/clientes/{clienteId} {
      allow read:   if isActiveUser();
      allow create: if isAdminOrSupervisor();
      allow update: if isActiveUser() && (isAdminOrSupervisor() || getUserSection() == seccionId);
      allow delete: if isAdmin();
    }
  }
}
```

### Debugging `permission-denied`
1. Check `request.auth` is not null (user is signed in).
2. Verify the user document exists at `usuarios/{uid}` and has correct `rol` and `activo` fields.
3. Use **Firebase Emulator Suite** to replay the exact request.
4. Add `allow read: if true;` temporarily to isolate whether the issue is auth or data.
5. Use the **Rules Playground** in Firebase Console (specify auth UID + path + operation).

### Testing rules locally
```bash
firebase emulators:start --only firestore
# then run: firebase emulators:exec --only firestore "npx jest"
```

---

## 3  Firebase CLI

### Essential commands
```bash
# Authenticate
firebase login
firebase login --reauth           # force re-auth

# Project management
firebase projects:list
firebase use <project-id>         # switch active project
firebase use --add                # add alias (e.g. staging, prod)

# Deploy
firebase deploy                   # deploy everything in firebase.json
firebase deploy --only hosting    # only Hosting (gestor-app/dist)
firebase deploy --only firestore:rules
firebase deploy --only firestore:indexes

# Emulators
firebase emulators:start          # all emulators
firebase emulators:start --only firestore,auth
firebase emulators:export ./emulator-data   # persist seed data
firebase emulators:start --import ./emulator-data

# View logs
firebase functions:log
```

### `.firebaserc` structure
```json
{
  "projects": {
    "default": "clase-001",
    "staging": "clase-001-staging"
  },
  "targets": {}
}
```

### Hosting deployment workflow (this project)
```bash
cd gestor-app
npm run build          # outputs to dist/
cd ..
firebase deploy --only hosting
```

---

## 4  Firebase Admin SDK — Python

### Initialization pattern (`admin-app/`)
```python
import firebase_admin
from firebase_admin import credentials, firestore, auth

# Initialize once (guard against re-initialization)
if not firebase_admin._apps:
    cred = credentials.Certificate("clase-001-firebase-adminsdk-fbsvc-ee190f0bcc.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()
```

### Common operations
```python
# Read a document
doc = db.collection('campañas').document(campaign_id).get()
data = doc.to_dict()

# Write / merge
db.collection('usuarios').document(uid).set({'rol': 'gestor', 'activo': True}, merge=True)

# Subcollection batch write
batch = db.batch()
for cliente in clientes:
    ref = (db.collection('campañas').document(campaign_id)
             .collection('gestores').document(seccion_id)
             .collection('clientes').document(cliente['id']))
    batch.set(ref, cliente)
batch.commit()

# Query
docs = (db.collection('campañas').document(campaign_id)
          .collection('gestores').document(seccion_id)
          .collection('clientes')
          .where('estado', '==', 'pendiente')
          .stream())

# Create Auth user
user = auth.create_user(email=email, password=pwd, display_name=name)
auth.set_custom_user_claims(user.uid, {'rol': 'gestor'})
```

### Error handling
```python
from firebase_admin import exceptions
try:
    doc = ref.get()
except exceptions.NotFoundError:
    ...
except exceptions.FirebaseError as e:
    print(e.code, e.message)
```

---

## 5  Flutter Firebase Integration

### Dependencies (`pubspec.yaml`)
```yaml
dependencies:
  firebase_core: ^3.x.x
  firebase_auth: ^5.x.x
  cloud_firestore: ^5.x.x
```

### Initialization (`main.dart`)
```dart
await Firebase.initializeApp(
  options: DefaultFirebaseOptions.currentPlatform,
);
```

### Auth
```dart
// Sign in
final cred = await FirebaseAuth.instance
    .signInWithEmailAndPassword(email: email, password: password);

// Current user
final user = FirebaseAuth.instance.currentUser;

// Auth state stream
FirebaseAuth.instance.authStateChanges().listen((user) { ... });
```

### Firestore reads
```dart
final db = FirebaseFirestore.instance;

// One-time read
final snap = await db
    .collection('campañas').doc(campaignId)
    .collection('gestores').doc(seccionId)
    .collection('clientes')
    .where('estado', isEqualTo: 'pendiente')
    .get();

// Real-time listener
db.collection('usuarios').doc(uid).snapshots().listen((snap) {
  final data = snap.data();
});
```

### Offline persistence (Flutter)
```dart
// Enabled by default on mobile. For web:
db.settings = const Settings(persistenceEnabled: true);
```

---

## 6  Firestore Indexes

Composite indexes are required when a query:
- Filters on one field **and** orders by a different field, OR
- Uses `where` on two or more different fields simultaneously.

### Create via CLI
```bash
# firestore.indexes.json
{
  "indexes": [
    {
      "collectionGroup": "clientes",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "estado",    "order": "ASCENDING" },
        { "fieldPath": "updatedAt", "order": "DESCENDING" }
      ]
    }
  ]
}
```
```bash
firebase deploy --only firestore:indexes
```

### Quick index from error
When Dart/Flutter throws a "requires an index" error, the error message includes a direct URL to create the index in the console — just click it.

---

## 7  Pagination

```dart
// First page
final first = await db.collection('clientes')
    .orderBy('apellido')
    .limit(20)
    .get();

// Next page — pass last document as cursor
final next = await db.collection('clientes')
    .orderBy('apellido')
    .startAfterDocument(first.docs.last)
    .limit(20)
    .get();
```

---

## 8  Batch Writes & Transactions

```dart
// Batch (up to 500 ops)
final batch = db.batch();
batch.set(db.collection('clientes').doc(id), data);
batch.update(db.collection('campañas').doc(cid), {'total': FieldValue.increment(1)});
await batch.commit();

// Transaction (read-then-write consistent)
await db.runTransaction((tx) async {
  final snap = await tx.get(ref);
  final current = snap['saldo'] as num;
  tx.update(ref, {'saldo': current - monto});
});
```

---

## 9  Cost & Quota Checklist

- [ ] Add `.limit()` to ALL queries — never fetch unbounded collections.
- [ ] Use `select()` (Python) / `withConverter` + field masks (Dart) to fetch only needed fields.
- [ ] Cache user role/profile in app state; avoid repeated `get()` on `usuarios/{uid}`.
- [ ] Avoid real-time listeners on large collections unless truly needed.
- [ ] Use `merge: true` (Python) / `SetOptions(merge: true)` (Dart) instead of overwriting docs.
- [ ] Batch writes when loading bulk data (Excel → Firestore).
- [ ] Enable Firestore budget alerts in GCP console.

---

## 10  Common Errors & Fixes

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `PERMISSION_DENIED` | Rule mismatch or missing `usuarios/{uid}` doc | Check rule helpers, verify user doc exists |
| `NOT_FOUND` | Wrong collection/doc path | Log the path being queried |
| `FAILED_PRECONDITION: index required` | Composite query without index | Deploy the index or click the URL in the error |
| `RESOURCE_EXHAUSTED` | Quota exceeded | Add `.limit()`, check reads in GCP console |
| `UNAUTHENTICATED` | Token expired or not initialized | Re-authenticate, check `Firebase.initializeApp` ran |
| `firebase deploy` 401 | Token expired | Run `firebase login --reauth` |
| Hosting shows old version | Browser cache | Hard-refresh or clear cache; verify `dist/` was rebuilt |

---

## References

- [Firestore rules reference](./references/firestore-rules.md)
- [Firebase CLI reference](./references/firebase-cli.md)
