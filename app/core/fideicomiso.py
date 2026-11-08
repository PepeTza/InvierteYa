"""Fideicomiso SIMULADO: un banco fiduciario y un fideicomiso con tres portafolios.

- Cada portafolio tiene su propio valor de unidad.
- Las unidades se asignan al confirmarse la captura: unidades = monto / valor de la unidad.
- InvierteYa PROPONE las órdenes por lote; el fiduciario las APRUEBA y las instruye a la
  casa de bolsa. Aquí el banco, la casa de bolsa y la CVV están simulados.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN

# Composición: el Conservador viene de la ficha de la Sesión 1; Moderado y Agresivo son supuestos.
PORTAFOLIOS = {
    "CONSERVADOR": {"valor_unidad": Decimal("1.25"),
                    "composicion": {"renta_fija": 70, "fondos": 20, "acciones": 10}},
    "MODERADO": {"valor_unidad": Decimal("1.32"),
                 "composicion": {"renta_fija": 40, "fondos": 30, "acciones": 30}},
    "AGRESIVO": {"valor_unidad": Decimal("1.40"),
                 "composicion": {"renta_fija": 15, "fondos": 25, "acciones": 60}},
}
CUATRO_DECIMALES = Decimal("0.0001")


def a_dolares(centavos: int) -> Decimal:
    return (Decimal(centavos) / 100).quantize(Decimal("0.01"))


def calcular_unidades(monto_centavos: int, portafolio: str) -> Decimal:
    valor = PORTAFOLIOS[portafolio]["valor_unidad"]
    return (a_dolares(monto_centavos) / valor).quantize(CUATRO_DECIMALES, rounding=ROUND_DOWN)


class FideicomisoSimulado:
    """Agrupa el banco fiduciario (cuenta + aprobación), la casa de bolsa y la CVV simulados."""

    def __init__(self):
        self.efectivo = {p: 0 for p in PORTAFOLIOS}                 # centavos sin invertir
        self.posiciones = {p: {"renta_fija": 0, "fondos": 0, "acciones": 0} for p in PORTAFOLIOS}
        self.abonos: dict[str, int] = {}                             # fecha -> abono neto (centavos)
        self.ordenes_ejecutadas: list[dict] = []

    # --- banco fiduciario: recibe el abono T+1 del adquirente ---
    def recibir_abono(self, fecha: str, neto_centavos: int, aportes_por_portafolio: dict[str, int]):
        self.abonos[fecha] = self.abonos.get(fecha, 0) + neto_centavos
        # El efectivo se registra por portafolio según los aportes brutos asignados.
        for p, monto in aportes_por_portafolio.items():
            self.efectivo[p] += monto

    # --- InvierteYa propone ---
    @staticmethod
    def proponer_ordenes(aportes_por_portafolio: dict[str, int]) -> list[dict]:
        propuesta = []
        for p, total in aportes_por_portafolio.items():
            if total <= 0:
                continue
            for instrumento, pct in PORTAFOLIOS[p]["composicion"].items():
                propuesta.append({"portafolio": p, "instrumento": instrumento,
                                  "monto_centavos": total * pct // 100})
            # el redondeo sobrante queda en efectivo
        return propuesta

    # --- el fiduciario aprueba e instruye; casa de bolsa ejecuta; CVV custodia ---
    def aprobar_y_ejecutar(self, propuesta: list[dict]) -> dict:
        por_portafolio: dict[str, int] = {}
        for o in propuesta:
            por_portafolio[o["portafolio"]] = por_portafolio.get(o["portafolio"], 0) + o["monto_centavos"]
        rechazadas = [p for p, monto in por_portafolio.items() if monto > self.efectivo[p]]
        if rechazadas:
            return {"aprobada": False, "motivo": f"Fondos insuficientes en: {', '.join(rechazadas)}",
                    "nota": "El dinero queda en efectivo y la propuesta se corrige al día siguiente."}
        for o in propuesta:
            self.efectivo[o["portafolio"]] -= o["monto_centavos"]
            # Simplificación: se compra al valor de mercado actual (sin variación de precio).
            self.posiciones[o["portafolio"]][o["instrumento"]] += o["monto_centavos"]
            self.ordenes_ejecutadas.append(o)
        return {"aprobada": True, "ordenes": len(propuesta),
                "nota": "Títulos registrados en la CVV a nombre del fideicomiso (simulado)."}

    # --- estado de posiciones valorizado (insumo del nivel 3) ---
    def estado_posiciones(self) -> dict[str, int]:
        return {p: sum(self.posiciones[p].values()) + self.efectivo[p] for p in PORTAFOLIOS}
