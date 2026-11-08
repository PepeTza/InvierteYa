"""Pasarela de pago aliada SIMULADA (incluye adquirente, suiche y emisor).

En la fase 1 InvierteYa se apoya en una pasarela ya certificada. Este módulo
imita su comportamiento para el prototipo:
  - tokeniza la tarjeta (el PAN nunca llega a InvierteYa);
  - responde autorizaciones, capturas, reversos y devoluciones;
  - genera latencias, rechazos y timeouts con probabilidades configurables;
  - entrega el archivo de liquidación diario para la conciliación.
"""
from __future__ import annotations

import random
import secrets
from dataclasses import dataclass, field
from datetime import datetime, date

from app.core import iso8583

TIMEOUT_MS = 30_000  # 30 s, acordado en el diagrama 1


@dataclass
class ConfigPasarela:
    tasa_rechazo_51: float = 0.05          # fondos insuficientes
    tasa_rechazo_05: float = 0.03          # no honrar
    tasa_rechazo_59: float = 0.01          # sospecha de fraude
    tasa_timeout: float = 0.02             # el emisor no responde a tiempo
    tasa_falla_captura: float = 0.005
    tasa_reverso_sin_respuesta: float = 0.10
    comision_pct: float = 0.03             # comisión de la pasarela (supuesto, validar)
    latencia_media_ms: float = 350.0
    semilla: int | None = 42


@dataclass
class Respuesta:
    status: str
    response_code: str | None = None
    authorization_id: str | None = None
    auth_code: str | None = None
    rrn: str | None = None
    latencia_ms: float = 0.0
    iso: list[dict] = field(default_factory=list)


@dataclass
class _Autorizacion:
    id: str
    token: str
    monto: int
    stan: str
    rrn: str
    auth_code: str | None
    momento: datetime
    estado: str  # AUTHORIZED, DECLINED, TIMEOUT, CAPTURED, REVERSED, REVERSAL_PENDING, REFUNDED
    referencia: str
    fecha: date


class PasarelaSimulada:
    def __init__(self, config: ConfigPasarela | None = None):
        self.config = config or ConfigPasarela()
        self.rng = random.Random(self.config.semilla)
        self.tokens: dict[str, str] = {}          # token -> PAN enmascarado
        self.autorizaciones: dict[str, _Autorizacion] = {}
        self._stan = 0
        # Escenarios forzados para demos y pruebas: APROBADA, 51, 05, 59, TIMEOUT,
        # FALLA_CAPTURA, REVERSO_SIN_RESPUESTA (se consumen en orden).
        self.forzados: list[str] = []

    def forzar(self, *escenarios: str):
        self.forzados.extend(escenarios)

    def _forzado(self, opciones: tuple[str, ...]) -> str | None:
        if self.forzados and self.forzados[0] in opciones:
            return self.forzados.pop(0)
        return None

    # ---------- utilidades ----------
    def _siguiente_stan(self) -> str:
        self._stan = (self._stan + 1) % 1_000_000
        return str(self._stan).zfill(6)

    def _rrn(self) -> str:
        return str(self.rng.randint(10**11, 10**12 - 1))

    def _latencia(self) -> float:
        # lognormal: la mayoría cerca de la media, con una cola de transacciones lentas
        return round(self.rng.lognormvariate(0, 0.45) * self.config.latencia_media_ms, 1)

    # ---------- tokenización (formulario/SDK de la pasarela) ----------
    def tokenizar(self, pan: str) -> str:
        """Recibe un PAN SINTÉTICO de prueba y devuelve un token."""
        digitos = "".join(c for c in pan if c.isdigit())
        token = "tok_" + secrets.token_hex(8)
        self.tokens[token] = digitos[:4] + "*" * (len(digitos) - 8) + digitos[-4:]
        return token

    # ---------- autorización: 0100 / 0110 ----------
    def autorizar(self, token: str, monto: int, referencia: str,
                  momento: datetime | None = None) -> Respuesta:
        momento = momento or datetime.now()
        if token not in self.tokens:
            return Respuesta(status="INVALID_TOKEN", response_code="14")
        stan, rrn = self._siguiente_stan(), self._rrn()
        iso = [iso8583.autorizacion(self.tokens[token], monto, stan, momento)]
        r = self.rng.random()
        c = self.config
        aut_id = "auth_" + secrets.token_hex(6)
        forzado = self._forzado(("APROBADA", "51", "05", "59", "TIMEOUT"))
        if forzado:
            r = {"TIMEOUT": 0.0, "51": c.tasa_timeout, "05": c.tasa_timeout + c.tasa_rechazo_51,
                 "59": c.tasa_timeout + c.tasa_rechazo_51 + c.tasa_rechazo_05, "APROBADA": 1.0}[forzado]
            if forzado == "APROBADA":
                r = 0.999999

        if r < c.tasa_timeout:
            estado, codigo, auth_code, latencia = "TIMEOUT", None, None, float(TIMEOUT_MS)
            # El emisor pudo haber aprobado aunque la respuesta se perdió: por eso hay que reversar.
        else:
            latencia = self._latencia()
            umbral = c.tasa_timeout
            if r < (umbral := umbral + c.tasa_rechazo_51):
                estado, codigo = "DECLINED", "51"
            elif r < (umbral := umbral + c.tasa_rechazo_05):
                estado, codigo = "DECLINED", "05"
            elif r < umbral + c.tasa_rechazo_59:
                estado, codigo = "DECLINED", "59"
            else:
                estado, codigo = "AUTHORIZED", "00"
            auth_code = str(self.rng.randint(100000, 999999)) if codigo == "00" else None
            iso.append(iso8583.respuesta_autorizacion(stan, rrn, codigo, auth_code, momento))

        self.autorizaciones[aut_id] = _Autorizacion(
            aut_id, token, monto, stan, rrn, auth_code, momento, estado, referencia, momento.date())
        return Respuesta(status=estado, response_code=codigo, authorization_id=aut_id,
                         auth_code=auth_code, rrn=rrn, latencia_ms=latencia, iso=iso)

    # ---------- captura: 0220 / 0230 ----------
    def capturar(self, authorization_id: str, monto: int,
                 momento: datetime | None = None) -> Respuesta:
        momento = momento or datetime.now()
        a = self.autorizaciones.get(authorization_id)
        if a is None or a.estado != "AUTHORIZED":
            return Respuesta(status="NOT_CAPTURABLE", response_code="12")
        if monto > a.monto:
            return Respuesta(status="AMOUNT_EXCEEDED", response_code="13")
        iso = [iso8583.completacion(monto, a.stan, a.rrn, a.auth_code, momento)]
        latencia = self._latencia()
        if self._forzado(("FALLA_CAPTURA",)) or self.rng.random() < self.config.tasa_falla_captura:
            iso.append(iso8583.respuesta_completacion(a.stan, "96", momento))
            return Respuesta(status="CAPTURE_FAILED", response_code="96", authorization_id=a.id,
                             rrn=a.rrn, latencia_ms=latencia, iso=iso)
        a.estado = "CAPTURED"
        iso.append(iso8583.respuesta_completacion(a.stan, "00", momento))
        return Respuesta(status="CAPTURED", response_code="00", authorization_id=a.id,
                         auth_code=a.auth_code, rrn=a.rrn, latencia_ms=latencia, iso=iso)

    # ---------- reverso: 0400 / 0410 (0421 si no hay respuesta) ----------
    def reversar(self, authorization_id: str, motivo: str,
                 momento: datetime | None = None) -> Respuesta:
        momento = momento or datetime.now()
        a = self.autorizaciones.get(authorization_id)
        if a is None:
            return Respuesta(status="NOT_FOUND", response_code="25")
        if a.estado in ("REVERSED", "DECLINED"):
            return Respuesta(status=a.estado, authorization_id=a.id, rrn=a.rrn)  # idempotente
        if a.estado == "CAPTURED":
            return Respuesta(status="ALREADY_CAPTURED_USE_REFUND", response_code="12",
                             authorization_id=a.id)
        stan = self._siguiente_stan()
        campo90 = iso8583.datos_originales("0100", a.stan, a.momento)
        iso = [iso8583.reverso(a.monto, stan, campo90, momento)]
        latencia = self._latencia()
        if (self._forzado(("REVERSO_SIN_RESPUESTA",))
                or self.rng.random() < self.config.tasa_reverso_sin_respuesta):
            for _ in range(3):  # 3 reintentos con aviso repetido, cada 60 s
                iso.append(iso8583.reverso(a.monto, stan, campo90, momento, repetido=True))
            a.estado = "REVERSAL_PENDING"
            return Respuesta(status="REVERSAL_PENDING", authorization_id=a.id, rrn=a.rrn,
                             latencia_ms=latencia, iso=iso)
        a.estado = "REVERSED"
        iso.append(iso8583.respuesta_reverso(stan, "00", momento))
        return Respuesta(status="REVERSED", response_code="00", authorization_id=a.id,
                         rrn=a.rrn, latencia_ms=latencia, iso=iso)

    # ---------- devolución (para cobros huérfanos detectados en la conciliación) ----------
    def devolver(self, authorization_id: str) -> Respuesta:
        a = self.autorizaciones.get(authorization_id)
        if a is None or a.estado != "CAPTURED":
            return Respuesta(status="NOT_REFUNDABLE", response_code="12")
        a.estado = "REFUNDED"
        return Respuesta(status="REFUNDED", response_code="00", authorization_id=a.id, rrn=a.rrn)

    # ---------- archivo de liquidación (insumo del nivel 1 de conciliación) ----------
    def liquidacion(self, fecha: date) -> dict:
        filas = []
        for a in self.autorizaciones.values():
            if a.fecha != fecha or a.estado not in ("CAPTURED", "REFUNDED"):
                continue
            comision = round(a.monto * self.config.comision_pct)
            filas.append({"authorization_id": a.id, "rrn": a.rrn, "auth_code": a.auth_code,
                          "monto": a.monto, "comision": comision, "tipo": "CAPTURA",
                          "referencia": a.referencia})
            if a.estado == "REFUNDED":
                filas.append({"authorization_id": a.id, "rrn": a.rrn, "auth_code": a.auth_code,
                              "monto": -a.monto, "comision": -comision, "tipo": "DEVOLUCION",
                              "referencia": a.referencia})
        bruto = sum(f["monto"] for f in filas)
        comisiones = sum(f["comision"] for f in filas)
        return {"fecha": fecha.isoformat(), "transacciones": filas, "total_bruto": bruto,
                "total_comisiones": comisiones, "total_neto": bruto - comisiones,
                "iso_cierre": iso8583.reconciliacion(len(filas), bruto, datetime.now())}
