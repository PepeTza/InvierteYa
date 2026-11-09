"""API de InvierteYa (prototipo de la Sesión 2) + pasarela de pago SIMULADA.

Ejecutar:
    pip install -r requirements.txt
    uvicorn app.main:app --reload
Luego abrir http://127.0.0.1:8000/docs  (Swagger UI con la especificación OpenAPI 3)
La especificación en JSON queda en http://127.0.0.1:8000/openapi.json

Autenticación SIMULADA: enviar el encabezado  Authorization: Bearer demo-token
(en producción sería OAuth2/JWT validado en el API Gateway).
"""
import os
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api import esquemas as E
from app.core import tutor
from app.core.perfil import Cuestionario
from app.core.servicio import ErrorNegocio, InvierteYa

app = FastAPI(
    title="InvierteYa API (prototipo · Sesión 2)",
    version="0.2.0",
    description=(
        "Inversión fraccionada desde $5 a través de un **fideicomiso** administrado por un banco, "
        "con perfil de riesgo y tutor didáctico.\n\n"
        "**Todo lo externo está SIMULADO:** pasarela, adquirente, suiche, emisor, banco fiduciario, "
        "casa de bolsa y CVV. Solo datos sintéticos."
    ),
    openapi_tags=[
        {"name": "Usuarios", "description": "Registro, KYC simulado y contrato de adhesión"},
        {"name": "Perfil y tutor", "description": "Cuestionario, perfil de riesgo y lecciones"},
        {"name": "Aportes", "description": "Autorización, captura, asignación de unidades y reverso"},
        {"name": "Operaciones", "description": "Cierre del día: conciliación en 3 niveles y batch"},
        {"name": "Pasarela simulada", "description": "Lo que expone la pasarela aliada (mock)"},
    ],
)

servicio = InvierteYa()
seguridad = HTTPBearer(description="Simulado: usar el token `demo-token`")
TOKEN_DEMO = os.getenv("INVIERTEYA_TOKEN_DEMO", "demo-token")


def autenticado(cred: HTTPAuthorizationCredentials = Depends(seguridad)):
    if cred.credentials != TOKEN_DEMO:
        raise HTTPException(status_code=401, detail="Token inválido")


@app.exception_handler(ErrorNegocio)
def manejar_error_negocio(_, exc: ErrorNegocio):
    codigo_http = 404 if exc.codigo == "USUARIO_NO_EXISTE" else 422
    return JSONResponse(status_code=codigo_http, content={"codigo": exc.codigo, "mensaje": exc.mensaje})


def _usuario_out(u) -> E.UsuarioOut:
    return E.UsuarioOut(usuario_id=u.id, nombre=u.nombre, kyc_aprobado=u.kyc_aprobado,
                        adhesion_firmada=u.adhesion_firmada, perfil=u.perfil)


# ------------------------------------------------------------------ API InvierteYa
v1 = APIRouter(prefix="/v1", dependencies=[Depends(autenticado)])


@v1.post("/usuarios", response_model=E.UsuarioOut, status_code=201, tags=["Usuarios"])
def registrar(datos: E.RegistroIn):
    return _usuario_out(servicio.registrar(datos.nombre, datos.email))


@v1.post("/usuarios/{usuario_id}/kyc", tags=["Usuarios"],
         responses={404: {"model": E.Error}})
def kyc(usuario_id: str):
    """Proveedor de KYC SIMULADO (siempre aprueba). El resultado se comparte con el banco fiduciario."""
    return servicio.aprobar_kyc(usuario_id)


@v1.post("/usuarios/{usuario_id}/adhesion", tags=["Usuarios"],
         responses={404: {"model": E.Error}, 422: {"model": E.Error}})
def adhesion(usuario_id: str, datos: E.AdhesionIn):
    """Firma digital del contrato de adhesión: el usuario pasa a ser fideicomitente y beneficiario."""
    return servicio.firmar_adhesion(usuario_id, datos.acepta)


@v1.post("/usuarios/{usuario_id}/perfil", response_model=E.PerfilOut, tags=["Perfil y tutor"],
         responses={404: {"model": E.Error}})
def perfil(usuario_id: str, c: E.CuestionarioIn):
    """Cuestionario de 10 preguntas. Devuelve perfil, explicación en lenguaje simple y una lección."""
    return servicio.evaluar_perfil(usuario_id, Cuestionario(**c.model_dump()))


@v1.get("/lecciones", response_model=E.Leccion | None, tags=["Perfil y tutor"])
def leccion(paso: E.Paso, perfil: E.Perfil = "CONSERVADOR",
            conocimiento: int = Query(1, ge=1, le=5)):
    """Tutor con contenido predefinido: selecciona la lección según paso, perfil y nivel."""
    return tutor.seleccionar(paso, perfil, conocimiento)


@v1.post("/aportes", response_model=E.AporteOut, status_code=201, tags=["Aportes"],
         responses={404: {"model": E.Error}, 422: {"model": E.Error}})
def crear_aporte(datos: E.AporteIn,
                 idempotency_key: str = Header(..., alias="Idempotency-Key",
                                               description="Evita cobros dobles si se reintenta")):
    """Diagramas 1-3: autoriza, captura y asigna unidades; reversa ante timeout o falla.
    Si se repite la misma Idempotency-Key, devuelve el resultado original (`duplicado: true`)."""
    return servicio.crear_aporte(datos.usuario_id, round(datos.monto * 100), datos.token_tarjeta,
                                 idempotency_key)


@v1.get("/aportes/{aporte_id}", response_model=E.AporteOut, tags=["Aportes"],
        responses={404: {"model": E.Error}})
def ver_aporte(aporte_id: str):
    if aporte_id not in servicio.aportes:
        raise HTTPException(status_code=404, detail="Aporte no encontrado")
    return servicio.aportes[aporte_id]


@v1.get("/usuarios/{usuario_id}/portafolio", response_model=E.PortafolioOut, tags=["Aportes"],
        responses={404: {"model": E.Error}})
def portafolio(usuario_id: str):
    return servicio.portafolio(usuario_id)


@v1.post("/operaciones/cierre", tags=["Operaciones"])
def cierre(fecha: date | None = None, inyectar_descuadre: bool = False):
    """Job T+1: liquidación de la pasarela, abono al fideicomiso, conciliación en 3 niveles y
    propuesta de órdenes por lote (InvierteYa propone, el fiduciario aprueba).
    `inyectar_descuadre=true` simula que la pasarela omite una transacción (para la demo)."""
    return servicio.cerrar_dia(fecha or date.today(), inyectar_descuadre)


@v1.post("/demo/forzar-escenario", tags=["Operaciones"])
def forzar(escenarios: list[str] = Query(..., description=(
        "APROBADA, 51, 05, 59, TIMEOUT, FALLA_CAPTURA, REVERSO_SIN_RESPUESTA")),
           reemplazar: bool = Query(False, description="Vacía la cola antes de agregar los escenarios")):
    """Solo para la demo: fuerza el resultado de las próximas operaciones de la pasarela."""
    if reemplazar:
        servicio.pasarela.forzados.clear()
    servicio.pasarela.forzar(*escenarios)
    return {"forzados": servicio.pasarela.forzados}


@v1.post("/demo/reiniciar", tags=["Operaciones"])
def reiniciar_demo():
    """Solo para la demo: borra usuarios, aportes, cierres y escenarios forzados (todo vive en memoria)."""
    global servicio
    servicio = InvierteYa()
    return {"reiniciado": True}


# ------------------------------------------------------------------ Pasarela simulada
psp = APIRouter(prefix="/pasarela/v1", tags=["Pasarela simulada"])


def _resp(r) -> E.RespuestaPasarela:
    return E.RespuestaPasarela(status=r.status, response_code=r.response_code,
                               authorization_id=r.authorization_id, auth_code=r.auth_code,
                               rrn=r.rrn, latencia_ms=r.latencia_ms, iso=r.iso)


@psp.post("/tokens", response_model=E.TokenOut, status_code=201)
def tokenizar(datos: E.TokenIn):
    """Formulario/SDK de la pasarela: recibe el PAN (solo de PRUEBA) y devuelve un token."""
    return E.TokenOut(token=servicio.pasarela.tokenizar(datos.pan))


@psp.post("/authorizations", response_model=E.RespuestaPasarela)
def autorizar(d: E.AutorizacionIn):
    """ISO 8583 0100/0110 hacia adquirente, suiche y emisor."""
    return _resp(servicio.pasarela.autorizar(d.token, d.amount, d.reference))


@psp.post("/captures", response_model=E.RespuestaPasarela)
def capturar(d: E.CapturaIn):
    """ISO 8583 0220/0230."""
    return _resp(servicio.pasarela.capturar(d.authorization_id, d.amount))


@psp.post("/reversals", response_model=E.RespuestaPasarela)
def reversar(d: E.ReversoIn):
    """ISO 8583 0400/0410 con campo 90; si no hay respuesta, aviso 0420 y repeticiones 0421."""
    return _resp(servicio.pasarela.reversar(d.original_reference, d.reason))


@psp.post("/refunds", response_model=E.RespuestaPasarela)
def devolver(d: E.DevolucionIn):
    """Devolución de un cobro ya capturado (cobros huérfanos detectados en conciliación)."""
    return _resp(servicio.pasarela.devolver(d.authorization_id))


@psp.get("/settlements/{fecha}")
def liquidacion(fecha: date):
    """Archivo de liquidación diario (insumo del nivel 1 de conciliación)."""
    return servicio.pasarela.liquidacion(fecha)


app.include_router(v1)
app.include_router(psp)


# ------------------------------------------------------------------ Front-end (React)
# `cd frontend && npm run build` genera frontend/dist; aquí se sirve en /app (un solo servidor para la demo).
FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND.is_dir():
    app.mount("/app", StaticFiles(directory=FRONTEND, html=True), name="frontend")


@app.get("/", include_in_schema=False)
def inicio():
    if FRONTEND.is_dir():
        return RedirectResponse("/app/")
    return {"servicio": "InvierteYa API (prototipo)", "docs": "/docs", "openapi": "/openapi.json",
            "app": "Compila el front-end: cd frontend && npm install && npm run build"}
