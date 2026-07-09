"""

Tramo Engine — Motor de Evaluación de Tramos

============================================



Ciclo de cobranza **por cuenta** (59 días desde fecha de asignación):



  Etapa 1 · Recuperación inicial  → Días  1 – 10

  Etapa 2 · Seguimiento medio     → Días 11 – 43

  Etapa 3 · Cierre de gestión     → Días 44 – 59



Reglas:

  - El día del ciclo se calcula por cuenta (fecha_asignacion del Excel).

  - Día 60: cierre automático (estado_ciclo = cerrada).

  - Día 70 sin recupero: retorno al banco (estado_ciclo = retornada_banco).

  - Saldo < S/ 10: excluido de avance de tramo.

  - Cartas físicas (2-5) solo si saldo > S/ 40.

"""



from __future__ import annotations



import logging

from dataclasses import dataclass, field

from datetime import datetime, date

from typing import List, Optional



from sqlalchemy.orm import Session



from .excel_parser import make_seccion_key

from .database import (

    Cliente, Campana, HistorialTramo, HistorialZona, CartaGenerada,

    TramoEnum, EstadoCampana, EstadoCiclo, EstadoGestion, db_service, ConfigCampana,

    FASE_GESTION_CALL, FASE_GESTION_CAMPO, make_call_section_key,

)




logger = logging.getLogger(__name__)



# ── Default constants (used when no DB config exists) ─────────────



_DEFAULT_UMBRAL_MINIMO_GESTION = 10.0

_DEFAULT_UMBRAL_CARTA_FISICA = 40.0

_DEFAULT_DIAS_CIERRE = 60

_DEFAULT_DIAS_RETORNO = 70

_DEFAULT_DURACION = 59



_DEFAULT_TRAMO_BOUNDARIES = {

    TramoEnum.TRAMO_1: (1, 10),

    TramoEnum.TRAMO_2: (11, 43),

    TramoEnum.TRAMO_3: (44, 59),

}



_DEFAULT_CARTA_SCHEDULE = {

    1: {"dia": 1,  "tramo": TramoEnum.TRAMO_1, "requiere_umbral_alto": False},

    2: {"dia": 9,  "tramo": TramoEnum.TRAMO_1, "requiere_umbral_alto": True},

    3: {"dia": 11, "tramo": TramoEnum.TRAMO_2, "requiere_umbral_alto": True},

    4: {"dia": 35, "tramo": TramoEnum.TRAMO_2, "requiere_umbral_alto": True},

    5: {"dia": 44, "tramo": TramoEnum.TRAMO_3, "requiere_umbral_alto": True},

}



UMBRAL_MINIMO_GESTION = _DEFAULT_UMBRAL_MINIMO_GESTION

UMBRAL_CARTA_FISICA = _DEFAULT_UMBRAL_CARTA_FISICA

DIAS_CIERRE = _DEFAULT_DIAS_CIERRE

DIAS_RETORNO_BANCO = _DEFAULT_DIAS_RETORNO

DURACION_CICLO = _DEFAULT_DURACION

TRAMO_BOUNDARIES = dict(_DEFAULT_TRAMO_BOUNDARIES)

CARTA_SCHEDULE = dict(_DEFAULT_CARTA_SCHEDULE)





def load_config() -> ConfigCampana | None:

    """Read ``ConfigCampana`` from SQLite and refresh module globals."""

    global UMBRAL_MINIMO_GESTION, UMBRAL_CARTA_FISICA

    global TRAMO_BOUNDARIES, CARTA_SCHEDULE

    global DIAS_CIERRE, DIAS_RETORNO_BANCO, DURACION_CICLO



    if not db_service.is_initialized:

        return None



    try:

        with db_service.session() as session:

            cfg = ConfigCampana.get_or_create(session)



            UMBRAL_MINIMO_GESTION = cfg.umbral_minimo_gestion

            UMBRAL_CARTA_FISICA = cfg.umbral_carta_fisica

            DIAS_CIERRE = getattr(cfg, "dias_cierre", None) or _DEFAULT_DIAS_CIERRE

            DIAS_RETORNO_BANCO = (

                getattr(cfg, "dias_retorno_banco", None) or _DEFAULT_DIAS_RETORNO

            )

            DURACION_CICLO = cfg.duracion_dias or _DEFAULT_DURACION



            TRAMO_BOUNDARIES = {

                TramoEnum.TRAMO_1: (cfg.tramo1_inicio, cfg.tramo1_fin),

                TramoEnum.TRAMO_2: (cfg.tramo2_inicio, cfg.tramo2_fin),

                TramoEnum.TRAMO_3: (cfg.tramo3_inicio, cfg.tramo3_fin),

            }



            def _tramo_for_day(day: int) -> TramoEnum:

                for t, (s, e) in TRAMO_BOUNDARIES.items():

                    if s <= day <= e:

                        return t

                return TramoEnum.TRAMO_3



            CARTA_SCHEDULE = {

                1: {"dia": cfg.carta1_dia, "tramo": _tramo_for_day(cfg.carta1_dia), "requiere_umbral_alto": False},

                2: {"dia": cfg.carta2_dia, "tramo": _tramo_for_day(cfg.carta2_dia), "requiere_umbral_alto": True},

                3: {"dia": cfg.carta3_dia, "tramo": _tramo_for_day(cfg.carta3_dia), "requiere_umbral_alto": True},

                4: {"dia": cfg.carta4_dia, "tramo": _tramo_for_day(cfg.carta4_dia), "requiere_umbral_alto": True},

                5: {"dia": cfg.carta5_dia, "tramo": _tramo_for_day(cfg.carta5_dia), "requiere_umbral_alto": True},

            }



            return cfg

    except Exception:

        logger.exception("Failed to load campaign config from DB")

        return None





# ── Action DTOs ──────────────────────────────────────────────────



@dataclass

class TramoTransition:

    """Represents a tramo change for one client."""

    cliente_id: int

    codigo_cliente: str

    tramo_anterior: int

    tramo_nuevo: int

    dia_campana: int

    saldo: float

    motivo: str = "Evaluación automática por calendario"





@dataclass

class CallToCampoTransition:

    """Cuenta que pasa de call center a gestión de campo (tramo 1 → 2)."""

    cliente_id: int

    codigo_cliente: str

    seccion_call: str

    seccion_territorial: str

    call_gestor_uid_anterior: str = ""

    motivo: str = "Pase automático call → campo (día 11, sin contacto, saldo > umbral)"





@dataclass

class CycleStateChange:

    """Cierre o retorno de una cuenta en su ciclo individual."""

    cliente_id: int

    codigo_cliente: str

    dia_ciclo: int

    estado_anterior: str

    estado_nuevo: str

    motivo: str





@dataclass

class CartaPendiente:

    """Represents a letter that should be generated."""

    cliente_id: int

    codigo_cliente: str

    nombre_completo: str

    region: str

    zona: str

    seccion: str

    seccion_key: str

    numero_carta: int

    tramo: int

    dia_campana: int

    saldo: float

    omitida_por_monto: bool = False





@dataclass

class EvaluationResult:

    """Full result of a tramo evaluation run."""

    campana_id: str

    dia_campana: int

    fecha_evaluacion: datetime = field(default_factory=datetime.now)

    transiciones: List[TramoTransition] = field(default_factory=list)

    cambios_ciclo: List[CycleStateChange] = field(default_factory=list)

    cartas_pendientes: List[CartaPendiente] = field(default_factory=list)

    pasos_a_campo: List[CallToCampoTransition] = field(default_factory=list)

    clientes_excluidos: int = 0

    clientes_evaluados: int = 0

    clientes_cerrados: int = 0

    clientes_retornados: int = 0

    errores: List[str] = field(default_factory=list)



    @property

    def resumen(self) -> str:

        return (

            f"Evaluación campaña {self.campana_id} — Día cartera {self.dia_campana}\n"

            f"  Clientes evaluados: {self.clientes_evaluados}\n"

            f"  Excluidos (saldo < {UMBRAL_MINIMO_GESTION}): {self.clientes_excluidos}\n"

            f"  Transiciones de tramo: {len(self.transiciones)}\n"

            f"  Cierres ciclo (día {DIAS_CIERRE}): {self.clientes_cerrados}\n"

            f"  Retornos banco (día {DIAS_RETORNO_BANCO}): {self.clientes_retornados}\n"

            f"  Cartas pendientes: {len(self.cartas_pendientes)}\n"

            f"  Pasos call → campo: {len(self.pasos_a_campo)}\n"

            f"  Errores: {len(self.errores)}"

        )





# ── Tramo Engine ─────────────────────────────────────────────────



class TramoEngine:

    """Motor de reglas: evalúa cada cuenta según su propio ciclo de 59 días."""



    @staticmethod

    def get_tramo_for_day(dia: int) -> TramoEnum:

        """Dado el día del ciclo de una cuenta, devuelve la etapa correspondiente."""

        if dia < 1:

            return TramoEnum.NONE

        for tramo, (start, end) in TRAMO_BOUNDARIES.items():

            if start <= dia <= end:

                return tramo

        return TramoEnum.TRAMO_3



    @staticmethod

    def get_pending_cartas(dia: int) -> List[int]:

        """Cartas que debieron emitirse en o antes del día del ciclo dado."""

        return sorted(

            num for num, info in CARTA_SCHEDULE.items()

            if info["dia"] <= dia

        )



    def evaluate_campaign(

        self,

        session: Session,

        campana: Campana,

        *,

        dia_override: int | None = None,

    ) -> EvaluationResult:

        """

        Evalúa todos los clientes activos de la campaña.



        Cada cuenta usa su ``dia_ciclo`` (desde fecha_asignacion).

        """

        load_config()

        dia_cartera = dia_override if dia_override is not None else campana.dia_actual

        result = EvaluationResult(campana_id=campana.id, dia_campana=dia_cartera)



        clientes = (

            session.query(Cliente)

            .filter(

                Cliente.campana_id == campana.id,

                Cliente.activo_en_cartera.is_(True),

            )

            .all()

        )



        for cliente in clientes:

            result.clientes_evaluados += 1



            try:

                dia = cliente.dia_ciclo

                estado = cliente.estado_ciclo or EstadoCiclo.ACTIVA.value



                if estado == EstadoCiclo.RETORNADA_BANCO.value:

                    continue



                if estado == EstadoCiclo.CERRADA.value:

                    if dia >= DIAS_RETORNO_BANCO and cliente.sigue_en_gestion:

                        result.cambios_ciclo.append(CycleStateChange(

                            cliente_id=cliente.id,

                            codigo_cliente=cliente.codigo_cliente,

                            dia_ciclo=dia,

                            estado_anterior=estado,

                            estado_nuevo=EstadoCiclo.RETORNADA_BANCO.value,

                            motivo=f"Sin recupero al día {dia} del ciclo",

                        ))

                        result.clientes_retornados += 1

                    continue



                if dia >= DIAS_CIERRE:

                    result.cambios_ciclo.append(CycleStateChange(

                        cliente_id=cliente.id,

                        codigo_cliente=cliente.codigo_cliente,

                        dia_ciclo=dia,

                        estado_anterior=estado,

                        estado_nuevo=EstadoCiclo.CERRADA.value,

                        motivo=f"Cierre automático al día {dia} del ciclo",

                    ))

                    result.clientes_cerrados += 1

                    continue



                if not cliente.sigue_en_gestion:

                    result.clientes_excluidos += 1

                    continue



                tramo_esperado = self.get_tramo_for_day(dia)

                cartas_necesarias = self.get_pending_cartas(dia)



                if cliente.tramo_actual != tramo_esperado.value:

                    result.transiciones.append(TramoTransition(

                        cliente_id=cliente.id,

                        codigo_cliente=cliente.codigo_cliente,

                        tramo_anterior=cliente.tramo_actual,

                        tramo_nuevo=tramo_esperado.value,

                        dia_campana=dia,

                        saldo=cliente.importe_deuda_pendiente,

                    ))



                cartas_existentes = set()

                for c in (

                    session.query(CartaGenerada)

                    .filter(

                        CartaGenerada.cliente_id == cliente.id,

                        CartaGenerada.campana_id == campana.id,

                    )

                    .all()

                ):

                    estado_pub = str(c.estado_publicacion or "").strip().lower()

                    if c.omitida_por_monto or estado_pub == "publicada":

                        cartas_existentes.add(c.numero_carta)



                for num_carta in cartas_necesarias:

                    if num_carta in cartas_existentes:

                        continue



                    info = CARTA_SCHEDULE[num_carta]

                    omitida = False

                    if info["requiere_umbral_alto"] and not cliente.requiere_carta_fisica:

                        omitida = True



                    result.cartas_pendientes.append(CartaPendiente(

                        cliente_id=cliente.id,

                        codigo_cliente=cliente.codigo_cliente,

                        nombre_completo=cliente.nombre_completo or "",

                        region=cliente.region or "",

                        zona=cliente.zona or "",

                        seccion=cliente.seccion or "",

                        seccion_key=make_seccion_key(

                            cliente.region or "",

                            cliente.zona or "",

                            cliente.seccion or "",

                        ),

                        numero_carta=num_carta,

                        tramo=info["tramo"].value,

                        dia_campana=dia,

                        saldo=cliente.importe_deuda_pendiente,

                        omitida_por_monto=omitida,

                    ))



            except Exception as e:

                result.errores.append(

                    f"Error evaluando cliente {cliente.codigo_cliente}: {e}"

                )

                logger.exception(

                    "Error evaluando cliente %s", cliente.codigo_cliente

                )



        return result



    def apply_transitions(

        self,

        session: Session,

        result: EvaluationResult,

    ) -> int:

        """Aplica transiciones de tramo. Retorna cantidad actualizada."""

        count = 0

        for tr in result.transiciones:

            cliente = session.get(Cliente, tr.cliente_id)

            if cliente is None:

                continue



            cliente.tramo_actual = tr.tramo_nuevo

            cliente.fecha_actualizacion = datetime.now()



            if (

                tr.tramo_anterior == TramoEnum.TRAMO_1.value

                and tr.tramo_nuevo == TramoEnum.TRAMO_2.value

                and getattr(cliente, "fase_gestion", FASE_GESTION_CAMPO) == FASE_GESTION_CALL

            ):

                sin_contacto = cliente.estado_gestion != EstadoGestion.VISITADO_HABIDO.value

                saldo_supera_umbral = cliente.importe_deuda_pendiente > UMBRAL_CARTA_FISICA

                if sin_contacto and saldo_supera_umbral:

                    seccion_call = (

                        make_call_section_key(cliente.call_gestor_uid)

                        if cliente.call_gestor_uid

                        else ""

                    )

                    seccion_territorial = make_seccion_key(

                        cliente.region or "", cliente.zona or "", cliente.seccion or "SIN_SECCION"

                    )

                    uid_anterior = cliente.call_gestor_uid or ""

                    cliente.fase_gestion = FASE_GESTION_CAMPO

                    cliente.call_gestor_uid = None

                    cliente.call_gestor_nombre = None

                    motivo_pase = (

                        "Pase automático call→campo: sin contacto efectivo "

                        f"y saldo S/ {cliente.importe_deuda_pendiente:.2f} > S/ {UMBRAL_CARTA_FISICA}"

                    )

                    result.pasos_a_campo.append(

                        CallToCampoTransition(

                            cliente_id=tr.cliente_id,

                            codigo_cliente=tr.codigo_cliente,

                            seccion_call=seccion_call,

                            seccion_territorial=seccion_territorial,

                            call_gestor_uid_anterior=uid_anterior,

                            motivo=motivo_pase,

                        )

                    )

                    session.add(

                        HistorialZona(

                            campana_id=result.campana_id,

                            codigo_cliente=tr.codigo_cliente,

                            event_id=f"call_campo_{tr.cliente_id}_{datetime.now().isoformat()}",

                            seccion_anterior=seccion_call or seccion_territorial,

                            seccion_nueva=seccion_territorial,

                            usuario_nombre="Sistema",

                            usuario_email="sistema@antcobranzas",

                            fecha_evento=datetime.now().isoformat(),

                        )

                    )



            historial = HistorialTramo(

                cliente_id=tr.cliente_id,

                campana_id=result.campana_id,

                tramo_anterior=tr.tramo_anterior,

                tramo_nuevo=tr.tramo_nuevo,

                dia_campana=tr.dia_campana,

                saldo_al_momento=tr.saldo,

                motivo=tr.motivo,

            )

            session.add(historial)

            count += 1



        session.commit()

        logger.info(

            "Applied %d tramo transitions for campaign %s",

            count, result.campana_id,

        )

        return count



    def apply_cycle_changes(

        self,

        session: Session,

        result: EvaluationResult,

    ) -> int:

        """Aplica cierres y retornos de ciclo por cuenta."""

        count = 0

        today = date.today()

        for ch in result.cambios_ciclo:

            cliente = session.get(Cliente, ch.cliente_id)

            if cliente is None:

                continue

            cliente.estado_ciclo = ch.estado_nuevo

            cliente.fecha_actualizacion = datetime.now()

            if ch.estado_nuevo == EstadoCiclo.CERRADA.value:

                cliente.fecha_cierre_real = today

            count += 1



        session.commit()

        logger.info(

            "Applied %d cycle state changes for campaign %s",

            count, result.campana_id,

        )

        return count



    def record_cartas(

        self,

        session: Session,

        result: EvaluationResult,

        *,

        include_omitted: bool = True,

    ) -> int:

        """Registra cartas generadas u omitidas en la base de datos."""

        count = 0

        for cp in result.cartas_pendientes:

            if cp.omitida_por_monto and not include_omitted:

                continue



            existing = (

                session.query(CartaGenerada)

                .filter(

                    CartaGenerada.cliente_id == cp.cliente_id,

                    CartaGenerada.campana_id == result.campana_id,

                    CartaGenerada.numero_carta == cp.numero_carta,

                )

                .first()

            )

            if existing:

                continue



            carta = CartaGenerada(

                cliente_id=cp.cliente_id,

                campana_id=result.campana_id,

                numero_carta=cp.numero_carta,

                tramo=cp.tramo,

                omitida_por_monto=cp.omitida_por_monto,

            )

            session.add(carta)

            count += 1



        session.commit()

        logger.info(

            "Recorded %d cartas for campaign %s",

            count, result.campana_id,

        )

        return count





def evaluar_campana(

    campana_id: str | None = None,

    dia_override: int | None = None,

    auto_apply: bool = False,

) -> EvaluationResult:

    """Función de conveniencia para evaluar una campaña."""

    engine = TramoEngine()



    with db_service.session() as session:

        if campana_id:

            campana = session.get(Campana, campana_id)

        else:

            campana = (

                session.query(Campana)

                .filter(Campana.estado == EstadoCampana.ACTIVA.value)

                .order_by(Campana.fecha_creacion.desc())

                .first()

            )



        if campana is None:

            result = EvaluationResult(

                campana_id=campana_id or "N/A", dia_campana=0

            )

            result.errores.append("No se encontró campaña activa.")

            return result



        result = engine.evaluate_campaign(

            session, campana, dia_override=dia_override

        )



        if auto_apply:

            engine.apply_transitions(session, result)

            engine.apply_cycle_changes(session, result)

            engine.record_cartas(session, result)



    return result


