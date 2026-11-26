"""Módulo de auditoría inmutable y hardening HTTP para InvierteYa (Sesión 3).

Implementa:
- Bitácora cronológica inmutable encadenada por hash SHA-256 (Res. SUDEBAN 001.21
  y contrato `docs/equipo/CONTRATO_API_S3.md`).
- Middleware de cabeceras de seguridad HTTP y configuración CORS restrictiva.
- Middleware de auditoría automática para operaciones sensibles en `/v1/...`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.middleware.base import BaseHTTPMiddleware

    _FASTAPI_DISPONIBLE = True
except ImportError:  # pragma: no cover - permite probar BitacoraAuditoria sin FastAPI
    FastAPI = Any  # type: ignore[misc,assignment]
    Request = Any  # type: ignore[misc,assignment]
    CORSMiddleware = None  # type: ignore[assignment]
    BaseHTTPMiddleware = object  # type: ignore[misc,assignment]
    _FASTAPI_DISPONIBLE = False

HASH_GENESIS = "0" * 64
ORIGENES_CORS_DEFECTO = (
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://localhost:5173",
)

_RUTAS_SENSIBLES: tuple[tuple[str, re.Pattern[str], str, str, str], ...] = (
    (
        "POST",
        re.compile(r"^/v1/aportes/?$"),
        "APORTE",
        "usuario_app",
        "pasarela_y_fideicomiso",
    ),
    (
        "POST",
        re.compile(r"^/v1/usuarios/(?P<usuario_id>[^/]+)/adhesion/?$"),
        "ADHESION_FIDEICOMISO",
        "usuario_app",
        "fideicomiso_bancario",
    ),
    (
        "POST",
        re.compile(r"^/v1/usuarios/(?P<usuario_id>[^/]+)/perfil/?$"),
        "EVALUACION_PERFIL",
        "usuario_app",
        "motor_ia_perfil",
    ),
    (
        "PATCH",
        re.compile(r"^/v1/usuarios/(?P<usuario_id>[^/]+)/perfil/tanda2/?$"),
        "ACTUALIZACION_PERFIL_TANDA2",
        "usuario_app",
        "motor_ia_perfil",
    ),
    (
        "POST",
        re.compile(r"^/v1/usuarios/(?P<usuario_id>[^/]+)/perfil/revision/?$"),
        "SOLICITUD_REVISION_PERFIL",
        "usuario_app",
        "asesor_humano",
    ),
    (
        "DELETE",
        re.compile(r"^/v1/usuarios/(?P<usuario_id>[^/]+)/datos-personales/?$"),
        "SUPRESION_HABEAS_DATA",
        "usuario_app",
        "repositorio_datos_personales",
    ),
)


@dataclass(frozen=True)
class RegistroAuditoria:
    """Entrada inmutable de la bitácora cronológica encadenada por SHA-256."""

    timestamp: str
    usuario_id: str
    ip: str
    operacion: str
    origen: str
    destino: str
    hash_previo: str
    hash_actual: str

    def a_dict(self) -> dict[str, str]:
        """Devuelve una copia serializable del registro."""
        return asdict(self)


def _calcular_hash_registro(
    *,
    timestamp: str,
    usuario_id: str,
    ip: str,
    operacion: str,
    origen: str,
    destino: str,
    hash_previo: str,
) -> str:
    """Calcula el SHA-256 canónico del registro vinculado al hash anterior."""
    carga = json.dumps(
        {
            "timestamp": timestamp,
            "usuario_id": usuario_id,
            "ip": ip,
            "operacion": operacion,
            "origen": origen,
            "destino": destino,
            "hash_previo": hash_previo,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(carga.encode("utf-8")).hexdigest()


class BitacoraAuditoria:
    """Bitácora append-only con encadenamiento SHA-256 para trazabilidad regulatoria."""

    def __init__(self, ruta_archivo: str | Path | None = None) -> None:
        self._lock = threading.Lock()
        self._ruta = Path(ruta_archivo) if ruta_archivo else None
        self._registros: list[RegistroAuditoria] = []
        if self._ruta and self._ruta.exists():
            self._cargar_desde_archivo()

    def _cargar_desde_archivo(self) -> None:
        assert self._ruta is not None
        lineas = self._ruta.read_text(encoding="utf-8").splitlines()
        for linea in lineas:
            if not linea.strip():
                continue
            datos = json.loads(linea)
            self._registros.append(RegistroAuditoria(**datos))

    def registrar(
        self,
        *,
        usuario_id: str,
        ip: str,
        operacion: str,
        origen: str,
        destino: str,
        timestamp: str | None = None,
    ) -> RegistroAuditoria:
        """Agrega un evento al final de la cadena y calcula su hash enlazado."""
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        with self._lock:
            hash_previo = (
                self._registros[-1].hash_actual if self._registros else HASH_GENESIS
            )
            hash_actual = _calcular_hash_registro(
                timestamp=ts,
                usuario_id=usuario_id,
                ip=ip,
                operacion=operacion,
                origen=origen,
                destino=destino,
                hash_previo=hash_previo,
            )
            registro = RegistroAuditoria(
                timestamp=ts,
                usuario_id=usuario_id,
                ip=ip,
                operacion=operacion,
                origen=origen,
                destino=destino,
                hash_previo=hash_previo,
                hash_actual=hash_actual,
            )
            self._registros.append(registro)
            if self._ruta:
                self._ruta.parent.mkdir(parents=True, exist_ok=True)
                with self._ruta.open("a", encoding="utf-8") as archivo:
                    archivo.write(json.dumps(registro.a_dict(), ensure_ascii=False) + "\n")
            return registro

    def verificar_integridad(self) -> bool:
        """Verifica que toda la cadena de hashes sea íntegra desde el bloque génesis."""
        with self._lock:
            hash_esperado_previo = HASH_GENESIS
            for registro in self._registros:
                if registro.hash_previo != hash_esperado_previo:
                    return False
                hash_recalculado = _calcular_hash_registro(
                    timestamp=registro.timestamp,
                    usuario_id=registro.usuario_id,
                    ip=registro.ip,
                    operacion=registro.operacion,
                    origen=registro.origen,
                    destino=registro.destino,
                    hash_previo=registro.hash_previo,
                )
                if registro.hash_actual != hash_recalculado:
                    return False
                hash_esperado_previo = registro.hash_actual
            return True

    def listar(
        self,
        *,
        usuario_id: str | None = None,
        operacion: str | None = None,
        limite: int | None = None,
    ) -> list[dict[str, str]]:
        """Devuelve los registros en formato dict, filtrados opcionalmente."""
        with self._lock:
            filtrados = [
                r.a_dict()
                for r in self._registros
                if (usuario_id is None or r.usuario_id == usuario_id)
                and (operacion is None or r.operacion == operacion)
            ]
        if limite is not None and limite >= 0:
            return filtrados[-limite:] if limite > 0 else []
        return filtrados

    def reiniciar(self) -> None:
        """Limpia los registros en memoria (y el archivo asociado si existe)."""
        with self._lock:
            self._registros.clear()
            if self._ruta and self._ruta.exists():
                self._ruta.unlink()


def obtener_origenes_cors() -> list[str]:
    """Lee orígenes CORS permitidos desde INVIERTEYA_CORS_ORIGINS o usa valores locales."""
    crudo = os.getenv("INVIERTEYA_CORS_ORIGINS", "")
    if not crudo.strip():
        return list(ORIGENES_CORS_DEFECTO)
    return [origen.strip() for origen in crudo.split(",") if origen.strip()]


def _extraer_ip_cliente(request: Request) -> str:
    """Obtiene la IP del cliente priorizando X-Forwarded-For cuando existe proxy."""
    reintento = request.headers.get("x-forwarded-for")
    if reintento:
        return reintento.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "desconocida"


def _coincide_ruta_sensible(
    metodo: str, ruta: str
) -> tuple[str, str, str, str | None] | None:
    """Identifica si la petición corresponde a una operación sujeta a auditoría."""
    metodo_upper = metodo.upper()
    for metodo_regla, patron, operacion, origen, destino in _RUTAS_SENSIBLES:
        if metodo_upper != metodo_regla:
            continue
        match = patron.match(ruta)
        if match:
            usuario_id = match.groupdict().get("usuario_id")
            return operacion, origen, destino, usuario_id
    return None


class MiddlewareSeguridadHTTP(BaseHTTPMiddleware):
    """Agrega cabeceras HTTP de endurecimiento defensivo a todas las respuestas."""

    _CSP_ESTRICTA = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    _CSP_SWAGGER = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "font-src 'self' data: https://cdn.jsdelivr.net; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        ruta = request.url.path
        es_docs = ruta.startswith("/docs") or ruta.startswith("/redoc")

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            self._CSP_SWAGGER if es_docs else self._CSP_ESTRICTA,
        )
        return response


class MiddlewareAuditoria(BaseHTTPMiddleware):
    """Registra automáticamente operaciones sensibles en BitacoraAuditoria."""

    def __init__(self, app, bitacora: BitacoraAuditoria) -> None:
        super().__init__(app)
        self.bitacora = bitacora

    async def dispatch(self, request: Request, call_next):
        regla = _coincide_ruta_sensible(request.method, request.url.path)
        if regla is None:
            return await call_next(request)

        operacion, origen, destino, usuario_id = regla
        if usuario_id is None:
            cuerpo = await request.body()
            if cuerpo:
                try:
                    payload = json.loads(cuerpo)
                    if isinstance(payload, dict) and payload.get("usuario_id"):
                        usuario_id = str(payload["usuario_id"])
                except (ValueError, UnicodeDecodeError):
                    usuario_id = None

        response = await call_next(request)
        sufijo_estado = "OK" if response.status_code < 400 else f"HTTP_{response.status_code}"
        self.bitacora.registrar(
            usuario_id=usuario_id or "no_identificado",
            ip=_extraer_ip_cliente(request),
            operacion=f"{operacion}:{sufijo_estado}",
            origen=origen,
            destino=destino,
        )
        return response


def configurar_seguridad(
    app: FastAPI,
    *,
    bitacora: BitacoraAuditoria | None = None,
    origenes_cors: list[str] | None = None,
) -> BitacoraAuditoria:
    """Conecta CORS restrictivo, cabeceras seguras y auditoría inmutable en FastAPI."""
    if not _FASTAPI_DISPONIBLE:
        raise RuntimeError(
            "FastAPI y Starlette son requeridos para configurar_seguridad()."
        )

    bitacora_activa = bitacora or BitacoraAuditoria()
    origenes = origenes_cors if origenes_cors is not None else obtener_origenes_cors()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origenes,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )
    app.add_middleware(MiddlewareAuditoria, bitacora=bitacora_activa)
    app.add_middleware(MiddlewareSeguridadHTTP)
    app.state.bitacora_auditoria = bitacora_activa
    return bitacora_activa
