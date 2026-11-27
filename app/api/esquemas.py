"""Esquemas Pydantic de la API (de aquí FastAPI genera la especificación OpenAPI 3).

Sesión 3: catálogo de fideicomisos, adhesión por fideicomiso, aporte repartido con medio de pago,
cuestionario en 2 tandas, IA predictiva y privacidad. Los esquemas de la Sesión 2 siguen
aceptándose (campos nuevos con valores por defecto) para no romper CP-01..CP-21.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- InvierteYa
Paso = Literal["CUESTIONARIO_COMPLETO", "ANTES_PRIMER_APORTE", "UNIDADES_ASIGNADAS",
               "VER_PORTAFOLIO", "ANTES_RESCATE"]
Perfil = Literal["CONSERVADOR", "MODERADO", "AGRESIVO"]
Etiqueta = Literal["RECOMENDADO", "COMPATIBLE", "POR_ENCIMA_DEL_PERFIL"]
MedioPago = Literal["TARJETA", "PAGO_MOVIL", "TRANSFERENCIA"]


class RegistroIn(BaseModel):
    nombre: str = Field(..., max_length=120, examples=["María Pérez (dato sintético)"])
    email: str = Field(..., max_length=254, examples=["maria@example.com"])


class UsuarioOut(BaseModel):
    usuario_id: str
    nombre: str
    kyc_aprobado: bool
    adhesion_firmada: bool
    perfil: str | None


class KycIn(BaseModel):
    edad: int | None = Field(None, ge=18, le=100, examples=[24],
                             description="Edad verificada por el KYC simulado (default 24)")


class KycOut(BaseModel):
    usuario_id: str
    kyc: str
    compartido_con_fiduciario: bool
    edad_kyc: int


# ---------------------------------------------------------------- catálogo de fideicomisos
class FideicomisoBanco(BaseModel):
    id: str
    nombre: str
    riesgo: int = Field(..., ge=1, le=5)
    horizonte: str
    minimo_usd: float
    comision_anual_pct: float
    rescate_dias: str
    valor_unidad: str
    rendimiento_anual_simulado_pct: float
    composicion: dict[str, int]


class CatalogoBancoOut(BaseModel):
    banco: str
    fecha_valor: str
    publicado_en: str
    fideicomisos: list[FideicomisoBanco]


class FideicomisoOut(FideicomisoBanco):
    etiqueta: Etiqueta | None = Field(None, description="None si el usuario aún no tiene perfil")
    etiqueta_texto: str | None = None
    requiere_confirmacion_riesgo: bool
    adhesion_firmada: bool


class CatalogoOut(BaseModel):
    usuario_id: str | None
    perfil_usuario: Perfil | None
    riesgo_maximo_perfil: int | None
    nota_rendimiento: str
    actualizado_en: str | None
    fideicomisos: list[FideicomisoOut]


# ---------------------------------------------------------------- adhesión
class AdhesionIn(BaseModel):
    acepta: bool = Field(..., description="El usuario acepta el contrato de adhesión al fideicomiso")
    fideicomiso_id: str | None = Field(
        None, examples=["mix_bal"],
        description="Fideicomiso del catálogo. Si se omite, se usa el recomendado del perfil (compatibilidad S2)")
    confirmacion_riesgo_extra: bool = Field(
        False, description="Obligatoria (true) si el fideicomiso está 'Por encima de tu perfil'")


class AdhesionOut(BaseModel):
    usuario_id: str
    adhesion: str
    fideicomitente_y_beneficiario: bool
    fideicomiso_id: str | None
    nombre_fideicomiso: str | None
    etiqueta: Etiqueta | None
    confirmacion_riesgo_extra: bool
    sello_tiempo: str = Field(..., description="ISO 8601 con zona horaria")
    hash_adhesion: str = Field(..., description="SHA-256 del documento firmado (JSON canónico)")
    algoritmo_hash: str
    version_contrato: str
    base_legal: str
    leccion: Leccion | None


# ---------------------------------------------------------------- cuestionario y perfil
class CuestionarioIn(BaseModel):
    """Formato Sesión 2 (10 variables). Se sigue aceptando por compatibilidad."""
    edad: int = Field(..., ge=18, le=100, examples=[24])
    ingreso_rango: int = Field(..., ge=1, le=5, examples=[2])
    pct_invertible: float = Field(..., ge=0, le=100, examples=[15])
    horizonte_anios: float = Field(..., ge=0, examples=[2])
    objetivo: Literal["proteger", "crecer", "ganar_rapido"]
    reaccion_caida_20: Literal["vender_todo", "esperar", "comprar_mas"]
    experiencia_previa: bool
    fondo_emergencia: bool
    dependientes: int = Field(..., ge=0)
    conocimiento: int = Field(..., ge=1, le=5)


class CuestionarioS3In(BaseModel):
    """Formato Sesión 3: Tanda 1 (6 preguntas) y, opcionalmente, Tanda 2. `null` = 'Prefiero no decirlo'."""
    tanda: Literal[1, 2] = 1
    edad: int | None = Field(None, ge=18, le=100, description="Si se omite, se toma del KYC")
    ahorro_mensual_rango: Literal[1, 2, 3, 4] | None = Field(
        None, examples=[2], description="1 ($5–$20) · 2 ($20–$50) · 3 ($50–$100) · 4 (> $100) · null (no dice)")
    horizonte_anios: float = Field(..., ge=0, le=50, examples=[2.0],
                                   description="0.5 (imprevisto) · 2.0 (meta 1–3 años) · 4.0 (algo grande) · 7.0 (mi futuro)")
    objetivo: Literal["proteger", "crecer", "ganar_rapido"]
    reaccion_caida_20: Literal["vender_todo", "esperar", "comprar_mas"]
    emergencia_200: Literal["ahorros", "prestado", "no_podria"] | None = Field(
        None, description="null = 'Prefiero no decirlo' (nunca Agresivo)")
    experiencia_tipo: Literal["ninguna", "ahorro_dolares", "caja_ahorro", "acciones"]
    dependientes: int | None = Field(None, ge=0, le=5)
    quiz_aciertos: Literal[0, 1, 2] | None = None


class Tanda2In(BaseModel):
    dependientes: int | None = Field(..., ge=0, le=5, examples=[0])
    quiz_aciertos: Literal[0, 1, 2] | None = Field(..., examples=[2])


class Leccion(BaseModel):
    id: str
    paso: str
    perfil: str
    nivel: str
    titulo: str
    texto: str


class PerfilOut(BaseModel):
    perfil: Perfil
    puntaje: float
    puntaje_maximo: int
    explicacion: str
    factores_suben: list[str] = Field(default_factory=list, description="Lo que sube la tolerancia al riesgo")
    factores_moderan: list[str] = Field(default_factory=list, description="Lo que la modera")
    avisos: list[str]
    leccion: Leccion | None
    motor: str
    perfil_reglas: Perfil | None = Field(
        None, description="Perfil según las reglas de idoneidad (respaldo y comparación)")
    probabilidad: float | None = Field(None, description="Probabilidad del perfil según el modelo")
    probabilidades: dict[str, float] | None = Field(None, description="Probabilidad de cada perfil")
    revision_humana: bool = Field(False, description="True si la probabilidad es < 60%: un asesor revisa el caso")
    # Extensiones Sesión 3
    tanda_completada: int = 2
    campos_omitidos: list[str] = Field(default_factory=list)
    que_cambiaria: list[str] = Field(default_factory=list, description="Qué respuesta cambiaría el perfil")
    aviso_transparencia: str | None = None
    nota_rendimiento: str | None = None
    fideicomiso_recomendado: str | None = Field(None, description="Fideicomiso principal sugerido para el perfil")


class RevisionIn(BaseModel):
    motivo: str = Field(..., min_length=3, max_length=500,
                        examples=["Creo que mi tolerancia es más conservadora"])


class RevisionOut(BaseModel):
    revision_id: str
    estado: Literal["PENDIENTE_ASESOR"]
    perfil_actual: Perfil
    mensaje: str


# ---------------------------------------------------------------- aportes
class Distribucion(BaseModel):
    fideicomiso_id: str = Field(..., examples=["rf_usd"])
    porcentaje: float = Field(..., gt=0, le=100, examples=[70])


class AporteIn(BaseModel):
    usuario_id: str
    monto: float = Field(..., ge=5, le=1000, description="Monto a invertir en USD (mínimo $5)", examples=[20])
    token_tarjeta: str = Field(..., description="Token del medio de pago emitido por la pasarela. "
                                                "InvierteYa nunca recibe el PAN ni el número de teléfono.")
    medio_pago: MedioPago = Field("TARJETA", description="TARJETA: 1% + 2% recargo · PAGO_MOVIL/TRANSFERENCIA: 1%")
    distribucion: list[Distribucion] | None = Field(
        None, min_length=1, max_length=5,
        description="Reparto entre fideicomisos (suma 100%). Si se omite: 100% al recomendado del perfil")


class EventoAporte(BaseModel):
    estado: str
    detalle: str


class Asignacion(BaseModel):
    fideicomiso_id: str
    nombre: str
    porcentaje: float
    monto: str
    unidades: str
    valor_unidad: str


class AporteOut(BaseModel):
    id: str
    usuario_id: str
    portafolio: str = Field(..., description="Perfil del usuario al momento del aporte")
    monto: str
    estado: Literal["PENDIENTE", "AUTORIZADO", "CAPTURADO", "ASIGNADO", "RECHAZADO",
                    "EN_REVERSO", "REVERSADO", "REVERSO_PENDIENTE"]
    unidades: str | None = Field(None, description="Total de unidades (suma de todas las asignaciones)")
    mensaje: str | None
    leccion: Leccion | None
    rrn: str | None
    auth_code: str | None
    eventos: list[EventoAporte]
    iso8583: list[dict] = Field(..., description="Mensajes ISO 8583 SIMULADOS del tramo pasarela-suiche (demo)")
    latencia_total_ms: float | None = None
    duplicado: bool
    # Extensiones Sesión 3 (transparencia de comisiones · Res. SUDEBAN 063.15)
    medio_pago: MedioPago = "TARJETA"
    comision_aporte_pct: float = 1.0
    recargo_medio_pago_pct: float = 0.0
    comision_aporte_usd: str = "0.00"
    recargo_medio_pago_usd: str = "0.00"
    comision_total_usd: str = "0.00"
    monto_cobrado: str | None = Field(None, description="Monto + comisión + recargo (lo que se cobra)")
    distribucion: list[Distribucion] = Field(default_factory=list)
    asignaciones: list[Asignacion] = Field(default_factory=list)


class FideicomisoPortafolio(BaseModel):
    fideicomiso_id: str
    nombre: str
    riesgo: int
    unidades: str
    valor_unidad: str
    saldo: str
    composicion: dict[str, int]
    comision_anual_pct: float
    aportes: int
    etiqueta: Etiqueta | None = None


class PortafolioOut(BaseModel):
    usuario_id: str
    portafolio: str | None
    unidades: str
    valor_unidad: str = Field(..., description="Valor promedio ponderado de la unidad (consolidado)")
    saldo: str
    composicion: dict[str, int]
    aportes: int
    leccion: Leccion | None
    fideicomisos: list[FideicomisoPortafolio] = Field(default_factory=list)
    nota_rendimiento: str | None = None


# ---------------------------------------------------------------- IA predictiva
class RiesgoAbandonoOut(BaseModel):
    usuario_id: str
    probabilidad_abandono: float
    en_riesgo: bool
    nivel_riesgo: Literal["BAJO", "MEDIO", "ALTO"]
    umbral_alerta: float
    factores: list[str]
    sugerencia_suave: str | None
    accion_permitida: Literal["SOLO_SUGERIR_RECORDATORIO"]
    aviso_etico: str
    motor: str
    consentimiento_alertas: bool = Field(..., description="Si es false no se muestra la sugerencia")
    datos_simulados: bool = Field(..., description="True si se usó ?simular_inactivo=true (demo)")
    variables: dict = Field(..., description="Variables que recibió el modelo (transparencia)")


class PronosticoFideicomiso(BaseModel):
    fideicomiso_id: str
    nombre: str
    flujo_neto_manana_usd: float
    flujo_neto_7d_usd: float
    mae_usd: float
    mape_pct: float


class PronosticoOut(BaseModel):
    modelo_elegido: str
    fecha_corte: str
    por_fideicomiso: list[PronosticoFideicomiso]
    total_manana_usd: float
    total_7d_usd: float
    nota: str


# ---------------------------------------------------------------- privacidad y seguridad de datos
class ConsentimientoIn(BaseModel):
    informes_agregados: bool | None = Field(None, description="Informes agregados anónimos (k >= 10)")
    alertas_ahorro: bool | None = Field(None, description="Avisos suaves del modelo de abandono")


class ConsentimientoOut(BaseModel):
    usuario_id: str
    consentimientos: dict[str, bool]
    actualizado_en: str
    historial: list[dict]
    nota: str


class DatosPersonalesOut(BaseModel):
    usuario_id: str
    suprimido: bool
    datos_identificacion: dict
    kyc_aprobado: bool
    perfil: str | None
    respuestas_cuestionario: dict | None
    adhesiones: list[dict]
    aportes: dict
    consentimientos: dict[str, bool]
    historial_consentimientos: list[dict]
    revisiones_perfil: list[dict]
    finalidades: list[str]
    destinatarios: list[dict]
    proteccion: dict
    conservacion: str
    base_legal: str


class SupresionOut(BaseModel):
    usuario_id: str
    estado: str
    seudonimo: str
    suprimido: list[str]
    conservado: list[str]
    motivo_conservacion: str


class CeldaOro(BaseModel):
    perfil: str | None = None
    fideicomiso_id: str | None = None
    suprimida: bool
    personas: int | str
    total: float | None
    promedio: float | None


class InformeAgregadoOut(BaseModel):
    k_minimo: int
    dimensiones: list[str]
    metrica: str | None
    celdas: list[CeldaOro]
    celdas_publicadas: int
    celdas_suprimidas: int
    personas_que_consintieron: int
    nota: str


class RotacionLlavesOut(BaseModel):
    version_anterior: int
    version_activa: int
    registros_reenvueltos: int
    kms: dict


class Error(BaseModel):
    codigo: str
    mensaje: str


# ---------------------------------------------------------------- Pasarela simulada
class TokenIn(BaseModel):
    pan: str = Field(..., description="SOLO números de tarjeta de PRUEBA (o teléfono sintético de Pago Móvil)",
                     examples=["4111111111111111"])


class TokenOut(BaseModel):
    token: str


class AutorizacionIn(BaseModel):
    token: str
    amount: int = Field(..., gt=0, description="Monto en centavos")
    currency: Literal["USD"] = "USD"
    reference: str


class CapturaIn(BaseModel):
    authorization_id: str
    amount: int = Field(..., gt=0)


class ReversoIn(BaseModel):
    original_reference: str = Field(..., description="authorization_id de la transacción original")
    reason: Literal["TIMEOUT", "FALLA_CAPTURA", "DUPLICADO", "OTRO"]


class DevolucionIn(BaseModel):
    authorization_id: str


class RespuestaPasarela(BaseModel):
    status: str
    response_code: str | None
    authorization_id: str | None
    auth_code: str | None
    rrn: str | None
    latencia_ms: float
    iso: list[dict]


AdhesionOut.model_rebuild()
