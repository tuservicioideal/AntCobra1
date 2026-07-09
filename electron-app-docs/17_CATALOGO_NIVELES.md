# 17 — Catálogo de Niveles de Gestión (Niveles 1-4)

## Descripción

Sistema de clasificación jerárquica de 4 niveles que los gestores usan para registrar el resultado de cada gestión. Tiene 2 canales: **CAM** (campo) y **TEL** (call center).

---

## Catálogo completo

El archivo fuente es: `admin-app/data/catalogo_niveles_PE.json`

### Canal CAM (Campo)

#### Nivel 1: Contacto efectivo
| Nivel 2 | Nivel 3 | Nivel 4 |
|---------|---------|---------|
| Promesa de pago | Promesa total | CAM Promesa total |
| Promesa de pago | Promesa parcial | CAM Promesa parcial |
| Renuente | Cliente renuente | CAM Cliente renuente |
| Fallecido | Cliente fallecido | CAM Cliente fallecido |
| Inubicable | Cliente inubicable | CAM Cliente inubicable |
| Disputa de saldo | Disputa de saldo | CAM Disputa de saldo |

#### Nivel 1: Contacto no efectivo
| Nivel 2 | Nivel 3 | Nivel 4 |
|---------|---------|---------|
| No contacto directo | Ausente temporal | CAM Ausente temporal |
| No contacto directo | Dirección incorrecta | CAM Dirección incorrecta |
| No contacto directo | No responde | CAM No responde |

#### Nivel 1: No contacto
| Nivel 2 | Nivel 3 | Nivel 4 |
|---------|---------|---------|
| No contacto total | No se encontró | CAM No se encontró |
| No contacto total | Zona de riesgo | CAM Zona de riesgo |

---

### Canal TEL (Call Center)

#### Nivel 1: Contacto efectivo
| Nivel 2 | Nivel 3 | Nivel 4 |
|---------|---------|---------|
| Promesa de pago | Promesa total | TEL Promesa total |
| Promesa de pago | Promesa parcial | TEL Promesa parcial |
| Renuente | Cliente renuente | TEL Cliente renuente |
| Fallecido | Cliente fallecido | TEL Cliente fallecido |
| Inubicable | Sin número válido | TEL Sin número válido |

#### Nivel 1: Contacto no efectivo
| Nivel 2 | Nivel 3 | Nivel 4 |
|---------|---------|---------|
| No contacto directo | Buzón de voz | TEL Buzón de voz |
| No contacto directo | Número equivocado | TEL Número equivocado |
| No contacto directo | Llamada fallida | TEL Llamada fallida |

#### Nivel 1: No contacto
| Nivel 2 | Nivel 3 | Nivel 4 |
|---------|---------|---------|
| No contacto total | Sin cobertura | TEL Sin cobertura |
| No contacto total | Rechazó llamada | TEL Rechazó llamada |

---

## Mapeo Nivel → EstadoGestion

```typescript
function mapNivelToEstado(nivel1: string): EstadoGestion {
  if (nivel1 === "Contacto efectivo") return "visitado_habido"
  if (nivel1 === "Contacto no efectivo") return "visitado_no_habido"
  if (nivel1 === "No contacto") return "visitado_no_habido"
  return "pendiente"
}
```

---

## Estados especiales (botones separados en los apps)

| Estado | Descripción |
|--------|-------------|
| `suplantacion` | Persona en domicilio no es el titular |
| `pago_no_registrado` | Cliente afirma haber pagado pero no aparece en sistema |

Estos estados se registran directamente sin pasar por los niveles 1-4.

---

## Cascada en la UI

Los 4 dropdowns son en cascada: seleccionar Nivel 1 filtra los Nivel 2, y así sucesivamente.

```typescript
// Estructura del catálogo JSON
interface NivelCatalog {
  [canal: string]: {  // "CAM" | "TEL"
    [nivel1: string]: {
      [nivel2: string]: {
        [nivel3: string]: string[]  // array de nivel4
      }
    }
  }
}
```

---

## Montos de gestión monetaria (APK / PWA)

Firestore y SQLite usan `fecha_promesa_pago` y `monto_promesa_pago` para **promesas, pagos reportados y cancelaciones**. En la APK (`GestionMontoRules`) el panel de importe aparece cuando:

| Condición en niveles | Fecha en UI | Etiqueta monto |
|----------------------|-------------|----------------|
| `nivel_2` contiene «promesa» | Sí si es «Promesa de pago» o «Recordar promesa» | Monto prometido |
| `nivel_2` contiene «Cliente cancelo» | No | Monto pagado |
| `nivel_3` / `nivel_4` contiene «Pago a socia», «Pago a cobrador» o «Pago a gerente» | No | Monto pagado |
| Estado especial «Pago no registrado» | No | Fila opcional debajo de estados especiales |

Ningún campo es obligatorio: el gestor puede registrar la gestión sin monto ni fecha.

---

## Dónde se usa el catálogo

| App | Implementación |
|-----|---------------|
| admin-app (Python) | `catalogo_niveles_PE.json` cargado en `team.py` |
| gestor-app (React) | `catalogService.js` con cascading selects |
| flutter-app | `NivelCatalogService` con `DropdownButtonFormField` |
| **electron-app** (nuevo) | Cargar JSON desde `resources/`, cascading dropdowns en UI |

El catálogo se puede almacenar en `resources/catalogo_niveles_PE.json` en el proyecto Electron y leerlo desde Main o bundlearlo en el renderer.
