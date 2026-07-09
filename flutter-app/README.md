# App Recaudo Legal — Flutter

Aplicación Flutter para gestores de campo (APK Android + **portal web** en Firebase Hosting), conectada a Firebase (`clase-001`). Sustituye el antiguo `gestor-app` React en producción.

## Características

- **Login** con Firebase Authentication (email/contraseña)
- **Dashboard**: lista de clientes con búsqueda, filtros (todos/pendientes/visitados), estadísticas y barra de progreso del tramo
- **Detalle del Cliente**: información completa, tarjeta de deuda, captura GPS obligatoria, notas, 5 botones de estado con confirmación
- **Estadísticas**: gráfico de dona SVG, barras de progreso por sección, distribución departamental, KPIs
- **Admin**: CRUD de usuarios con roles (gestor, asistente, supervisor, admin)
- **Recorridos en campo** (admin/supervisor): mapa en vivo, trazas GPS por día, km recorridos y rutas planificadas del equipo (`Más` → Recorridos en campo)
- **Mis rutas** (gestor): rutas diarias guardadas desde el mapa de clientes
- **Offline**: persistence automática de Firestore en móvil
- **GPS obligatorio**: geolocator con manejo de permisos
- **Alertas**: creación automática para suplantación y pago no registrado
- **Indicador de conectividad**: barra naranja cuando no hay conexión
- **Indicador de deuda alta**: clientes con deuda >S/500 resaltados

## Prerequisitos

1. **Flutter SDK** ≥ 3.19  
   Instalar desde: https://docs.flutter.dev/get-started/install
2. **Firebase CLI** para configuración avanzada (opcional)
3. **Android Studio** o **VS Code** con extensión de Flutter

## Configuración Firebase

### Android
1. Ve a [Firebase Console](https://console.firebase.google.com/) → Proyecto `clase-001`
2. Agregar aplicación Android:
   - Nombre del paquete: `com.fym.recaudolegal`
3. Descargar `google-services.json`
4. Colocarlo en `android/app/google-services.json`

### iOS (opcional)
1. Agregar aplicación iOS en Firebase Console
2. Descargar `GoogleService-Info.plist`
3. Colocarlo en `ios/Runner/GoogleService-Info.plist`

### Web
Ya configurado con las credenciales del proyecto en `lib/config/firebase_config.dart`.

## Instalación

```bash
cd flutter-app
flutter pub get
```

## Ejecución

```bash
# Android
flutter run

# Web (desarrollo)
flutter run -d chrome

# iOS (solo en macOS)
flutter run -d ios
```

## Web — build y deploy (Firebase Hosting)

```powershell
flutter build web --release
cd ..
firebase deploy --only hosting
```

Detalle: [HOSTING-DEPLOY.md](../HOSTING-DEPLOY.md) en la raíz del repo.

**Nota:** en navegador el GPS/recorrido solo funciona con la pestaña abierta; en campo se recomienda la APK.

## Estructura del Proyecto

```
lib/
├── main.dart                   # Entry point + Firebase init
├── app.dart                    # MaterialApp + auth routing
├── config/
│   ├── firebase_config.dart    # Firebase credentials
│   └── theme.dart              # Material 3 theme + colors
├── models/
│   ├── client_model.dart       # Modelo de cliente
│   ├── user_model.dart         # Modelo de usuario
│   └── tracking_models.dart    # GestorLocation, TrailPoint, km
├── services/
│   ├── auth_service.dart       # Auth + profile resolution
│   ├── connectivity_service.dart
│   ├── campaign_service.dart   # Campaña activa + secciones
│   ├── firestore_service.dart  # CRUD Firestore + tracking admin
│   ├── tracking_service.dart   # GPS continuo (solo gestores)
│   ├── alert_service.dart      # Alertas suplantación/pago
│   └── location_service.dart   # GPS via geolocator
├── screens/
│   ├── login_screen.dart
│   ├── home_shell.dart         # Bottom navigation
│   ├── dashboard_screen.dart
│   ├── client_detail_screen.dart
│   ├── stats_screen.dart
│   ├── tracking_screen.dart    # Recorridos admin (mapa + km)
│   └── admin_screen.dart
└── widgets/
    ├── stat_card.dart
    └── client_list_tile.dart
```

## Firestore Collections

La app usa las mismas colecciones que el gestor-app web:

- `campañas/{id}` → metadata de campaña (tramo, día)
- `campañas/{id}/gestores/{seccion}/clientes/{codigo}` → clientes
- `usuarios/{id}` → perfiles de usuario
- `alertas/{auto-id}` → alertas de suplantación/pago
- `ubicaciones_gestores/{gestorUid}` → última posición GPS del gestor
- `ubicaciones_gestores/{gestorUid}/puntos/{id}` → histórico de puntos (auto + visitas)
- `rutas_diarias/{yyyy-MM-dd}_{gestorUid}` → ruta planificada del día (clientes seleccionados en mapa)

### Vista admin: recorridos

1. Iniciar sesión como **admin** o **supervisor**.
2. Ir a **Más** → **Recorridos en campo**.
3. Seleccionar fecha y gestor para ver traza GPS (km del día) y ruta planificada si existe.

El tracking continuo en segundo plano solo se activa para usuarios con rol **gestor** (permisos Android: ubicación + segundo plano).

## Dependencias Principales

| Paquete | Uso |
|---------|-----|
| firebase_core | Inicialización Firebase |
| firebase_auth | Autenticación |
| cloud_firestore | Base de datos |
| provider | State management |
| geolocator | GPS |
| permission_handler | Permisos del dispositivo |
| connectivity_plus | Detección online/offline |
| google_fonts | Tipografía Inter |
| flutter_animate | Animaciones fluidas |
