"""Genera el dataset SINTÉTICO del baseline de IA (perfil de riesgo).

    python ia/generar_dataset.py            -> data/dataset_sintetico.csv (5.000 filas)
    python ia/generar_dataset.py --n 10000  -> otro tamaño

Cómo se construye (detalle en docs/ia/DATASET.md):
  1. Se simulan las 10 respuestas del cuestionario (ficha de IA de la Sesión 1) con
     distribuciones y correlaciones SUPUESTAS por el equipo para el segmento objetivo
     (personas de 20 a 40 años, urbanas, que nunca han invertido).
  2. Se calcula el puntaje de idoneidad con la MISMA regla del prototipo (app/core/perfil.py).
  3. Se suma ruido gaussiano (desv. 0,75 puntos): representa que dos asesores no siempre
     coinciden con un cliente que está cerca del límite entre dos perfiles.
  4. Se etiqueta con los mismos cortes (<7 Conservador, <13 Moderado, resto Agresivo) y se
     aplica la regla de seguridad: sin fondo de emergencia nunca Agresivo.

No contiene datos de personas reales. Semilla fija (42): el archivo es reproducible.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from app.core.perfil import (Cuestionario, _puntos, aplicar_reglas_seguridad,  # noqa: E402
                             puntaje_a_perfil)

SEMILLA = 42
N_POR_DEFECTO = 5000
DESV_RUIDO = 0.75
RUTA_CSV = RAIZ / "data" / "dataset_sintetico.csv"

VARIABLES = ["edad", "ingreso_rango", "pct_invertible", "horizonte_anios", "objetivo",
             "reaccion_caida_20", "experiencia_previa", "fondo_emergencia", "dependientes",
             "conocimiento"]


def simular_respuestas(n: int, rng: np.random.Generator) -> pd.DataFrame:
    # Edad: 70% en el segmento principal (20-40), el resto en los extremos.
    grupo = rng.choice(3, size=n, p=[0.10, 0.70, 0.20])
    edad = np.where(grupo == 0, rng.integers(18, 20, n),
                    np.where(grupo == 1, rng.integers(20, 41, n), rng.integers(41, 66, n)))

    # Ingreso por rangos 1 (más bajo) a 5 (más alto); sube un poco con la edad.
    base_ingreso = rng.choice([1, 2, 3, 4, 5], size=n, p=[0.28, 0.32, 0.22, 0.12, 0.06])
    ingreso = np.clip(base_ingreso + (rng.random(n) < (edad - 18) / 120), 1, 5)

    # Rasgo latente "tolerancia al riesgo" (no observable, NO se guarda en el CSV).
    # Hace que las respuestas sean coherentes entre sí, como en un cuestionario real:
    # quien quiere crecer rápido suele tener horizonte largo y no vender ante una caída.
    t = rng.normal(0, 1, n)

    # % invertible: más alto con mayor ingreso y algo con la tolerancia (1% a 50%).
    pct = np.clip(np.round(rng.gamma(2.0, 3.5 + 2.0 * ingreso + 1.5 * np.clip(t, -1, 2))), 1, 50)

    # Experiencia previa y conocimiento (autoevaluado 1-5).
    experiencia = rng.random(n) < 1 / (1 + np.exp(-(-2.3 + 0.8 * t + 0.3 * ingreso)))
    conocimiento = np.clip(np.round(1.8 + 1.2 * experiencia + 0.4 * t + rng.normal(0, 0.8, n)), 1, 5)

    def ordinal(z, cortes, valores):
        return np.asarray(valores)[np.searchsorted(cortes, z)]

    # Horizonte (años): más largo con la tolerancia y en menores de 35.
    z_h = 0.7 * t + 0.3 * (edad < 35) + rng.normal(0, 0.7, n)
    horizonte = ordinal(z_h, [-1.3, -0.8, -0.2, 0.3, 0.9, 1.4], [0.5, 1, 2, 3, 5, 7, 10])

    # Objetivo y reacción ante una caída del 20%.
    objetivo = ordinal(0.9 * t + rng.normal(0, 0.6, n), [-0.45, 0.9],
                       ["proteger", "crecer", "ganar_rapido"])
    reaccion = ordinal(0.9 * t + 0.4 * experiencia + rng.normal(0, 0.6, n), [-0.4, 0.75],
                       ["vender_todo", "esperar", "comprar_mas"])

    # Fondo de emergencia: más probable con mayor ingreso.
    fondo = rng.random(n) < 0.25 + 0.12 * ingreso

    # Dependientes: más con la edad.
    dependientes = np.clip(rng.poisson(np.where(edad < 30, 0.3, 1.1)), 0, 5)

    return pd.DataFrame({
        "edad": edad.astype(int), "ingreso_rango": ingreso.astype(int),
        "pct_invertible": pct.astype(int), "horizonte_anios": horizonte,
        "objetivo": objetivo, "reaccion_caida_20": reaccion,
        "experiencia_previa": experiencia, "fondo_emergencia": fondo,
        "dependientes": dependientes.astype(int), "conocimiento": conocimiento.astype(int),
    })


def etiquetar(df: pd.DataFrame, rng: np.random.Generator, desv_ruido: float = DESV_RUIDO) -> pd.DataFrame:
    df = df.copy()
    puntajes = [round(sum(_puntos(Cuestionario(**fila)).values()), 2)
                for fila in df[VARIABLES].to_dict("records")]
    df["puntaje_reglas"] = puntajes
    df["ruido"] = np.round(rng.normal(0, desv_ruido, len(df)), 2)
    df["puntaje_con_ruido"] = (df["puntaje_reglas"] + df["ruido"]).round(2)
    perfiles = []
    for fila, puntaje in zip(df[VARIABLES].to_dict("records"), df["puntaje_con_ruido"]):
        perfil, _ = aplicar_reglas_seguridad(puntaje_a_perfil(puntaje), Cuestionario(**fila))
        perfiles.append(perfil)
    df["perfil"] = perfiles
    return df


def generar(n: int = N_POR_DEFECTO, semilla: int = SEMILLA) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    df = etiquetar(simular_respuestas(n, rng), rng)
    df.insert(0, "id", [f"syn_{i:05d}" for i in range(1, n + 1)])
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=N_POR_DEFECTO)
    ap.add_argument("--salida", type=Path, default=RUTA_CSV)
    args = ap.parse_args()
    df = generar(args.n)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.salida, index=False)
    print(f"{len(df)} usuarios sintéticos -> {args.salida}")
    print(df["perfil"].value_counts().to_string())


if __name__ == "__main__":
    main()
