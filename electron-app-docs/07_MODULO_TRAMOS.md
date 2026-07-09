# 07 — Módulo Motor de Tramos (TramoEngine)

## Descripción

Evalúa en qué etapa del ciclo de **59 días por cuenta** se encuentra cada cliente (desde su `fecha_asignacion` del Excel) y determina qué cartas deben generarse. Los parámetros son configurables desde la BD.

---

## Ciclo de 59 días (por cuenta)

| Etapa | Nombre | Días | Acción |
|-------|--------|------|--------|
| 1 | Recuperación inicial | 1-10 | Contacto inicial, Carta 1 |
| 2 | Seguimiento medio | 11-43 | Seguimiento, Cartas 2 y 3 |
| 3 | Cierre de gestión | 44-59 | Presión máxima, Carta 4 y 5 |

- **Día 60**: cierre automático (`estado_ciclo = cerrada`).
- **Día 70** sin recupero: retorno al banco (`estado_ciclo = retornada_banco`).

---

## Calendario de cartas

| Carta | Código | Día | Tramo | Umbral saldo | Nombre |
|-------|--------|-----|-------|--------------|--------|
| 1 | E1-1 | 1 | 1 | Sin umbral (siempre) | Invitación a Reingreso |
| 2 | E1-2 | 9 | 1 | > S/ 40 | No Pierdas Ser Empresaria |
| 3 | E2-1 | 11 | 2 | > S/ 40 | Requerimiento de Pago |
| 4 | E2-2 | 35 | 2 | > S/ 40 | Insistimos en el Pago |
| 5 | E3-1 | 44 | 3 | > S/ 40 | Exigimos Pago — Pre Judicial |

---

## Reglas de exclusión

- Clientes con `importe_deuda_pendiente < S/ 10.00` → **excluidos** de tramos (no avanzan)
- Cartas 2-5 → solo si `importe_deuda_pendiente > S/ 40.00`
- Carta 1 → se genera para **todos** sin importar el saldo

---

## Lógica de evaluación

```typescript
function evaluateCliente(cliente: Cliente, diaCampana: number): TramoAction {
  // 1. Exclusión por saldo mínimo
  if (cliente.importe_deuda_pendiente < UMBRAL_MINIMO_GESTION) {
    return { excluded: true }
  }

  // 2. Determinar tramo según día
  const nuevoTramo = getTramoForDay(diaCampana)

  // 3. Detectar transición de tramo
  const transicion = nuevoTramo !== cliente.tramo_actual
    ? { anterior: cliente.tramo_actual, nuevo: nuevoTramo }
    : null

  // 4. Detectar cartas pendientes
  const cartasPendientes = []
  for (const [num, config] of Object.entries(CARTA_SCHEDULE)) {
    if (config.dia === diaCampana) {
      const omitida = config.requiere_umbral_alto
        && cliente.importe_deuda_pendiente <= UMBRAL_CARTA_FISICA
      cartasPendientes.push({ numero: num, omitida })
    }
  }

  return { transicion, cartasPendientes }
}
```

---

## Resultado de evaluación completa

```typescript
interface EvaluationResult {
  campanaId: string
  diaCampana: number
  fechaEvaluacion: Date
  transiciones: TramoTransition[]
  cartasPendientes: CartaPendiente[]
  clientesExcluidos: number   // saldo < 10
  clientesEvaluados: number
}

interface TramoTransition {
  clienteId: number
  codigoCliente: string
  tramoAnterior: number
  tramoNuevo: number
  diaCampana: number
  saldo: number
}

interface CartaPendiente {
  clienteId: number
  codigoCliente: string
  nombreCompleto: string
  numeroCarta: number
  tramo: number
  diaCampana: number
  saldo: number
  omitidaPorMonto: boolean  // true si saldo < 40 para cartas 2-5
}
```

---

## Parámetros configurables (ConfigCampana)

Todos los días y umbrales son editables desde la página de Configuración:

```typescript
interface ConfigCampana {
  tramo1_inicio: number  // default: 1
  tramo1_fin: number     // default: 8
  tramo2_inicio: number  // default: 9
  tramo2_fin: number     // default: 43
  tramo3_inicio: number  // default: 44
  tramo3_fin: number     // default: 60

  carta1_dia: number     // default: 1
  carta2_dia: number     // default: 9
  carta3_dia: number     // default: 11
  carta4_dia: number     // default: 35
  carta5_dia: number     // default: 44

  umbral_minimo_gestion: number  // default: 10.0
  umbral_carta_fisica: number    // default: 40.0
}
```

El motor carga la config de la BD al iniciar y actualiza sus constantes internas. Si la BD no está inicializada, usa los defaults hardcodeados.
