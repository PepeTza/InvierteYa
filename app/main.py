"""API de InvierteYa (MVP · Sesión 3) + banco fiduciario y pasarela de pago SIMULADOS.

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

from fastapi import APIRouter, Body, Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api import esquemas as E
from app.core import catalogo as cat
from app.core import tutor
from app.core.auditoria import configurar_seguridad
from app.core.perfil import Cuestionario
from app.core.servicio import ErrorNegocio, InvierteYa

app = FastAPI(
    title="InvierteYa API (MVP · Sesión 3)",
    version="0.3.0",
    description=(
        "Inversión fraccionada desde $5 a través de un **catálogo de 5 fideicomisos** administrados por "
        "un banco, con perfil de riesgo explicable (cuestionario en 2 tandas), aporte repartido, IA "
        "predictiva (abandono y flujos) y protección de datos (AES-256-GCM, habeas data, k ≥ 10).\n\n"
        "**Todo lo externo está SIMULADO:** pasarela, adquirente, suiche, emisor, banco fiduciario, "
        "casa de bolsa, CVV y KMS. Solo datos sintéticos."
    ),
    openapi_tags=[
        {"name": "Usuarios", "description": "Registro, KYC simulado y contrato de adhesión por fideicomiso"},
        {"name": "Fideicomisos", "description": "Catálogo del banco etiquetado por idoneidad"},
        {"name": "Perfil y tutor", "description": "Cuestionario en 2 tandas, perfil, revisión humana y lecciones"},
        {"name": "Aportes", "description": "Aporte repartido, comisiones, unidades por fideicomiso y reverso"},
        {"name": "IA predictiva", "description": "Riesgo de abandono (solo sugiere) y pronóstico de flujos"},
        {"name": "Privacidad", "description": "Consentimiento, habeas data (art. 28) e informes agregados Oro"},
        {"name": "Operaciones", "description": "Cierre del día (conciliación por fideicomiso), batch, KMS y auditoría"},
        {"name": "Banco fiduciario simulado", "description": "Catálogo que publica el banco (mock)"},
        {"name": "Pasarela simulada", "description": "Lo que expone la pasarela aliada (mock)"},
    ],
)
# Hardening (Track 4 · Ronald): CORS restrictivo, cabeceras HTTP seguras y bitácora inmutable
# encadenada por SHA-256 de las operaciones sensibles (Res. SUDEBAN 001.21).
bitacora = configurar_seguridad(app)

servicio = InvierteYa()
seguridad = HTTPBearer(description="Simulado: usar el token `demo-token`")
TOKEN_DEMO = os.getenv("INVIERTEYA_TOKEN_DEMO", "demo-token")


def autenticado(cred: HTTPAuthorizationCredentials = Depends(seguridad)):
    if cred.credentials != TOKEN_DEMO:
        raise HTTPException(status_code=401, detail="Token inválido")


@app.exception_handler(ErrorNegocio)
def manejar_error_negocio(_, exc: ErrorNegocio):
    codigo_http = {"USUARIO_NO_EXISTE": 404, "PRONOSTICO_NO_DISPONIBLE": 503}.get(exc.codigo, 422)
    return JSONResponse(status_code=codigo_http, content={"codigo": exc.codigo, "mensaje": exc.mensaje})


def _usuario_out(u) -> E.UsuarioOut:
    return E.UsuarioOut(usuario_id=u.id, nombre=u.nombre, kyc_aprobado=u.kyc_aprobado,
                        adhesion_firmada=u.adhesion_firmada, perfil=u.perfil)


# ------------------------------------------------------------------ API InvierteYa
v1 = APIRouter(prefix="/v1", dependencies=[Depends(autenticado)])


@v1.post("/usuarios", response_model=E.UsuarioOut, status_code=201, tags=["Usuarios"])
def registrar(datos: E.RegistroIn):
    """Registro (datos sintéticos). El email se guarda cifrado con AES-256-GCM."""
    return _usuario_out(servicio.registrar(datos.nombre, datos.email))


@v1.post("/usuarios/{usuario_id}/kyc", response_model=E.KycOut, tags=["Usuarios"],
         responses={404: {"model": E.Error}})
def kyc(usuario_id: str, datos: E.KycIn | None = Body(None)):
    """Proveedor de KYC SIMULADO (siempre aprueba) y aporta la edad, que ya no se pregunta en el
    cuestionario. La edad se guarda cifrada (AES-256-GCM). El resultado se comparte con el fiduciario."""
    return servicio.aprobar_kyc(usuario_id, datos.edad if datos else None)


@v1.post("/usuarios/{usuario_id}/adhesion", response_model=E.AdhesionOut, tags=["Usuarios"],
         responses={404: {"model": E.Error}, 422: {"model": E.Error}})
def adhesion(usuario_id: str, datos: E.AdhesionIn):
    """Firma electrónica del contrato de adhesión **a un fideicomiso del catálogo**: el usuario pasa a ser
    fideicomitente y beneficiario. Guarda sello de tiempo y hash SHA-256 del documento.
    Si el fideicomiso está *Por encima de tu perfil* exige `confirmacion_riesgo_extra: true`
    (si no, `422 CONFIRMACION_RIESGO_REQUERIDA`)."""
    return servicio.firmar_adhesion(usuario_id, datos.acepta, datos.fideicomiso_id,
                                    datos.confirmacion_riesgo_extra)


@v1.get("/fideicomisos", response_model=E.CatalogoOut, tags=["Fideicomisos"],
        responses={404: {"model": E.Error}})
def fideicomisos(usuario_id: str | None = None,
                 riesgo_max: int | None = Query(None, ge=1, le=5, description="Filtro por nivel de riesgo")):
    """Catálogo del banco (caché diaria) con la etiqueta de idoneidad para el perfil del usuario:
    `RECOMENDADO` → `COMPATIBLE` → `POR_ENCIMA_DEL_PERFIL`."""
    return servicio.listar_fideicomisos(usuario_id, riesgo_max)


@v1.post("/usuarios/{usuario_id}/perfil", response_model=E.PerfilOut, tags=["Perfil y tutor"],
         responses={404: {"model": E.Error}, 422: {"model": E.Error}})
def perfil(usuario_id: str, c: E.CuestionarioS3In | E.CuestionarioIn):
    """Tanda 1 del cuestionario conversacional (formato S3; la edad sale del KYC) o el formato de
    10 preguntas de la Sesión 2. Devuelve perfil, explicación simple, qué lo cambiaría y una lección."""
    if isinstance(c, E.CuestionarioS3In):
        return servicio.evaluar_perfil_s3(usuario_id, c.model_dump())
    return servicio.evaluar_perfil(usuario_id, Cuestionario(**c.model_dump()))


@v1.patch("/usuarios/{usuario_id}/perfil/tanda2", response_model=E.PerfilOut, tags=["Perfil y tutor"],
          responses={404: {"model": E.Error}, 422: {"model": E.Error}})
def perfil_tanda2(usuario_id: str, datos: E.Tanda2In):
    """'Afinemos tu perfil': hogar + quiz amistoso. Recalcula con la Tanda 1 guardada."""
    return servicio.completar_tanda2(usuario_id, datos.dependientes, datos.quiz_aciertos)


@v1.post("/usuarios/{usuario_id}/perfil/revision", response_model=E.RevisionOut, status_code=201,
         tags=["Perfil y tutor"], responses={404: {"model": E.Error}, 422: {"model": E.Error}})
def perfil_revision(usuario_id: str, datos: E.RevisionIn):
    """Botón 'No estoy de acuerdo con mi perfil': el caso pasa a revisión de un asesor humano."""
    return servicio.solicitar_revision(usuario_id, datos.motivo)


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
    """Diagramas 1-3: autoriza, captura y asigna unidades **en cada fideicomiso de la distribución**;
    reversa ante timeout o falla. Comisión transparente: 1% de aporte + 2% de recargo solo con TARJETA
    (se cobra encima: se invierte el 100% del monto). Si se repite la misma Idempotency-Key, devuelve
    el resultado original (`duplicado: true`)."""
    distribucion = [d.model_dump() for d in datos.distribucion] if datos.distribucion else None
    return servicio.crear_aporte(datos.usuario_id, round(datos.monto * 100), datos.token_tarjeta,
                                 idempotency_key, distribucion=distribucion, medio_pago=datos.medio_pago)


@v1.get("/aportes/{aporte_id}", response_model=E.AporteOut, tags=["Aportes"],
        responses={404: {"model": E.Error}})
def ver_aporte(aporte_id: str):
    if aporte_id not in servicio.aportes:
        raise HTTPException(status_code=404, detail="Aporte no encontrado")
    return servicio.aportes[aporte_id]


@v1.get("/usuarios/{usuario_id}/portafolio", response_model=E.PortafolioOut, tags=["Aportes"],
        responses={404: {"model": E.Error}})
def portafolio(usuario_id: str):
    """Consolidado total y desglose por fideicomiso."""
    return servicio.portafolio(usuario_id)


# ---------- IA predictiva (Daniel: ia/predictor_abandono.py · ia/pronostico_flujos.py)
@v1.get("/usuarios/{usuario_id}/riesgo-abandono", response_model=E.RiesgoAbandonoOut,
        tags=["IA predictiva"], responses={404: {"model": E.Error}})
def riesgo_abandono(usuario_id: str, simular_inactivo: bool = Query(
        False, description="Solo demo: simula un usuario inactivo para mostrar el aviso suave")):
    """Probabilidad de que el usuario deje de ahorrar en 60 días. **Solo sugiere** un recordatorio:
    nunca mueve dinero, cambia el perfil ni cobra. Respeta el consentimiento `alertas_ahorro`."""
    return servicio.riesgo_abandono(usuario_id, simular_inactivo)


@v1.get("/fiduciario/pronostico-flujos", response_model=E.PronosticoOut, tags=["IA predictiva"],
        responses={503: {"model": E.Error}})
def pronostico_flujos():
    """Pronóstico de flujos netos por fideicomiso (mañana y 7 días) para planificar los lotes."""
    return servicio.pronostico_flujos()


# ---------- Privacidad y habeas data
@v1.put("/usuarios/{usuario_id}/consentimiento", response_model=E.ConsentimientoOut, tags=["Privacidad"],
        responses={404: {"model": E.Error}, 422: {"model": E.Error}})
def consentimiento(usuario_id: str, datos: E.ConsentimientoIn):
    """Otorga o retira, en cualquier momento, consentimientos separados de los términos."""
    return servicio.actualizar_consentimiento(usuario_id, datos.informes_agregados, datos.alertas_ahorro)


@v1.get("/usuarios/{usuario_id}/datos-personales", response_model=E.DatosPersonalesOut, tags=["Privacidad"],
        responses={404: {"model": E.Error}})
def datos_personales(usuario_id: str):
    """Derecho de acceso (Constitución art. 28): qué datos guardamos, para qué, con quién y cómo se protegen."""
    return servicio.datos_personales(usuario_id)


@v1.delete("/usuarios/{usuario_id}/datos-personales", response_model=E.SupresionOut, tags=["Privacidad"],
           responses={404: {"model": E.Error}})
def suprimir_datos_personales(usuario_id: str):
    """Derecho de supresión: anonimiza los datos de uso; conserva solo el registro contable (LC/FT)."""
    return servicio.suprimir_datos(usuario_id)


@v1.get("/fiduciario/informe-agregado", response_model=E.InformeAgregadoOut, tags=["Privacidad"])
def informe_agregado():
    """Capa Oro: saldo por perfil y fideicomiso de quienes consintieron; las celdas con < 10 personas
    se suprimen. Nunca se comparten ni venden datos individuales."""
    return servicio.informe_agregado()


# ---------- Operaciones
@v1.post("/operaciones/cierre", tags=["Operaciones"])
def cierre(fecha: date | None = None, inyectar_descuadre: bool = False):
    """Job T+1: liquidación de la pasarela, abono a cada fideicomiso, conciliación en 3 niveles por
    fideicomiso y propuesta de órdenes por lote (InvierteYa propone, el fiduciario aprueba).
    `inyectar_descuadre=true` simula que la pasarela omite una transacción (para la demo)."""
    return servicio.cerrar_dia(fecha or date.today(), inyectar_descuadre)


@v1.post("/operaciones/kms/rotar", response_model=E.RotacionLlavesOut, tags=["Operaciones"])
def rotar_llaves():
    """KMS SIMULADO: rota la llave maestra y re-envuelve las llaves de datos (los datos no se re-cifran)."""
    return servicio.rotar_llaves()


@v1.get("/operaciones/auditoria", tags=["Operaciones"])
def auditoria(usuario_id: str | None = None, limite: int = Query(50, ge=1, le=500)):
    """Bitácora inmutable (Res. SUDEBAN 001.21) y verificación de la cadena SHA-256."""
    return {"integra": bitacora.verificar_integridad(),
            "registros": bitacora.listar(usuario_id=usuario_id, limite=limite)}


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


# ------------------------------------------------------------------ Banco fiduciario simulado
banco = APIRouter(prefix="/fiduciario/v1", tags=["Banco fiduciario simulado"])


@banco.get("/fideicomisos", response_model=E.CatalogoBancoOut)
def catalogo_banco():
    """Catálogo que publica el banco fiduciario (simulado). InvierteYa lo cachea una vez al día."""
    return cat.catalogo_banco()


# ------------------------------------------------------------------ Pasarela simulada
psp = APIRouter(prefix="/pasarela/v1", tags=["Pasarela simulada"])


def _resp(r) -> E.RespuestaPasarela:
    return E.RespuestaPasarela(status=r.status, response_code=r.response_code,
                               authorization_id=r.authorization_id, auth_code=r.auth_code,
                               rrn=r.rrn, latencia_ms=r.latencia_ms, iso=r.iso)


@psp.post("/tokens", response_model=E.TokenOut, status_code=201)
def tokenizar(datos: E.TokenIn):
    """Formulario/SDK de la pasarela: recibe el PAN (solo de PRUEBA) o el teléfono de Pago Móvil
    (sintético) y devuelve un token."""
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
app.include_router(banco)
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
    return {"servicio": "InvierteYa API (MVP · Sesión 3)", "docs": "/docs", "openapi": "/openapi.json",
            "app": "Compila el front-end: cd frontend && npm install && npm run build"}
