"""Fideicomiso SIMULADO · Sesión 3: un banco fiduciario con el catálogo de 5 fideicomisos.

- Cada fideicomiso del catálogo (`app/core/catalogo.py`) tiene su propio valor de unidad.
- Las unidades se asignan al confirmarse la captura: unidades = monto / valor de la unidad.
- InvierteYa PROPONE las órdenes por lote para cada fideicomiso; el fiduciario las APRUEBA y
  las instruye a la casa de bolsa. El banco, la casa de bolsa y la CVV están simulados.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

from app.core.catalogo import FIDEICOMISO_POR_DEFECTO, FIDEICOMISOS, IDS

CATALOGO = {f["id"]: f for f in FIDEICOMISOS}

# Compatibilidad Sesión 2: los 3 portafolios fijos se mapean al fideicomiso por defecto de cada
# perfil (mismo valor de unidad: 1,25 · 1,32 · 1,40). Lo siguen usando scripts antiguos.
PORTAFOLIOS = {perfil: {"fideicomiso_id": fid, "valor_unidad": CATALOGO[fid]["valor_unidad"],
                        "composicion": CATALOGO[fid]["composicion"]}
               for perfil, fid in FIDEICOMISO_POR_DEFECTO.items()}
CUATRO_DECIMALES = Decimal("0.0001")


def a_dolares(centavos: int) -> Decimal:
    return (Decimal(centavos) / 100).quantize(Decimal("0.01"))


def _resolver(fideicomiso_o_perfil: str) -> str:
    """Acepta un id del catálogo o, por compatibilidad S2, un perfil (CONSERVADOR/...)."""
    return FIDEICOMISO_POR_DEFECTO.get(fideicomiso_o_perfil, fideicomiso_o_perfil)


def calcular_unidades(monto_centavos: int, fideicomiso_id: str,
                      valor_unidad: Decimal | None = None) -> Decimal:
    valor = valor_unidad if valor_unidad is not None else CATALOGO[_resolver(fideicomiso_id)]["valor_unidad"]
    return (a_dolares(monto_centavos) / valor).quantize(CUATRO_DECIMALES, rounding=ROUND_DOWN)


class FideicomisoSimulado:
    """Agrupa el banco fiduciario (cuenta + aprobación), la casa de bolsa y la CVV simulados."""

    def __init__(self):
        self.efectivo = {f: 0 for f in IDS}                         # centavos sin invertir
        self.posiciones = {f: {"renta_fija": 0, "fondos": 0, "acciones": 0} for f in IDS}
        self.abonos: dict[str, int] = {}                             # fecha -> abono (centavos)
        self.abonos_por_fideicomiso: dict[str, dict[str, int]] = {}  # fecha -> {fid: centavos}
        self.ordenes_ejecutadas: list[dict] = []

    # --- banco fiduciario: recibe el abono T+1 (adquirente + cobertura de InvierteYa) ---
    def recibir_abono(self, fecha: str, abono_centavos: int, aportes_por_fideicomiso: dict[str, int]):
        self.abonos[fecha] = self.abonos.get(fecha, 0) + abono_centavos
        del_dia = self.abonos_por_fideicomiso.setdefault(fecha, {})
        # El efectivo se registra en cada fideicomiso según los aportes asignados.
        for fid, monto in aportes_por_fideicomiso.items():
            fid = _resolver(fid)
            self.efectivo[fid] += monto
            del_dia[fid] = del_dia.get(fid, 0) + monto

    # --- InvierteYa propone ---
    @staticmethod
    def proponer_ordenes(aportes_por_fideicomiso: dict[str, int]) -> list[dict]:
        propuesta = []
        for fid, total in aportes_por_fideicomiso.items():
            fid = _resolver(fid)
            if total <= 0:
                continue
            for instrumento, pct in CATALOGO[fid]["composicion"].items():
                if pct <= 0:
                    continue
                propuesta.append({"fideicomiso_id": fid, "instrumento": instrumento,
                                  "monto_centavos": total * pct // 100})
            # el redondeo sobrante queda en efectivo
        return propuesta

    # --- el fiduciario aprueba e instruye; casa de bolsa ejecuta; CVV custodia ---
    def aprobar_y_ejecutar(self, propuesta: list[dict]) -> dict:
        por_fid: dict[str, int] = {}
        for o in propuesta:
            por_fid[o["fideicomiso_id"]] = por_fid.get(o["fideicomiso_id"], 0) + o["monto_centavos"]
        rechazadas = [f for f, monto in por_fid.items() if monto > self.efectivo[f]]
        if rechazadas:
            return {"aprobada": False, "motivo": f"Fondos insuficientes en: {', '.join(rechazadas)}",
                    "nota": "El dinero queda en efectivo y la propuesta se corrige al día siguiente."}
        for o in propuesta:
            self.efectivo[o["fideicomiso_id"]] -= o["monto_centavos"]
            # Simplificación: se compra al valor de mercado actual (sin variación de precio).
            self.posiciones[o["fideicomiso_id"]][o["instrumento"]] += o["monto_centavos"]
            self.ordenes_ejecutadas.append(o)
        return {"aprobada": True, "ordenes": len(propuesta),
                "por_fideicomiso": {f: {"ordenes": sum(1 for o in propuesta if o["fideicomiso_id"] == f),
                                        "monto_centavos": m} for f, m in por_fid.items()},
                "nota": "Títulos registrados en la CVV a nombre de cada fideicomiso (simulado)."}

    # --- estado de posiciones valorizado (insumo del nivel 3) ---
    def estado_posiciones(self) -> dict[str, int]:
        return {f: sum(self.posiciones[f].values()) + self.efectivo[f] for f in IDS}
