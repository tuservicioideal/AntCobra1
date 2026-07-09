"""
Template Engine — Carta de Cobranza
=====================================
Manages letter templates stored in the DB, replaces {{TAGS}}, and parses
the simple markup format used by the template editor.

Markup syntax (plain text, editable by the user):
  - First non-empty line       → TITLE  (red, bold, centered, large)
  - {{TAG}}                    → replaced with client / gestor / campaign data
  - **text**                   → bold
  - *text*                     → italic
  - [ROJO]text[/ROJO]          → red coloured text
  - [CENTRO]text[/CENTRO]      → center-aligned paragraph
  - [LISTA]text[/LISTA]  OR  • text → bullet point
  - [FIRMA]text[/FIRMA]        → bold + centered (signature block)
  - [NOTA]text[/NOTA]          → small font (footer / disclaimer)
  - Blank line                 → paragraph separator
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# ── Supported placeholder tags ──────────────────────────────────

TAGS: dict[str, str] = {
    "NOMBRE":            "Nombre completo del cliente",
    "DNI":               "Número de DNI del cliente",
    "DIRECCION":         "Dirección del cliente",
    "CODIGO":            "Código del cliente",
    "ZONA":              "Zona del cliente",
    "SECCION":           "Sección del cliente",
    "CAMPANA":           "Campaña actual",
    "DEUDA":             "Importe de deuda pendiente (S/)",
    "CODIGO_PAGO":       "Código de pago del cliente",
    "FECHA":             "Fecha de la carta  (ej. 27 de abril de 2026)",
    "FECHA_VENCIMIENTO": "Fecha de vencimiento de la deuda",
    "GESTOR_NOMBRE":     "Nombre del gestor / encargado",
    "GESTOR_CELULAR":    "Celular del gestor encargado",
}

# ── Default templates (content faithful to the original letters) ─

DEFAULT_TEMPLATES: dict[int, str] = {
    # ── E1-1 ────────────────────────────────────────────────────
    1: """\
INVITACIÓN A REINGRESO
Lima, {{FECHA}}

Estimado(a) Consultor(a):
{{NOMBRE}}
DNI: {{DNI}}

Reciba un cordial saludo.

Nos comunicamos con usted en representación del prestigioso grupo empresarial **BELCORP**, casa matriz de las reconocidas marcas *Ésika, L'Bel y Cyzone*, con el propósito de invitarle a retomar su desarrollo empresarial y continuar creciendo junto a nosotros.

Sabemos el valor de su participación dentro de nuestra red y, por ello, queremos brindarle una oportunidad exclusiva de [ROJO]reingreso inmediato[/ROJO], permitiéndole reincorporarse a la próxima campaña activa y seguir generando ingresos dentro de su modelo de negocio.

Para facilitar este proceso, ponemos a su disposición una **condición preferencial de regularización**, mediante la cancelación de su saldo pendiente por el importe de **S/ {{DEUDA}}**, sin recargos adicionales, lo cual le permitirá restablecer su código y acceder nuevamente a todos los beneficios comerciales.

Puede realizar su pago de manera rápida y segura a través de:
• Banca por Internet
• Billeteras digitales
• Aplicaciones móviles bancarias
• Tarjeta de crédito o débito en la plataforma oficial

[CENTRO]**CÓDIGO DE PAGO: {{CODIGO_PAGO}}  DEUDA PENDIENTE: S/ {{DEUDA}}**[/CENTRO]

Este es el momento ideal para retomar sus objetivos, aprovechar nuevas oportunidades comerciales y seguir construyendo su crecimiento personal y financiero con una empresa líder en el mercado.

Agradecemos su atención y confianza, y estamos seguros de que tomará la mejor decisión para su futuro.

Atentamente,

[FIRMA]RECAUDO LEGAL & ABOGADOS[/FIRMA]
📱 WhatsApp: 942 470 641
📧 Email: recaudolegal@yahoo.com

[NOTA]Nota: Si al momento de recibir esta comunicación usted ya realizó el pago correspondiente, sírvase omitir este mensaje. Para consultas adicionales, puede comunicarse al contact center de Belcorp esikaperu@esika.biz o llamando – de lunes a viernes de 8 am a 8 pm y los sábados de 8 am a 6 pm – al 211-3614 (Lima o celular) o 080-11-3030 (provincia). El portador de esta carta NO está autorizado a recibir el dinero.[/NOTA]
""",

    # ── E1-2 ────────────────────────────────────────────────────
    2: """\
NO PIERDAS SER EMPRESARIA
Lima, {{FECHA}}

Estimado(a) Consultor(a):
{{NOMBRE}}
DNI: {{DNI}}

Reciba un cordial saludo.

Hace unos días nos comunicamos con usted para extenderle una invitación especial de parte del prestigioso grupo empresarial BELCORP, representante de las reconocidas marcas *Ésika, L'Bel y Cyzone*. Hoy queremos reiterarle esta oportunidad, porque sabemos que su potencial empresarial aún tiene mucho por desarrollarse.

Su participación dentro de nuestra red es valiosa, y por ello queremos brindarle una [ROJO]segunda oportunidad de reingreso[/ROJO], permitiéndole retomar sus actividades comerciales y continuar construyendo su crecimiento personal y económico.

Para concretar este proceso, solo es necesario regularizar su saldo pendiente por el importe de **S/ {{DEUDA}}**, utilizando su:

[CENTRO]**CÓDIGO DE PAGO: {{CODIGO_PAGO}}  DEUDA PENDIENTE S/ {{DEUDA}}**[/CENTRO]

Podrá realizar el pago de manera rápida y segura a través de:
• Banca por internet
• Billeteras digitales
• Aplicaciones móviles
• Tarjeta de crédito o débito en la web oficial

Una vez efectuado el pago, nuestro equipo coordinará directamente con usted su [ROJO]reincorporación inmediata al área comercial[/ROJO], permitiéndole acceder nuevamente a campañas, incentivos y beneficios exclusivos.

Esta es una oportunidad que no solo le permitirá retomar su actividad, sino también **fortalecer su independencia económica y su desarrollo personal como empresaria**.

No deje pasar esta oportunidad. Su regreso puede marcar un nuevo comienzo.

Atentamente,

[FIRMA]RECAUDO LEGAL & ABOGADOS[/FIRMA]
📱 WhatsApp: 942 470 641
📧 Email: recaudolegal@yahoo.com

[NOTA]Nota: Si al momento de recibir esta comunicación usted ya realizó el pago correspondiente, sírvase omitir este mensaje. Para consultas adicionales, puede comunicarse al contact center de Belcorp, escribiendo a esikaperu@esika.biz o llamando – de lunes a viernes de 8 am a 8 pm y los sábados de 8 am a 6 pm – al 211-3614 (Lima o celular) o 080-11-3030 (provincia). El portador de esta carta NO está autorizado a recibir el dinero.[/NOTA]
""",

    # ── E2-1 ────────────────────────────────────────────────────
    3: """\
REQUERIMIENTO DE PAGO
Lima, {{FECHA}}

Estimado(a) Consultor(a):
Señor(a): {{NOMBRE}}  DNI: {{DNI}}
Dirección: {{DIRECCION}}
Código: {{CODIGO}}  Zona: {{ZONA}}  Sección: {{SECCION}}  Campaña: {{CAMPANA}}

Reciba un cordial saludo.

Nos dirigimos a usted en relación a las comunicaciones previas sobre su **invitación de reingreso al sistema empresarial de BELCORP**, representante de las reconocidas marcas *Ésika, L'Bel y Cyzone*. Nuestro interés ha sido brindarle alternativas para su continuidad comercial; sin embargo, a la fecha su cuenta mantiene un saldo pendiente.

De acuerdo a nuestros registros, usted presenta una deuda por el importe de **S/ {{DEUDA}}**, correspondiente al pedido realizado el {{FECHA_VENCIMIENTO}}, cuyo vencimiento se produjo el día {{FECHA_VENCIMIENTO}}.

Entendemos que pueden presentarse situaciones imprevistas; no obstante, es importante que pueda **regularizar esta obligación a la brevedad**, a fin de evitar consecuencias que puedan afectar su historial financiero.

En ese sentido, le solicitamos efectuar el pago dentro de un [ROJO]plazo máximo de 72 horas[/ROJO], a fin de evitar el **reporte de su cuenta a centrales de riesgo**, tales como *Infocorp* y la *Cámara de Comercio de Lima*, lo cual podría limitar su acceso a créditos en el sistema financiero y comercial.

Para su comodidad, puede realizar el pago a través de:
• Banca por internet
• Billeteras digitales (incluyendo Yape)
• Aplicaciones móviles bancarias
• Tarjeta de crédito o débito en la web oficial

Una vez realizado el pago, le agradeceremos informarlo para gestionar la actualización de su estado y brindarle orientación respecto a su posible reingreso.

Nuestro equipo se encuentra a su disposición para acompañarlo en este proceso y absolver cualquier consulta.

Atentamente,

[FIRMA]RECAUDO LEGAL & ABOGADOS[/FIRMA]
📧 Email: recaudolegal@yahoo.com
📱 WhatsApp: 942 470 641

[NOTA]Nota: Si al momento de recibir esta carta usted ya hubiera cancelado la deuda, sírvase no considerar este aviso. En caso tenga alguna duda o reclamo puede comunicarse al contact center escribiendo a esikaperu@esika.biz o llamando – de lunes a viernes de 8 am a 8 pm y los sábados de 8 am a 6 pm – al 211-3614 (Lima o celular) o 080-11-3030 (provincia). El portador de esta carta NO está autorizado a recibir el dinero.[/NOTA]
""",

    # ── E2-2 ────────────────────────────────────────────────────
    4: """\
INSISTENCIA DE PAGO – REQUERIMIENTO URGENTE
Lima, {{FECHA}}

Señor(a): {{NOMBRE}}  DNI: {{DNI}}
Dirección: {{DIRECCION}}
Código: {{CODIGO}}  Zona: {{ZONA}}  Sección: {{SECCION}}  Campaña: {{CAMPANA}}  Deuda pendiente: S/ {{DEUDA}}

Estimado(a) Consultor(a):

Reciba un cordial saludo.

Nos dirigimos a usted en relación a su **obligación pendiente de pago** correspondiente a los productos del grupo BELCORP (*Ésika, L'Bel y Cyzone*), la cual, a la fecha, permanece impaga pese a las comunicaciones previas.

Entendemos que pueden existir circunstancias que hayan retrasado su cumplimiento; sin embargo, es importante señalar que su cuenta **ya registra acciones en centrales de riesgo**, tales como *Infocorp* y la *Cámara de Comercio de Lima*, lo cual impacta directamente en su capacidad de acceso a créditos en el sistema financiero y comercial.

En ese sentido, y con la finalidad de evitar mayores afectaciones, le solicitamos regularizar el pago total de su deuda por el importe de **S/ {{DEUDA}}**, dentro de un [ROJO]plazo máximo de 48 horas[/ROJO].

Puede realizar su pago de manera rápida y segura a través de:
• Banca por internet
• Billeteras digitales (incluyendo Yape)
• Aplicaciones móviles bancarias
• Tarjeta de crédito o débito en la web oficial

Una vez efectuado el pago, procederemos con la **actualización de su estado** y podrá gestionar su constancia de no adeudo, restableciendo progresivamente su condición en el sistema.

**Este es el momento oportuno para regularizar su situación y evitar mayores consecuencias.**

Agradecemos su pronta atención a la presente.

Atentamente,

[FIRMA]RECAUDO LEGAL & ABOGADOS[/FIRMA]
📧 Email: recaudolegal@yahoo.com
📱 WhatsApp: 942 470 641
Encargado: {{GESTOR_NOMBRE}}
Celular: {{GESTOR_CELULAR}}

[NOTA]Nota: Si al momento de recibir esta carta usted ya hubiera cancelado la deuda, sírvase no considerar este aviso. En caso tenga alguna duda o reclamo puede comunicarse al contact center escribiendo a esikaperu@esika.biz o llamando – de lunes a viernes de 8 am a 8 pm y los sábados de 8 am a 6 pm – al 211-3614 (Lima o celular) o 080-11-3030 (provincia). El portador de esta carta NO está autorizado a recibir el dinero.[/NOTA]
""",

    # ── E3-1 ────────────────────────────────────────────────────
    5: """\
EXIGIMOS PAGO – ETAPA PRE-JUDICIAL
Lima, {{FECHA}}

Señor(a): {{NOMBRE}}  DNI: {{DNI}}
Dirección: {{DIRECCION}}
Código: {{CODIGO}}  Zona: {{ZONA}}  Sección: {{SECCION}}  Campaña: {{CAMPANA}}  Deuda pendiente: S/ {{DEUDA}}

Estimado(a) Consultor(a):

Por medio de la presente, nos dirigimos a usted en relación a la **obligación pendiente de pago** que mantiene con CETCO S.A. – BELCORP (*Ésika, L'Bel y Cyzone*), la cual, a la fecha, permanece impaga pese a las reiteradas comunicaciones previas.

Es importante informarle que su cuenta **ha sido reportada a las principales centrales de riesgo**, tales como *Infocorp* y la *Cámara de Comercio de Lima*, afectando directamente su historial crediticio y limitando su acceso a financiamiento en el sistema bancario y comercial.

En ese sentido, y como **última instancia previa al inicio de acciones judiciales**, le requerimos formalmente proceder con la cancelación total de su deuda por el importe de **S/ {{DEUDA}}**, dentro de un [ROJO]plazo máximo e improrrogable de 48 horas[/ROJO].

De no regularizar su situación dentro del plazo indicado, su cuenta será derivada a nuestra área de **cobranzas judiciales**, lo que implicará:
• Incremento de gastos legales y administrativos
• Acciones legales correspondientes para la recuperación de la deuda
• Mayor afectación a su historial financiero

Para evitar dichas consecuencias, puede realizar su pago de forma inmediata a través de:
• Banca por internet
• Billeteras digitales (incluyendo Yape)
• Aplicaciones móviles bancarias
• Tarjeta de crédito o débito en la web oficial

Una vez efectuado el pago, se procederá a la **regularización de su estado**, permitiéndole gestionar su constancia de no adeudo y avanzar en la normalización de su historial crediticio.

Le recomendamos atender el presente requerimiento con la debida urgencia.

Atentamente,

[FIRMA]Abog. Marco Antonio Acosta Aldana[/FIRMA]
ICAP N° 1557
[FIRMA]RECAUDO LEGAL & ABOGADOS[/FIRMA]
📧 Email: recaudolegal@yahoo.com
📱 WhatsApp: 942 470 641
Responsable: {{GESTOR_NOMBRE}}
Celular: {{GESTOR_CELULAR}}

[NOTA]Nota: Si al momento de recibir la presente usted ya hubiera cancelado la deuda, sírvase no considerar este aviso. En caso tenga alguna duda o reclamo puede comunicarse al contact center escribiendo a esikaperu@esika.biz o llamando – de lunes a viernes de 8 am a 8 pm y los sábados de 8 am a 6 pm – al 211-3614 (Lima o celular) o 080-11-3030 (provincia). El portador de esta carta NO está autorizado a recibir el dinero.[/NOTA]
""",
}

CARTA_NOMBRES: dict[int, str] = {
    1: "E1-1 — Invitación a Reingreso",
    2: "E1-2 — No Pierdas Ser Empresaria",
    3: "E2-1 — Requerimiento de Pago",
    4: "E2-2 — Insistencia de Pago",
    5: "E3-1 — Exigimos Pago / Pre Judicial",
}

# ── Inline-markup parser ─────────────────────────────────────────

@dataclass
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    red: bool = False


@dataclass
class Segment:
    """One logical block of a rendered template."""
    kind: str   # title | date | body | center | bullet | firma | nota | blank
    runs: list[Run] = field(default_factory=list)

    @property
    def plain(self) -> str:
        return "".join(r.text for r in self.runs)


def _parse_runs(text: str) -> list[Run]:
    """Parse inline markup in a single line of text into Runs."""
    runs: list[Run] = []
    # Pattern order matters: bold first, then italic, then [ROJO]
    pattern = re.compile(
        r'\*\*(.+?)\*\*'           # **bold**
        r'|\*(.+?)\*'              # *italic*
        r'|\[ROJO\](.+?)\[/ROJO\]' # [ROJO]red[/ROJO]
    )
    last = 0
    for m in pattern.finditer(text):
        if m.start() > last:
            runs.append(Run(text[last:m.start()]))
        if m.group(1) is not None:
            runs.append(Run(m.group(1), bold=True))
        elif m.group(2) is not None:
            runs.append(Run(m.group(2), italic=True))
        elif m.group(3) is not None:
            runs.append(Run(m.group(3), red=True))
        last = m.end()
    if last < len(text):
        runs.append(Run(text[last:]))
    return runs or [Run("")]


def parse_template(text: str) -> list[Segment]:
    """
    Split a template text into Segments (title, body, bullet, etc.).
    The first non-empty line always becomes the TITLE segment.
    """
    segments: list[Segment] = []
    lines = text.splitlines()
    title_found = False

    # Multi-line blocks [NOTA], [FIRMA], [CENTRO]
    buffer = ""
    block_kind: Optional[str] = None

    def flush_block():
        nonlocal buffer, block_kind
        if block_kind and buffer.strip():
            segments.append(Segment(kind=block_kind, runs=_parse_runs(buffer.strip())))
        buffer = ""
        block_kind = None

    for raw in lines:
        line = raw.rstrip()

        # Check for block-open tags
        for tag, kind in [("[NOTA]", "nota"), ("[FIRMA]", "firma"), ("[CENTRO]", "center")]:
            close = tag.replace("[", "[/")
            if tag in line and close in line:
                inner = re.search(re.escape(tag) + r"(.*?)" + re.escape(close), line)
                if inner:
                    flush_block()
                    segments.append(Segment(kind=kind, runs=_parse_runs(inner.group(1).strip())))
                    line = ""  # consumed
                    break
            elif tag in line:
                flush_block()
                block_kind = kind
                buffer = line.replace(tag, "")
                line = None  # signal "consumed"
                break
            elif close in line and block_kind == kind:
                buffer += "\n" + line.replace(close, "")
                flush_block()
                line = None
                break

        if line is None:
            continue

        if block_kind:
            buffer += "\n" + line
            continue

        # Blank line
        if not line.strip():
            segments.append(Segment(kind="blank"))
            continue

        # Title (first non-empty line)
        if not title_found:
            title_found = True
            segments.append(Segment(kind="title", runs=_parse_runs(line)))
            continue

        # Bullet (starts with • or - or * as list marker)
        stripped = line.strip()
        if stripped.startswith(("• ", "- ", "* ")):
            item = stripped[2:]
            segments.append(Segment(kind="bullet", runs=_parse_runs(item)))
            continue

        # Regular body line
        segments.append(Segment(kind="body", runs=_parse_runs(line)))

    flush_block()
    return segments


# ── Tag renderer ─────────────────────────────────────────────────

def _es_date() -> str:
    """Return today's date in Spanish: '27 de abril de 2026'"""
    months = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
    }
    today = datetime.now()
    return f"{today.day} de {months[today.month]} de {today.year}"


def render_template(
    template_text: str,
    client: dict,
    gestor_config: dict | None = None,
    campaign_info: dict | None = None,
) -> str:
    """Replace all {{TAG}} placeholders with actual values."""
    gc = gestor_config or {}
    ci = campaign_info or {}

    nombre = (
        client.get("nombre_completo", "").strip()
        or (
            f"{client.get('nombres', '')} "
            f"{client.get('apellido_paterno', '')} "
            f"{client.get('apellido_materno', '')}".strip()
        )
    )
    dni = str(client.get("numero_documento", client.get("dni", "")))

    # Build address
    addr_parts = [
        client.get("direccion", ""),
        client.get("distrito", ""),
        client.get("provincia", ""),
    ]
    direccion = ", ".join(p for p in addr_parts if p)

    # Deuda
    deuda_raw = client.get("importe_deuda_pendiente",
                            client.get("importe_deuda_asignada",
                                       client.get("saldo", 0)))
    try:
        deuda_str = f"{float(deuda_raw):,.2f}"
    except (ValueError, TypeError):
        deuda_str = "0.00"

    values = {
        "NOMBRE":            nombre,
        "DNI":               dni,
        "DIRECCION":         direccion or client.get("direccion", ""),
        "CODIGO":            str(client.get("codigo_cliente", "")),
        "ZONA":              str(client.get("zona", "")),
        "SECCION":           str(client.get("seccion", "")),
        "CAMPANA":           str(ci.get("nombre", client.get("campana", ""))),
        "DEUDA":             deuda_str,
        "CODIGO_PAGO":       str(client.get("codigo_cliente",
                                             client.get("codigo_pago", ""))),
        "FECHA":             _es_date(),
        "FECHA_VENCIMIENTO": str(client.get("fecha_vencimiento", "—")),
        "GESTOR_NOMBRE":     gc.get("nombre_gestor", ""),
        "GESTOR_CELULAR":    gc.get("telefono_gestor", ""),
    }

    result = template_text
    for tag, value in values.items():
        result = result.replace(f"{{{{{tag}}}}}", value)
    return result
