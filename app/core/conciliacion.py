"""Conciliación diaria en tres niveles (diagrama 4)."""
from __future__ import annotations

from decimal import Decimal

from app.core.fideicomiso import PORTAFOLIOS


def nivel1_pagos_vs_liquidacion(aportes: list[dict], liquidacion: dict) -> dict:
    """Cruza los aportes de la BD con el archivo de la pasarela por RRN + cód. autorización + monto."""
    archivo = {(t["rrn"], t["auth_code"]): t for t in liquidacion["transacciones"]
               if t["tipo"] == "CAPTURA"}
    excepciones = []
    vistos = set()
    for a in aportes:
        clave = (a.get("rrn"), a.get("auth_code"))
        if a["estado"] in ("CAPTURADO", "ASIGNADO"):
            fila = archivo.get(clave)
            if fila is None:
                excepciones.append({"tipo": "CAPTURADO_SIN_LIQUIDAR", "aporte_id": a["id"],
                                    "accion": "Reclamo a la pasarela; unidades en revisión"})
            elif fila["monto"] != a["monto_centavos"]:
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


def nivel2_aportes_vs_fideicomiso(aportes_capturados_centavos: int, abono_neto: int,
                                  cobertura_comision: int) -> dict:
    """La pasarela liquida neto de comisión; InvierteYa cubre la comisión con un abono propio,
    así al fideicomiso siempre llega el 100% de lo que aportaron los usuarios."""
    recibido = abono_neto + cobertura_comision
    diferencia = recibido - aportes_capturados_centavos
    exc = [] if diferencia == 0 else [{"tipo": "DIFERENCIA_LIQUIDACION", "diferencia_centavos": diferencia,
                                       "accion": "Ajuste con doble aprobación (fiduciario + InvierteYa)"}]
    return {"nivel": 2, "cuadra": not exc, "capturado": aportes_capturados_centavos,
            "abono_neto_adquirente": abono_neto, "cobertura_comision_invierteya": cobertura_comision,
            "excepciones": exc}


def nivel3_unidades_vs_custodia(unidades_por_portafolio: dict[str, Decimal],
                                posiciones_valorizadas: dict[str, int],
                                cantidad_aportes: dict[str, int]) -> dict:
    """Por portafolio: unidades x valor de la unidad = posiciones valorizadas + efectivo.
    Tolerancia: el truncamiento de unidades a 4 decimales deja centésimas de centavo por aporte."""
    exc, detalle = [], {}
    for p in PORTAFOLIOS:
        valor = PORTAFOLIOS[p]["valor_unidad"]
        esperado = int((unidades_por_portafolio.get(p, Decimal(0)) * valor * 100).to_integral_value())
        custodia = posiciones_valorizadas.get(p, 0)
        tolerancia = 1 + cantidad_aportes.get(p, 0) // 50
        diferencia = custodia - esperado
        detalle[p] = {"unidades_x_valor": esperado, "custodia_mas_efectivo": custodia,
                      "diferencia_centavos": diferencia}
        if abs(diferencia) > tolerancia:
            exc.append({"tipo": "DIFERENCIA_CUSTODIA", "portafolio": p, "diferencia_centavos": diferencia,
                        "accion": "Ajuste con doble aprobación (fiduciario + InvierteYa)"})
    return {"nivel": 3, "cuadra": not exc, "detalle": detalle, "excepciones": exc}
