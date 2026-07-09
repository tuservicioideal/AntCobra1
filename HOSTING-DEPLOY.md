# Firebase Hosting — Landing + Portal gestores

El proyecto `clase-001` usa **dos sitios** de Firebase Hosting:

| Target | Sitio Firebase | Carpeta | URL |
|--------|--------------|---------|-----|
| `landing` | `clase-001` | `landing/` | https://clase-001.web.app |
| `gestores` | `gestores-clase-001` | `flutter-app/build/web` | https://gestores-clase-001.web.app |

## Configuración inicial (una sola vez)

Si el sitio secundario aún no existe en Firebase Console:

```powershell
firebase hosting:sites:create gestores-clase-001
firebase target:apply hosting landing clase-001
firebase target:apply hosting gestores gestores-clase-001
```

Los targets ya están definidos en [`.firebaserc`](.firebaserc).

## Deploy — Landing corporativa

```powershell
firebase deploy --only hosting:landing
```

Salida: carpeta [`landing/`](landing/) (HTML estático, sin build).

URLs:

- https://clase-001.web.app
- https://clase-001.firebaseapp.com

## Deploy — Portal gestores (Flutter Web)

```powershell
cd flutter-app
flutter build web --release
cd ..
firebase deploy --only hosting:gestores
```

Salida: `flutter-app/build/web`.

URLs:

- https://gestores-clase-001.web.app
- https://gestores-clase-001.firebaseapp.com

## Firebase Authentication

En [Firebase Console](https://console.firebase.google.com/) → proyecto **clase-001** → Authentication → **Dominios autorizados**, deben figurar al menos:

- `clase-001.web.app`
- `clase-001.firebaseapp.com`
- `gestores-clase-001.web.app`
- `gestores-clase-001.firebaseapp.com`
- `localhost` (desarrollo)

## APK en campo

Los gestores en calle deben usar la **APK** (`flutter build apk --release`) para GPS en segundo plano y mejor offline. La web complementa supervisores y uso ocasional desde navegador.

## Checklist de regresión (portal gestores web)

- [ ] Login email/contraseña (gestor, supervisor, admin)
- [ ] Dashboard: búsqueda, filtros, detalle cliente, estados + GPS
- [ ] Cartas JPG/Word: compartir/descargar en navegador
- [ ] Mapas y rutas (`flutter_map`)
- [ ] Admin usuarios / tracking equipo (roles permitidos)
- [ ] Indicador sin conexión

## Checklist de regresión (landing)

- [ ] Hero, servicios, FAQ y contacto visibles en móvil
- [ ] Enlaces `tel:`, WhatsApp y correo funcionan
- [ ] Mapa embebido carga correctamente
- [ ] `llms.txt` y `sitemap.xml` accesibles en la raíz
- [ ] JSON-LD válido (LegalService + FAQPage)
