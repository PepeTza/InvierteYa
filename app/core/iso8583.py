"""Construcción de mensajes ISO 8583 (versión 1987) SIMULADOS.

La pasarela aliada es quien habla ISO 8583 con el adquirente y el suiche.
InvierteYa nunca arma estos mensajes en producción: aquí los generamos
solo para que el prototipo muestre qué ocurre en ese tramo de la cadena
(sirve para la demo, los logs y la tabla de mapeo de las láminas).

Campos usados (verificar contra el estándar antes de presentar):
  2  PAN (enmascarado; el PAN real solo lo ve la pasarela)
  3  Código de proceso      4  Monto (12 dígitos, en centavos)
  7  Fecha/hora transmisión (MMDDhhmmss)
  11 STAN (número de traza) 37 RRN (referencia de recuperación)
  38 Código de autorización 39 Código de respuesta
  41 Terminal               42 Comercio
  49 Moneda (840 = USD)     90 Datos de la transacción original (reversos)
"""
from __future__ import annotations

from datetime import datetime

MTI = {
    "AUTORIZACION": "0100",
    "AUTORIZACION_RESP": "0110",
    "COMPLETACION": "0220",
    "COMPLETACION_RESP": "0230",
    "REVERSO": "0400",
    "REVERSO_RESP": "0410",
    "REVERSO_AVISO_REPETIDO": "0421",
    "RECONCILIACION": "0500",
    "RECONCILIACION_RESP": "0510",
}

TERMINAL_ID = "INVYA001"          # campo 41 (8 caracteres)
COMERCIO_ID = "INVIERTEYA00001"   # campo 42 (15 caracteres)
MONEDA_USD = "840"                # campo 49 (ISO 4217)
CODIGO_PROCESO_COMPRA = "000000"  # campo 3


def _fecha_transmision(momento: datetime) -> str:
    return momento.strftime("%m%d%H%M%S")


def _monto(monto_centavos: int) -> str:
    return str(monto_centavos).zfill(12)


def mensaje(mti: str, momento: datetime, **campos: str) -> dict:
    """Devuelve el mensaje como diccionario {mti, campos} legible en logs."""
    base = {"7": _fecha_transmision(momento)}
    base.update({k.lstrip("c"): v for k, v in campos.items()})
    return {"mti": mti, "campos": dict(sorted(base.items(), key=lambda kv: int(kv[0])))}


def autorizacion(pan_enmascarado: str, monto_centavos: int, stan: str, momento: datetime) -> dict:
    return mensaje(
        MTI["AUTORIZACION"], momento,
        c2=pan_enmascarado, c3=CODIGO_PROCESO_COMPRA, c4=_monto(monto_centavos),
        c11=stan, c41=TERMINAL_ID, c42=COMERCIO_ID, c49=MONEDA_USD,
    )


def respuesta_autorizacion(stan: str, rrn: str, codigo: str, auth_code: str | None,
                           momento: datetime) -> dict:
    campos = {"c11": stan, "c37": rrn, "c39": codigo}
    if auth_code:
        campos["c38"] = auth_code
    return mensaje(MTI["AUTORIZACION_RESP"], momento, **campos)


def completacion(monto_centavos: int, stan: str, rrn: str, auth_code: str, momento: datetime) -> dict:
    return mensaje(MTI["COMPLETACION"], momento, c4=_monto(monto_centavos), c11=stan,
                   c37=rrn, c38=auth_code)


def respuesta_completacion(stan: str, codigo: str, momento: datetime) -> dict:
    return mensaje(MTI["COMPLETACION_RESP"], momento, c11=stan, c39=codigo)


def datos_originales(mti_original: str, stan_original: str, momento_original: datetime) -> str:
    """Campo 90: MTI original(4) + STAN(6) + fecha/hora(10) + adquirente(11) + reenviador(11)."""
    return f"{mti_original}{stan_original}{_fecha_transmision(momento_original)}{'0' * 22}"


def reverso(monto_centavos: int, stan: str, campo90: str, momento: datetime,
            repetido: bool = False) -> dict:
    mti = MTI["REVERSO_AVISO_REPETIDO"] if repetido else MTI["REVERSO"]
    return mensaje(mti, momento, c4=_monto(monto_centavos), c11=stan, c90=campo90)


def respuesta_reverso(stan: str, codigo: str, momento: datetime) -> dict:
    return mensaje(MTI["REVERSO_RESP"], momento, c11=stan, c39=codigo)


def reconciliacion(cantidad: int, total_centavos: int, momento: datetime) -> dict:
    # En la práctica 0500 lleva totales en campos 74-97; aquí lo resumimos.
    return {"mti": MTI["RECONCILIACION"], "campos": {
        "7": _fecha_transmision(momento), "74": str(cantidad).zfill(10),
        "88": str(total_centavos).zfill(16)}}
