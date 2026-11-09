"""Esquemas Pydantic de la API (de aquí FastAPI genera la especificación OpenAPI 3)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- InvierteYa
Paso = Literal["CUESTIONARIO_COMPLETO", "ANTES_PRIMER_APORTE", "UNIDADES_ASIGNADAS",
               "VER_PORTAFOLIO", "ANTES_RESCATE"]
Perfil = Literal["CONSERVADOR", "MODERADO", "AGRESIVO"]


class RegistroIn(BaseModel):
    nombre: str = Field(..., examples=["María Pérez (dato sintético)"])
    email: str = Field(..., examples=["maria@example.com"])


class UsuarioOut(BaseModel):
    usuario_id: str
    nombre: str
    kyc_aprobado: bool
    adhesion_firmada: bool
    perfil: str | None


class AdhesionIn(BaseModel):
    acepta: bool = Field(..., description="El usuario acepta el contrato de adhesión al fideicomiso")


class CuestionarioIn(BaseModel):
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


class Leccion(BaseModel):
    id: str
    paso: str
    perfil: str
    nivel: str
    titulo: str
    texto: str


class PerfilOut(BaseModel):
    perfil: Literal["CONSERVADOR", "MODERADO", "AGRESIVO"]
    puntaje: float
    puntaje_maximo: int
    explicacion: str
    factores_suben: list[str] = Field(default_factory=list, description="Lo que sube la tolerancia al riesgo")
    factores_moderan: list[str] = Field(default_factory=list, description="Lo que la modera")
    avisos: list[str]
    leccion: Leccion | None
    motor: str
    perfil_reglas: Literal["CONSERVADOR", "MODERADO", "AGRESIVO"] | None = Field(
        None, description="Perfil según las reglas de idoneidad (respaldo y comparación)")
    probabilidad: float | None = Field(None, description="Probabilidad del perfil según el modelo baseline")
    probabilidades: dict[str, float] | None = Field(None, description="Probabilidad de cada perfil")
    revision_humana: bool = Field(False, description="True si la probabilidad es < 60%: un asesor revisa el caso")


class AporteIn(BaseModel):
    usuario_id: str
    monto: float = Field(..., ge=5, le=1000, description="Monto en USD (mínimo $5)", examples=[20])
    token_tarjeta: str = Field(..., description="Token emitido por la pasarela. InvierteYa nunca recibe el PAN.")


class EventoAporte(BaseModel):
    estado: str
    detalle: str


class AporteOut(BaseModel):
    id: str
    usuario_id: str
    portafolio: str
    monto: str
    estado: Literal["PENDIENTE", "AUTORIZADO", "CAPTURADO", "ASIGNADO", "RECHAZADO",
                    "EN_REVERSO", "REVERSADO", "REVERSO_PENDIENTE"]
    unidades: str | None
    mensaje: str | None
    leccion: Leccion | None
    rrn: str | None
    auth_code: str | None
    eventos: list[EventoAporte]
    iso8583: list[dict] = Field(..., description="Mensajes ISO 8583 SIMULADOS del tramo pasarela-suiche (demo)")
    latencia_total_ms: float | None = None
    duplicado: bool


class PortafolioOut(BaseModel):
    usuario_id: str
    portafolio: str | None
    unidades: str
    valor_unidad: str
    saldo: str
    composicion: dict[str, int]
    aportes: int
    leccion: Leccion | None


class Error(BaseModel):
    codigo: str
    mensaje: str


# ---------------------------------------------------------------- Pasarela simulada
class TokenIn(BaseModel):
    pan: str = Field(..., description="SOLO números de tarjeta de PRUEBA", examples=["4111111111111111"])


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
