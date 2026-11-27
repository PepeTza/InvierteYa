"""Conciliación diaria en tres niveles (diagrama 4) · Sesión 3: niveles 2 y 3 por fideicomiso."""
from __future__ import annotations

from decimal import Decimal

from app.core.catalogo import IDS
from app.core.fideicomiso import CATALOGO


def nivel1_pagos_vs_liquidacion(aportes: list[dict], liquidacion: dict) -> dict:
    """Cruza los aportes de la BD con el archivo de la pasarela por RRN + cód. autorización + monto.
    Desde S3 el monto cobrado incluye la comisión de aporte y el recargo del medio de pago."""
    archivo = {(t["rrn"], t["auth_code"]): t for t in liquidacion["transacciones"]
               if t["tipo"] == "CAPTURA"}
    excepciones = []
    vistos = set()
    for a in aportes:
        clave = (a.get("rrn"), a.get("auth_code"))
        if a["estado"] in ("CAPTURADO", "ASIGNADO"):
            fila = archivo.get(clave)
            cobrado = a.get("monto_cobrado_centavos", a["monto_centavos"])
            if fila is None:
                excepciones.append({"tipo": "CAPTURADO_SIN_LIQUIDAR", "aporte_id": a["id"],
                                    "accion": "Reclamo a la pasarela; unidades en revisión"})
            elif fila["monto"] != cobrado:
                excepciones.append({"tipo": "MONTO_DISTINTO", "aporte_id": a["id"],
                                    "accion": "Ajuste con doble aprobación"})
            vistos.add(clave)
        elif a["estado"] == "REVERSO_PENDIENTE":
            excepciones.append({"tipo": "REVERSO_PENDIENTE", "aporte_id": a["id"],
                                "accion": "Confirmar con la pasarela que la autorización no se capturó"})
    for clave, fila in archivo.items():
        if clave not in vistos:
            excepciones.append({"tipo": "COBRO_SIN_APORTE", "authorization_id": fila["authorization_id"],
                                "accion": "Devolución al usuario (POST /refunds)"})
    return {"nivel": 1, "cuadra": not excepciones, "excepciones": excepciones,
            "transacciones_archivo": len(archivo)}


def nivel2_aportes_vs_fideicomiso(aportes_por_fideicomiso: dict[str, int] | int, abono_neto: int,
                                  cobertura_comision: int, comisiones_invierteya: int = 0,
                                  abonado_por_fideicomiso: dict[str, int] | None = None) -> dict:
    """Lo cobrado al usuario = aporte invertido + comisión de aporte + recargo del medio de pago.
    La pasarela liquida neto de su comisión; InvierteYa cubre esa comisión con un abono propio y
    retiene sus ingresos (comisión + recargo), así al fideicomiso llega el 100% del monto invertido.

        abono_neto + cobertura - comisiones_invierteya  ==  Σ aportes asignados

    Además se verifica, fideicomiso por fideicomiso, que el efectivo abonado coincida con lo asignado."""
    if isinstance(aportes_por_fideicomiso, int):            # firma de la Sesión 2
        aportes_por_fideicomiso = {"total": aportes_por_fideicomiso}
    capturado = sum(aportes_por_fideicomiso.values())
    recibido = abono_neto + cobertura_comision - comisiones_invierteya
    diferencia = recibido - capturado
    exc = [] if diferencia == 0 else [{"tipo": "DIFERENCIA_LIQUIDACION", "diferencia_centavos": diferencia,
                                       "accion": "Ajuste con doble aprobación (fiduciario + InvierteYa)"}]
    detalle = {}
    if abonado_por_fideicomiso is not None:
        for fid in sorted(set(aportes_por_fideicomiso) | set(abonado_por_fideicomiso)):
            asignado, abonado = aportes_por_fideicomiso.get(fid, 0), abonado_por_fideicomiso.get(fid, 0)
            detalle[fid] = {"asignado": asignado, "abonado_fideicomiso": abonado,
                            "diferencia_centavos": abonado - asignado}
            if abonado != asignado:
                exc.append({"tipo": "DIFERENCIA_FIDEICOMISO", "fideicomiso_id": fid,
                            "diferencia_centavos": abonado - asignado,
                            "accion": "Reclasificar el abono entre fideicomisos (doble aprobación)"})
    return {"nivel": 2, "cuadra": not exc, "capturado": capturado,
            "abono_neto_adquirente": abono_neto, "cobertura_comision_invierteya": cobertura_comision,
            "ingresos_invierteya_retenidos": comisiones_invierteya,
            "por_fideicomiso": detalle, "excepciones": exc}


def nivel3_unidades_vs_custodia(unidades_por_fideicomiso: dict[str, Decimal],
                                posiciones_valorizadas: dict[str, int],
                                cantidad_aportes: dict[str, int],
                                valores_unidad: dict[str, Decimal] | None = None) -> dict:
    """Por fideicomiso: unidades x valor de la unidad = posiciones valorizadas + efectivo.
    Tolerancia: el truncamiento de unidades a 4 decimales deja centésimas de centavo por aporte."""
    exc, detalle = [], {}
    for fid in IDS:
        valor = (valores_unidad or {}).get(fid, CATALOGO[fid]["valor_unidad"])
        esperado = int((unidades_por_fideicomiso.get(fid, Decimal(0)) * valor * 100).to_integral_value())
        custodia = posiciones_valorizadas.get(fid, 0)
        tolerancia = 1 + cantidad_aportes.get(fid, 0) // 50
        diferencia = custodia - esperado
        detalle[fid] = {"unidades_x_valor": esperado, "custodia_mas_efectivo": custodia,
                        "diferencia_centavos": diferencia}
        if abs(diferencia) > tolerancia:
            exc.append({"tipo": "DIFERENCIA_CUSTODIA", "fideicomiso_id": fid, "diferencia_centavos": diferencia,
                        "accion": "Ajuste con doble aprobación (fiduciario + InvierteYa)"})
    return {"nivel": 3, "cuadra": not exc, "detalle": detalle, "excepciones": exc}
