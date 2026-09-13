# Pruebas E2E — AntCobranzas

## Credenciales locales

1. Copia [e2e/.env.example](.env.example) a la **raíz del repo** como `.env.e2e.local`.
2. Completa email/password (el archivo real **no** se sube a git).

Cuentas de laboratorio típicas (rellenar en `.env.e2e.local`):

| Rol | Variable |
|-----|----------|
| Admin | `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` |
| Gestor | `E2E_GESTOR_EMAIL` / `E2E_GESTOR_PASSWORD` |

Portal web gestores: https://gestores-clase-001.web.app  
Admin back-office: app desktop `admin-app` (CustomTkinter) — **no** es Playwright; se prueba con pytest.

## Playwright (portal Flutter Web)

Flutter Web (CanvasKit) no expone el DOM hasta activar semantics. Los specs hacen click en **Enable accessibility** antes de llenar el formulario.

```powershell
cd AntCobra1
npm install
npx playwright install chromium
npm run test:e2e
```

Specs en `e2e/*.spec.ts`. Credenciales: `.env.e2e.local` en la raíz (gitignored).

## Pytest (reparto call / fase)

```powershell
cd AntCobra1/admin-app
python -m pytest tests/test_fase_reparto.py tests/test_arrastre_dni_payload.py test_call_distribution.py tests/test_reparto_planner.py -q
```
