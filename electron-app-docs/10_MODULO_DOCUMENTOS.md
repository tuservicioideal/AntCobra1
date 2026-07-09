# 10 — Módulo Documentos (Generación de Cartas Word)

## Descripción

Genera archivos `.docx` de cartas de cobranza para los clientes según el calendario de tramos. También genera el reporte final del día 60.

---

## Las 5 cartas de cobranza

| # | Código | Día | Título | Tono | Umbral |
|---|--------|-----|--------|------|--------|
| 1 | E1-1 | 1 | INVITACIÓN A REINGRESO | Amigable/motivacional | Sin umbral |
| 2 | E1-2 | 9 | NO PIERDAS SER EMPRESARIA | Motivacional/urgente | > S/ 40 |
| 3 | E2-1 | 11 | REQUERIMIENTO DE PAGO | Formal | > S/ 40 |
| 4 | E2-2 | 35 | INSISTIMOS EN EL PAGO | Formal/serio | > S/ 40 |
| 5 | E3-1 | 44 | EXIGIMOS PAGO — PRE JUDICIAL | Urgente/legal | > S/ 40 |

---

## Contenido de cada carta

### Carta 1 — Invitación a Reingreso (E1-1)
- **Tono**: Cálido, motivacional
- **Asunto**: "INVITACIÓN A REGULARIZAR SU SITUACIÓN DE PAGO"
- **Color título**: Índigo `#4F46E5`
- **Saludo**: "Nos complace saludarte... mantienes un saldo pendiente..."
- **Cierre**: Invita a coordinar con representante asignado

### Carta 2 — No Pierdas Ser Empresaria (E1-2)
- **Tono**: Motivacional con urgencia
- **Asunto**: "IMPORTANTE: MANTENER TU ESTATUS DE EMPRESARIA"
- **Color título**: Naranja `#EA580C`
- **Contenido**: Alerta sobre perder condición de empresaria activa

### Carta 3 — Requerimiento de Pago (E2-1)
- **Tono**: Formal
- **Asunto**: "REQUERIMIENTO FORMAL DE PAGO"
- **Color título**: Rojo oscuro
- **Contenido**: Requerimiento formal con monto específico

### Carta 4 — Insistimos en el Pago (E2-2)
- **Tono**: Formal/serio
- **Asunto**: "SEGUNDO REQUERIMIENTO DE PAGO"
- **Color título**: Rojo
- **Contenido**: Segunda advertencia, menciona consecuencias

### Carta 5 — Exigimos Pago Pre Judicial (E3-1)
- **Tono**: Urgente/legal
- **Asunto**: "EXIGENCIA DE PAGO — ETAPA PRE JUDICIAL"
- **Color título**: Rojo oscuro `#991B1B`
- **Contenido**: Última instancia antes de proceso judicial

---

## Modo Word (fase actual — marzo 2026)

**Alcance vigente:** solo generación **Word (.docx)** desde plantillas `.docx` subidas en admin-app (**Documentos → Plantillas Word**).

- **PDF** e **imagen (JPG)** están **temporalmente deshabilitados** en la UI de admin-app y en la APK Flutter.
- El motor de conversión Word→PDF→JPG sigue en código (`word_template_engine.py`) para una fase posterior.
- La APK genera cartas Word **localmente** descargando la plantilla desde Firebase Storage.

### Etiquetas soportadas (`{{TAG}}` en MAYÚSCULAS)

| Tag | Valor |
|-----|-------|
| `{{NOMBRE}}` | Nombre completo del cliente |
| `{{DNI}}` | Número de documento |
| `{{DIRECCION}}` | Dirección (calle, distrito, provincia) |
| `{{CODIGO}}` | Código de cliente |
| `{{ZONA}}` | Zona territorial |
| `{{SECCION}}` | Sección / clave compuesta |
| `{{CAMPANA}}` | Nombre de la campaña activa |
| `{{DEUDA}}` | Importe pendiente (formato `1,234.56`) |
| `{{CODIGO_PAGO}}` | Código de pago (usualmente = código cliente) |
| `{{FECHA}}` | Fecha de generación (español) |
| `{{FECHA_VENCIMIENTO}}` | Fecha de vencimiento o promesa de pago |
| `{{GESTOR_NOMBRE}}` | Nombre del gestor asignado |
| `{{GESTOR_CELULAR}}` | Teléfono del gestor |

### Cómo preparar plantillas en Microsoft Word

1. Escriba cada etiqueta como **texto continuo**, sin cambiar fuente, tamaño o color a mitad del tag.
2. Use el formato exacto `{{NOMBRE}}` — no `{NOMBRE}`, `[NOMBRE]` ni campos Word nativos (Combinar correspondencia).
3. Suba el `.docx` en **Documentos → Plantillas Word** (una plantilla por carta 1–5).
4. Al subir, la app analiza las etiquetas y advierte si hay tags no soportados.
5. Word suele partir tags en el XML interno; el motor fusiona texto por párrafo antes de reemplazar.

### Implementación técnica

| App | Módulo |
|-----|--------|
| admin-app | `services/word_template_engine.py`, `ui/pages/documents.py` |
| flutter-app | `lib/services/letter_word_service.dart`, `letter_template_cache_service.dart` |

---

## Estructura del documento Word

```
[Logo empresa — placeholder]
[Título de la carta]
[Subtítulo / código etapa]
[Ciudad y fecha]

Señor(a): {nombre_completo}
Dirección: {direccion}, {distrito} - {departamento}
Referencia: Código cliente {codigo_cliente}
Asunto: {asunto}

[Cuerpo con saludo específico de la carta]

Monto adeudado: S/ {importe_deuda_pendiente}
[Tabla: Deuda original | Abonos anteriores | Saldo pendiente]

[Cierre específico de la carta]

Atentamente,
[Nombre empresa]
[Datos de contacto gestor]
```

---

## Modo de generación

### Por sección (modo batch)
Genera una carta por cada cliente de una sección que cumpla los criterios.
- Carpeta salida: `{output_dir}/{campana_id}/carta_{n}/{seccion_key}/`
- Nombre archivo: `carta_{n}_{seccion_letra}_{codigo_cliente}.docx`

### Por cliente individual
Para regenerar cartas específicas.

---

## Reporte final (Día 60)

`generateFinalReport(campanaId, outputDir)`

Genera un `.docx` con:
- Resumen estadístico de la campaña
- Tabla de clientes por estado de gestión
- Distribución de tramos
- Total deuda recuperada vs pendiente
- Tabla por sección

---

## Extracción de letra de sección

```typescript
function seccionDisplay(seccionKey: string): string {
  // "01_1211_H" → "H"
  return seccionKey.includes("_")
    ? seccionKey.split("_").pop()!
    : seccionKey
}
```

---

## Datos del cliente en la carta

```typescript
interface LetterClientData {
  codigo_cliente: string
  nombre_completo: string
  direccion: string
  distrito: string
  departamento: string
  importe_deuda_pendiente: number
  importe_deuda_asignada: number
  importe_abonos_anteriores: number
  importe_deuda_original: number
  seccion_key: string
  // Datos del gestor asignado (opcional)
  gestor_nombre?: string
  gestor_telefono?: string
}
```

---

## Integración con Firebase Storage

Después de generar, la carta puede subirse a Firebase Storage:
- Path: `cartas_generadas/{campaign_id}/{seccion_key}/{gestor_uid}/{filename}`
- Metadata guardada en Firestore `cartas_generadas/{doc_id}` (sufijo `_jpg`, `_pdf`, `_docx` por formato)

### Publicación oficial (admin-app)

Desde **Campaña → Publicar cartas**, el flujo publica por cliente:
- **DOCX** editable (plantilla Word rellena con datos del cliente)

La plantilla se sincroniza a Firebase Storage (`plantillas_carta/carta_N.docx`) al subirla desde Documentos.

### Generación en APK Flutter

La APK descarga la plantilla desde Firebase, reemplaza `{{TAG}}` en el dispositivo y guarda un `.docx` local (Abrir / Compartir).

El flujo JPG legacy (`letter_jpg_*`, canvas programático) queda **oculto en la UI** hasta habilitar PDF/JPG desde Word.
