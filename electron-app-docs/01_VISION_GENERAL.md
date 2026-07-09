# 01 — Visión General del Sistema

## Propósito

**AntCobranzas** es una aplicación de escritorio para empresas de cobranza externa que trabajan para entidades bancarias. Gestiona carteras de clientes deudores con un ciclo de 60 días dividido en 3 tramos, coordina equipos de gestores de campo y call center, genera cartas de cobranza y reportes para el banco.

---

## Usuarios del sistema

| Rol | Descripción | Accesos |
|-----|-------------|---------|
| `admin` | Administrador total | Todo |
| `supervisor` | Supervisa equipo, ve stats, distribuye | Todo menos cambiar config crítica |
| `asistente` | Ve monitor, estadísticas, genera cartas | Sin gestión de usuarios ni subida |
| `gestor` | Gestor de campo/call (solo apps móvil/web) | Solo app Flutter / gestor-web |

---

## Apps del ecosistema

```
AntCobra1/
├── admin-app/         → Desktop Python/tkinter (a reemplazar con Electron)
├── gestor-app/        → Web React (Vite) para gestores de call center
└── flutter-app/       → Móvil iOS/Android para gestores de campo
```

---

## Flujo operativo macro

```
1. El banco entrega un archivo Excel con la cartera de deudores
2. Admin/Supervisor carga el Excel en el desktop app
3. El sistema parsea y guarda en SQLite local (fuente de verdad)
4. Se asignan secciones a gestores del equipo
5. Se sube la cartera a Firestore (incluye DNI para operación call/campo)
6. Los gestores (campo y call) gestionan clientes en sus apps
7. El desktop app monitorea visitas en tiempo real
8. En días específicos (1, 9, 11, 35, 44) se generan cartas Word
9. Al cierre (día 60) se exporta el resultado en Excel para el banco
```

---

## Conceptos clave

### Cartera activa
- Siempre hay **una sola cartera activa** en Firestore (`campañas/cartera_activa`)
- Re-subir el Excel actualiza la cartera existente (idempotente)
- Los datos de visita de gestores se **preservan** al re-subir

### Sección (clave operativa principal)
- Cada cliente pertenece a una sección
- La sección se asigna a UN gestor
- La clave de sección es **compuesta**: `{region}_{zona}_{seccion}` → ej. `01_1211_H`
- La misma letra puede repetirse en distintas regiones/zonas

### Tramos
- **Tramo 1** (Días 1-8): Cobranza Normal
- **Tramo 2** (Días 9-43): Seguimiento Medio
- **Tramo 3** (Días 44-60): Cierre de Gestión

### Umbrales monetarios
- `< S/ 10`: excluido de gestión activa
- `> S/ 40`: recibe cartas físicas (Cartas 2-5)
- `> S/ 500`: marcado como "alto valor"

---

## Criterios de datos operativos

- El **DNI** (`numero_documento`) se guarda en SQLite (cartera del banco) y **también se sube a Firestore** para que gestores call y campo puedan operar con identificación completa.
- Los campos de gestión (estado, nota, GPS) los escriben los gestores y se sincronizan hacia SQLite.

---

## Firebase Project

- **Proyecto**: `clase-001`
- **Account propietaria**: `tuservicioideal.com@gmail.com`
- **Auth API Key**: `AIzaSyBubpxyyN2YvcPaU6WUJkrF2IQUOzFVYWg`
- **Storage Bucket**: `clase-001.firebasestorage.app`
