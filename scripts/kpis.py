"""Prueba de carga SIMULADA y tablero de KPIs transaccionales.

Corre N aportes contra la pasarela simulada (con sus tasas de rechazo, timeout y fallas)
y calcula los 4 KPIs que pide la Sesión 2:
  - tasa de aprobación (autorizaciones aprobadas por el emisor / intentos)
  - latencia p95 (de punta a punta: pasarela simulada + procesamiento real del backend)
  - TPS (con W "workers" concurrentes sobre un reloj simulado)
  - tasa de reversos (reversos iniciados / intentos)

Uso:  python scripts/kpis.py --n 1000 --workers 20
Salidas: docs/kpis.json y docs/kpis_tablero.png
IMPORTANTE: las latencias de la red bancaria son SIMULADAS; indicarlo en las láminas.
"""
import argparse
import heapq
import json
import statistics
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from app.core.perfil import Cuestionario  # noqa: E402
from app.core.servicio import InvierteYa  # noqa: E402


def percentil(valores, p):
    ordenados = sorted(valores)
    k = (len(ordenados) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(ordenados) - 1)
    return ordenados[f] + (ordenados[c] - ordenados[f]) * (k - f)


def correr(n: int, workers: int, semilla: int) -> dict:
    from app.core.pasarela_simulada import ConfigPasarela
    import random
    s = InvierteYa(ConfigPasarela(semilla=semilla))
    rng = random.Random(semilla)
    usuarios = []
    for i in range(50):  # 50 usuarios sintéticos con perfiles variados
        u = s.registrar(f"Usuario sintético {i}", f"u{i}@example.com")
        s.aprobar_kyc(u.id)
        s.evaluar_perfil(u.id, Cuestionario(
            edad=rng.randint(20, 40), ingreso_rango=rng.randint(1, 5), pct_invertible=rng.choice([5, 15, 30]),
            horizonte_anios=rng.choice([0.5, 2, 4, 8]), objetivo=rng.choice(["proteger", "crecer", "ganar_rapido"]),
            reaccion_caida_20=rng.choice(["vender_todo", "esperar", "comprar_mas"]),
            experiencia_previa=rng.random() < 0.3, fondo_emergencia=rng.random() < 0.5,
            dependientes=rng.choice([0, 0, 1, 2]), conocimiento=rng.randint(1, 5)))
        s.firmar_adhesion(u.id, True)
        usuarios.append((u, s.pasarela.tokenizar("4111111111111111")))

    aportes = []
    for i in range(n):
        u, tok = rng.choice(usuarios)
        monto = rng.choice([500, 1000, 2000, 3000, 5000, 10000])
        aportes.append(s.crear_aporte(u.id, monto, tok, f"carga-{i}"))

    # Reloj simulado: W workers atienden la cola; TPS = N / tiempo total
    libres = [0.0] * workers
    heapq.heapify(libres)
    fin_max = 0.0
    for a in aportes:
        inicio = heapq.heappop(libres)
        fin = inicio + a["latencia_total_ms"]
        fin_max = max(fin_max, fin)
        heapq.heappush(libres, fin)

    lat = [a["latencia_total_ms"] for a in aportes]
    def con(evento):
        return sum(1 for a in aportes if any(e["estado"] == evento for e in a["eventos"]))
    autorizados = con("AUTORIZADO")
    reversos = con("EN_REVERSO")
    finales = {}
    for a in aportes:
        finales[a["estado"]] = finales.get(a["estado"], 0) + 1
    cierre = s.cerrar_dia(date.today())

    return {
        "simulacion": {"transacciones": n, "workers": workers, "semilla": semilla,
                       "nota": "Latencias de pasarela/red SIMULADAS (lognormal, media 350 ms; timeout 30 s)"},
        "kpis": {
            "tasa_aprobacion_pct": round(100 * autorizados / n, 2),
            "latencia_p50_ms": round(percentil(lat, 50), 1),
            "latencia_p95_ms": round(percentil(lat, 95), 1),
            "latencia_p99_ms": round(percentil(lat, 99), 1),
            "tps": round(n / (fin_max / 1000), 1),
            "tasa_reversos_pct": round(100 * reversos / n, 2),
        },
        "estados_finales": dict(sorted(finales.items(), key=lambda kv: -kv[1])),
        "latencias_ms": lat,
        "conciliacion": {"conciliado": cierre["conciliado"], "excepciones": len(cierre["excepciones"]),
                         "tipos": sorted({e["tipo"] for e in cierre["excepciones"]})},
        "latencia_media_ms": round(statistics.mean(lat), 1),
    }


def _es(x, dec=0):
    """Formato numérico en español: punto para miles, coma para decimales."""
    t = f"{x:,.{dec}f}"
    return t.replace(",", "X").replace(".", ",").replace("X", ".")


def tablero(res: dict, salida: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    SUP, TXT, TXT2, GRID, AZUL = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0", "#2a78d6"
    k = res["kpis"]
    fig = plt.figure(figsize=(13, 7.2), facecolor=SUP)
    fig.suptitle("InvierteYa · KPIs transaccionales del prototipo", x=0.04, ha="left",
                 fontsize=17, fontweight="bold", color=TXT, y=0.97)
    fig.text(0.04, 0.905, f"{_es(res['simulacion']['transacciones'])} aportes simulados · "
             f"{res['simulacion']['workers']} workers · pasarela, red bancaria y latencias SIMULADAS",
             fontsize=10.5, color=TXT2)

    tiles = [("Tasa de aprobación", f"{_es(k['tasa_aprobacion_pct'], 1)}%", "autorizaciones aprobadas por el emisor"),
             ("Latencia p95", f"{_es(k['latencia_p95_ms'])} ms", f"p50 {_es(k['latencia_p50_ms'])} ms"),
             ("TPS", f"{_es(k['tps'], 1)}", "transacciones por segundo"),
             ("Tasa de reversos", f"{_es(k['tasa_reversos_pct'], 1)}%", "timeouts y fallas de captura")]
    for i, (titulo, valor, sub) in enumerate(tiles):
        x = 0.04 + i * 0.235
        ax = fig.add_axes([x, 0.64, 0.215, 0.22])
        ax.set_facecolor("white")
        for sp in ax.spines.values():
            sp.set_color(GRID)
        ax.set_xticks([]); ax.set_yticks([])
        ax.text(0.07, 0.78, titulo, fontsize=11, color=TXT2, transform=ax.transAxes)
        ax.text(0.07, 0.36, valor, fontsize=26, fontweight="bold", color=TXT, transform=ax.transAxes)
        ax.text(0.07, 0.12, sub, fontsize=9, color=TXT2, transform=ax.transAxes)

    # Distribución de latencias (sin los timeouts de 30 s, que se reportan aparte)
    lat = [v for v in res["latencias_ms"] if v < 30_000]
    timeouts = len(res["latencias_ms"]) - len(lat)
    ax1 = fig.add_axes([0.06, 0.11, 0.52, 0.42])
    ax1.hist(lat, bins=40, color=AZUL, edgecolor=SUP, linewidth=1.5)
    ax1.axvline(k["latencia_p95_ms"], color=TXT, linewidth=1.5, linestyle="--")
    ax1.text(k["latencia_p95_ms"], ax1.get_ylim()[1] * 0.92, f"  p95 = {_es(k['latencia_p95_ms'])} ms",
             color=TXT, fontsize=10)
    ax1.set_title(f"Latencia de punta a punta (ms) · {timeouts} timeouts de 30 s excluidos del gráfico",
                  loc="left", fontsize=11, color=TXT)
    ax1.set_ylabel("aportes", color=TXT2)

    # Estados finales de los aportes
    estados = res["estados_finales"]
    nombres = {"ASIGNADO": "Asignado", "RECHAZADO": "Rechazado", "REVERSADO": "Reversado",
               "REVERSO_PENDIENTE": "Reverso pendiente"}
    etiquetas = [nombres.get(e, e) for e in estados]
    ax2 = fig.add_axes([0.68, 0.11, 0.28, 0.42])
    barras = ax2.barh(etiquetas[::-1], list(estados.values())[::-1], color=AZUL, height=0.55)
    for b in barras:
        ax2.text(b.get_width(), b.get_y() + b.get_height() / 2, f"  {int(b.get_width())}",
                 va="center", fontsize=10, color=TXT)
    ax2.set_title("Estado final de los aportes", loc="left", fontsize=11, color=TXT)
    ax2.set_xlim(0, max(estados.values()) * 1.18)

    for ax in (ax1, ax2):
        ax.set_facecolor(SUP)
        ax.grid(axis="x" if ax is ax2 else "y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for lado in ("top", "right"):
            ax.spines[lado].set_visible(False)
        for lado in ("left", "bottom"):
            ax.spines[lado].set_color(GRID)
        ax.tick_params(colors=TXT2, labelsize=9.5)

    c = res["conciliacion"]
    fig.text(0.04, 0.015, f"Conciliación del día: {'cuadra' if c['conciliado'] else 'con excepciones'}"
             f" ({c['excepciones']} excepciones: {', '.join(c['tipos']) or 'ninguna'})",
             fontsize=9.5, color=TXT2)
    fig.savefig(salida, dpi=160, facecolor=SUP)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--semilla", type=int, default=7)
    args = ap.parse_args()
    res = correr(args.n, args.workers, args.semilla)
    docs = RAIZ / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "kpis.json").write_text(json.dumps({k: v for k, v in res.items() if k != "latencias_ms"},
                                               indent=2, ensure_ascii=False), encoding="utf-8")
    tablero(res, docs / "kpis_tablero.png")
    print(json.dumps(res["kpis"], indent=2, ensure_ascii=False))
    print("Estados finales:", res["estados_finales"])
    print("Conciliación:", res["conciliacion"])
