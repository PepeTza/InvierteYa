"""Pronóstico simple de flujos diarios por fideicomiso para el banco fiduciario (Sesión 3).

    python ia/pronostico_flujos.py

Compara dos enfoques simples sobre la serie diaria sintética de aportes netos (365 días × 5 fideicomisos):
  1. Media móvil de 7 días (baseline ingenuo).
  2. Regresión lineal regularizada (Ridge) con rezagos (1d, 7d, media 7d) y estacionalidad
     de calendario (día de semana y quincena).

Evaluación estrictamente temporal: primeros 305 días entrenamiento, últimos 60 días prueba.
Métricas: MAE (USD) y MAPE (%). Genera docs/ia/metricas_flujos.json y docs/ia/pronostico_flujos.png.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

RUTA_FLUJOS = RAIZ / "data" / "dataset_flujos_diarios.csv"
DIR_DOCS = RAIZ / "docs" / "ia"
RUTA_METRICAS_FLUJOS = DIR_DOCS / "metricas_flujos.json"
DIAS_PRUEBA = 60

COLUMNAS_REG = ["lag_1", "lag_7", "ma_7", "es_quincena", "es_fin_semana", "dia_idx"]


def cargar_flujos() -> pd.DataFrame:
    if not RUTA_FLUJOS.exists():
        from ia.generar_dataset_comportamiento import generar_flujos_diarios
        RUTA_FLUJOS.parent.mkdir(parents=True, exist_ok=True)
        generar_flujos_diarios().to_csv(RUTA_FLUJOS, index=False)
    return pd.read_csv(RUTA_FLUJOS)


def _mape(y_real: np.ndarray, y_pred: np.ndarray) -> float:
    mask = np.abs(y_real) > 1.0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((y_real[mask] - y_pred[mask]) / y_real[mask])) * 100.0)


def _preparar_serie(sub: pd.DataFrame) -> pd.DataFrame:
    s = sub.sort_values("dia_idx").copy()
    s["lag_1"] = s["flujo_neto_usd"].shift(1)
    s["lag_7"] = s["flujo_neto_usd"].shift(7)
    s["ma_7"] = s["flujo_neto_usd"].shift(1).rolling(7).mean()
    s["es_fin_semana"] = (s["dia_semana"] >= 5).astype(int)
    return s.dropna().reset_index(drop=True)


def _pronosticar_7_dias(modelo: Ridge, sub: pd.DataFrame) -> tuple[float, float]:
    """Pronostica los próximos 7 días de forma iterativa para un fideicomiso."""
    hist = sub.sort_values("dia_idx").copy()
    valores = hist["flujo_neto_usd"].tolist()
    ultima_fecha = pd.to_datetime(hist["fecha"].iloc[-1])
    ultimo_idx = int(hist["dia_idx"].iloc[-1])

    preds = []
    for paso in range(1, 8):
        fecha_f = ultima_fecha + pd.Timedelta(days=paso)
        es_quincena = int(fecha_f.day in (14, 15, 16, 29, 30, 31, 1))
        es_fds = int(fecha_f.weekday() >= 5)
        fila = pd.DataFrame([{
            "lag_1": valores[-1],
            "lag_7": valores[-7],
            "ma_7": float(np.mean(valores[-7:])),
            "es_quincena": es_quincena,
            "es_fin_semana": es_fds,
            "dia_idx": ultimo_idx + paso,
        }])
        pred = max(0.0, float(modelo.predict(fila[COLUMNAS_REG])[0]))
        preds.append(pred)
        valores.append(pred)
    return round(preds[0], 2), round(float(sum(preds)), 2)


def _grafico_flujos(fechas: list[str], real: np.ndarray, pred_ma: np.ndarray,
                    pred_reg: np.ndarray, ruta: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10.5, "axes.edgecolor": "#d8d7d2",
        "axes.labelcolor": "#52514e", "xtick.color": "#52514e", "ytick.color": "#52514e",
        "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    })
    fig, ax = plt.subplots(figsize=(8.2, 4.4), dpi=200)
    x = np.arange(len(fechas))
    ax.plot(x, real, label="Flujo neto real (sintético)", color="#0b0b0b", linewidth=2.0)
    ax.plot(x, pred_ma, label="Media móvil 7d", color="#9c9a94", linestyle="--", linewidth=1.6)
    ax.plot(x, pred_reg, label="Regresión con rezagos y quincena", color="#0f7a55", linewidth=2.0)
    paso = max(1, len(fechas) // 6)
    ax.set_xticks(x[::paso], [fechas[i][5:] for i in range(0, len(fechas), paso)])
    ax.set_ylabel("Flujo neto diario total (USD)")
    ax.set_xlabel("Últimos 60 días de prueba (MM-DD)")
    ax.set_title("Pronóstico diario de flujos netos · Total 5 fideicomisos",
                 color="#0b0b0b", fontsize=12, loc="left", pad=10)
    ax.grid(True, color="#ecebe7", linewidth=0.8)
    ax.legend(loc="upper left", frameon=True, facecolor="#fcfcfb", edgecolor="#d8d7d2")
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    fig.savefig(ruta, facecolor="#fcfcfb")
    plt.close(fig)


def evaluar_y_pronosticar(df: pd.DataFrame | None = None, guardar: bool = True) -> dict:
    df = cargar_flujos() if df is None else df
    por_fid = []

    real_total = np.zeros(DIAS_PRUEBA)
    ma_total = np.zeros(DIAS_PRUEBA)
    reg_total = np.zeros(DIAS_PRUEBA)
    fechas_pru: list[str] = []

    for fid, sub in df.groupby("fideicomiso_id", sort=False):
        nombre = str(sub["nombre_fideicomiso"].iloc[0])
        s = _preparar_serie(sub)
        ent = s.iloc[:-DIAS_PRUEBA]
        pru = s.iloc[-DIAS_PRUEBA:]

        y_real = pru["flujo_neto_usd"].to_numpy()
        pred_ma = pru["ma_7"].to_numpy()

        reg = Ridge(alpha=1.0)
        reg.fit(ent[COLUMNAS_REG], ent["flujo_neto_usd"].to_numpy())
        pred_reg = reg.predict(pru[COLUMNAS_REG])

        mae_ma, mape_ma = mean_absolute_error(y_real, pred_ma), _mape(y_real, pred_ma)
        mae_reg, mape_reg = mean_absolute_error(y_real, pred_reg), _mape(y_real, pred_reg)

        # Reentrenar con toda la serie para proyectar mañana y próxima semana
        reg_full = Ridge(alpha=1.0)
        reg_full.fit(s[COLUMNAS_REG], s["flujo_neto_usd"].to_numpy())
        manana_usd, semana_usd = _pronosticar_7_dias(reg_full, sub)

        real_total += y_real
        ma_total += pred_ma
        reg_total += pred_reg
        if not fechas_pru:
            fechas_pru = pru["fecha"].tolist()

        por_fid.append({
            "fideicomiso_id": fid,
            "nombre": nombre,
            "flujo_neto_manana_usd": manana_usd,
            "flujo_neto_7d_usd": semana_usd,
            "media_movil_7d": {"mae_usd": round(float(mae_ma), 2), "mape_pct": round(mape_ma, 2)},
            "regresion_lineal": {"mae_usd": round(float(mae_reg), 2), "mape_pct": round(mape_reg, 2)},
            "mae_usd": round(float(mae_reg), 2),
            "mape_pct": round(mape_reg, 2),
        })

    resumen_global = {
        "media_movil_7d": {
            "mae_usd": round(float(mean_absolute_error(real_total, ma_total)), 2),
            "mape_pct": round(_mape(real_total, ma_total), 2),
        },
        "regresion_lineal_rezagos": {
            "mae_usd": round(float(mean_absolute_error(real_total, reg_total)), 2),
            "mape_pct": round(_mape(real_total, reg_total), 2),
        },
    }
    ganador = ("regresion_lineal_rezagos"
               if resumen_global["regresion_lineal_rezagos"]["mape_pct"] <= resumen_global["media_movil_7d"]["mape_pct"]
               else "media_movil_7d")

    resultado = {
        "fecha_generacion": datetime.now().isoformat(timespec="seconds"),
        "fecha_corte": str(df["fecha"].max()),
        "dias_entrenamiento": int(df["dia_idx"].nunique() - DIAS_PRUEBA),
        "dias_prueba": DIAS_PRUEBA,
        "modelo_elegido": ganador,
        "comparacion_total": resumen_global,
        "por_fideicomiso": por_fid,
        "total_manana_usd": round(sum(f["flujo_neto_manana_usd"] for f in por_fid), 2),
        "total_7d_usd": round(sum(f["flujo_neto_7d_usd"] for f in por_fid), 2),
        "nota": "Pronóstico basado en serie diaria sintética para planificación de lotes del fiduciario.",
    }

    if guardar:
        DIR_DOCS.mkdir(parents=True, exist_ok=True)
        RUTA_METRICAS_FLUJOS.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
        _grafico_flujos(fechas_pru, real_total, ma_total, reg_total, DIR_DOCS / "pronostico_flujos.png")

    return resultado


def obtener_pronostico_fiduciario() -> dict:
    """Devuelve el pronóstico listo para GET /v1/fiduciario/pronostico-flujos."""
    if RUTA_METRICAS_FLUJOS.exists():
        return json.loads(RUTA_METRICAS_FLUJOS.read_text(encoding="utf-8"))
    return evaluar_y_pronosticar(guardar=False)


def main():
    r = evaluar_y_pronosticar()
    print(f"Pronóstico de flujos · modelo elegido: {r['modelo_elegido']}")
    for m, vals in r["comparacion_total"].items():
        print(f"  {m:26s} MAE=${vals['mae_usd']:7.2f}  MAPE={vals['mape_pct']:.2f}%")
    print(f"\nProyección total: mañana=${r['total_manana_usd']:,.2f} · 7 días=${r['total_7d_usd']:,.2f}")
    print("Archivos: docs/ia/metricas_flujos.json, docs/ia/pronostico_flujos.png")


if __name__ == "__main__":
    main()
