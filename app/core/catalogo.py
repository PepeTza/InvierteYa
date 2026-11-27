"""Catálogo de fideicomisos del banco fiduciario SIMULADO (Sesión 3 · comentario S2 #1).

- El banco publica su catálogo en `GET /fiduciario/v1/fideicomisos` (endpoint simulado).
- InvierteYa lo consume y lo guarda en una caché diaria (`CatalogoCache`): el valor de la
  unidad lo fija el fiduciario una vez al día, así que no hace falta consultarlo en cada aporte.
- Regla de idoneidad (contrato `docs/equipo/CONTRATO_API_S3.md` §1.2):
    riesgo máximo por perfil  CONSERVADOR -> 2 · MODERADO -> 3 · AGRESIVO -> 5
    etiqueta  RECOMENDADO · COMPATIBLE · POR_ENCIMA_DEL_PERFIL
  Elegir un fideicomiso por encima del perfil NO se bloquea: exige confirmación expresa.

Todos los datos (rendimientos, valores de unidad, composición) son SIMULADOS.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time
from decimal import Decimal
from typing import Callable

# --------------------------------------------------------------------------- catálogo del banco
FIDEICOMISOS: tuple[dict, ...] = (
    {"id": "liq_usd", "nombre": "Liquidez USD", "riesgo": 1, "horizonte": "< 1 año",
     "minimo_usd": 5.0, "comision_anual_pct": 1.0, "rescate_dias": "T+1",
     "valor_unidad": Decimal("1.05"), "rendimiento_anual_simulado_pct": 4.2,
     "composicion": {"renta_fija": 100, "fondos": 0, "acciones": 0}},
    {"id": "rf_usd", "nombre": "Renta Fija USD", "riesgo": 2, "horizonte": "1 a 3 años",
     "minimo_usd": 5.0, "comision_anual_pct": 1.5, "rescate_dias": "T+2",
     "valor_unidad": Decimal("1.25"), "rendimiento_anual_simulado_pct": 6.8,
     "composicion": {"renta_fija": 80, "fondos": 20, "acciones": 0}},
    {"id": "mix_bal", "nombre": "Mixto Balanceado", "riesgo": 3, "horizonte": "3 a 5 años",
     "minimo_usd": 10.0, "comision_anual_pct": 2.0, "rescate_dias": "T+3",
     "valor_unidad": Decimal("1.32"), "rendimiento_anual_simulado_pct": 9.4,
     "composicion": {"renta_fija": 40, "fondos": 30, "acciones": 30}},
    {"id": "acc_bvc", "nombre": "Acciones BVC", "riesgo": 4, "horizonte": "> 5 años",
     "minimo_usd": 10.0, "comision_anual_pct": 2.5, "rescate_dias": "T+3",
     "valor_unidad": Decimal("1.40"), "rendimiento_anual_simulado_pct": 13.5,
     "composicion": {"renta_fija": 15, "fondos": 25, "acciones": 60}},
    {"id": "crec_ves", "nombre": "Crecimiento Bolívares", "riesgo": 5, "horizonte": "> 5 años",
     "minimo_usd": 20.0, "comision_anual_pct": 2.5, "rescate_dias": "T+5",
     "valor_unidad": Decimal("1.18"), "rendimiento_anual_simulado_pct": 16.0,
     "composicion": {"renta_fija": 0, "fondos": 0, "acciones": 100}},
)
IDS = tuple(f["id"] for f in FIDEICOMISOS)

# --------------------------------------------------------------------------- idoneidad
RIESGO_MAXIMO_PERFIL = {"CONSERVADOR": 2, "MODERADO": 3, "AGRESIVO": 5}
# Riesgos que se etiquetan "Recomendado para ti" en cada perfil.
RIESGOS_RECOMENDADOS = {"CONSERVADOR": (2,), "MODERADO": (3,), "AGRESIVO": (4, 5)}
# Fideicomiso por defecto (compatibilidad S2: adhesión/aporte sin `fideicomiso_id`).
# Conservan el valor de unidad de los 3 portafolios de la Sesión 2 (1,25 · 1,32 · 1,40).
FIDEICOMISO_POR_DEFECTO = {"CONSERVADOR": "rf_usd", "MODERADO": "mix_bal", "AGRESIVO": "acc_bvc"}

ETIQUETAS = {
    "RECOMENDADO": "Recomendado para ti",
    "COMPATIBLE": "Compatible",
    "POR_ENCIMA_DEL_PERFIL": "Por encima de tu perfil",
}
ORDEN_ETIQUETA = {"RECOMENDADO": 0, "COMPATIBLE": 1, "POR_ENCIMA_DEL_PERFIL": 2, None: 3}
NOTA_RENDIMIENTO = "Rendimientos históricos simulados; no garantizan resultados futuros."


def catalogo_banco() -> dict:
    """Respuesta del endpoint SIMULADO del banco fiduciario (`GET /fiduciario/v1/fideicomisos`)."""
    hoy = date.today()
    return {
        "banco": "Banco fiduciario aliado (simulado)",
        "fecha_valor": hoy.isoformat(),
        "publicado_en": datetime.combine(hoy, time(8, 0)).isoformat(),
        "fideicomisos": [{**deepcopy(f), "valor_unidad": str(f["valor_unidad"])} for f in FIDEICOMISOS],
    }


class CatalogoCache:
    """Caché diaria del catálogo: se refresca la primera vez que se consulta cada día."""

    def __init__(self, fuente: Callable[[], dict] = catalogo_banco):
        self._fuente = fuente
        self._fecha: date | None = None
        self._datos: dict | None = None
        self._por_id: dict[str, dict] = {}
        self.consultas_al_banco = 0

    def _refrescar(self, hoy: date):
        datos = self._fuente()
        self.consultas_al_banco += 1
        por_id = {}
        for f in datos["fideicomisos"]:
            f = deepcopy(f)
            f["valor_unidad"] = Decimal(str(f["valor_unidad"]))
            por_id[f["id"]] = f
        self._datos, self._por_id, self._fecha = datos, por_id, hoy

    def obtener(self, hoy: date | None = None) -> dict[str, dict]:
        hoy = hoy or date.today()
        if self._fecha != hoy or self._datos is None:
            self._refrescar(hoy)
        return self._por_id

    @property
    def actualizado_en(self) -> str | None:
        return self._datos["publicado_en"] if self._datos else None

    def fideicomiso(self, fideicomiso_id: str) -> dict | None:
        return self.obtener().get(fideicomiso_id)

    def valor_unidad(self, fideicomiso_id: str) -> Decimal:
        return self.obtener()[fideicomiso_id]["valor_unidad"]


def etiquetar(riesgo: int, perfil: str | None) -> str | None:
    """Etiqueta de idoneidad de un fideicomiso para un perfil (None si aún no hay perfil)."""
    if perfil is None:
        return None
    maximo = RIESGO_MAXIMO_PERFIL[perfil]
    if riesgo > maximo:
        return "POR_ENCIMA_DEL_PERFIL"
    if riesgo in RIESGOS_RECOMENDADOS[perfil]:
        return "RECOMENDADO"
    return "COMPATIBLE"


def requiere_confirmacion(riesgo: int, perfil: str | None) -> bool:
    return etiquetar(riesgo, perfil) == "POR_ENCIMA_DEL_PERFIL"


def listar_para_perfil(fideicomisos: dict[str, dict], perfil: str | None,
                       riesgo_max: int | None = None,
                       adhesiones: set[str] | None = None) -> list[dict]:
    """Lista etiquetada y ordenada (Recomendado -> Compatible -> Por encima), con filtro de riesgo."""
    adhesiones = adhesiones or set()
    salida = []
    for f in fideicomisos.values():
        if riesgo_max is not None and f["riesgo"] > riesgo_max:
            continue
        etiqueta = etiquetar(f["riesgo"], perfil)
        salida.append({**deepcopy(f), "valor_unidad": str(f["valor_unidad"]),
                       "etiqueta": etiqueta,
                       "etiqueta_texto": ETIQUETAS.get(etiqueta) if etiqueta else None,
                       "requiere_confirmacion_riesgo": etiqueta == "POR_ENCIMA_DEL_PERFIL",
                       "adhesion_firmada": f["id"] in adhesiones})
    principal = FIDEICOMISO_POR_DEFECTO.get(perfil) if perfil else None

    def orden(f: dict):
        # Recomendados: primero el principal del perfil. Compatibles: del más cercano al perfil
        # al más prudente. Por encima: del menos al más riesgoso.
        e = f["etiqueta"]
        secundario = -f["riesgo"] if e == "COMPATIBLE" else f["riesgo"]
        return ORDEN_ETIQUETA[e], f["id"] != principal, secundario

    salida.sort(key=orden)
    return salida


def distribuir_centavos(monto_centavos: int, porcentajes: list[float]) -> list[int]:
    """Reparte el monto según porcentajes (que suman 100) sin perder centavos: el redondeo
    sobrante se asigna al último tramo para que la suma sea exacta."""
    montos = [int(Decimal(monto_centavos) * Decimal(str(p)) / 100) for p in porcentajes]
    if montos:
        montos[-1] += monto_centavos - sum(montos)
    return montos
