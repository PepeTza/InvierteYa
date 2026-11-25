"""Genera el dataset SINTÉTICO del modelo de perfil de riesgo (actualizado Sesión 3).

    python ia/generar_dataset.py            -> data/dataset_sintetico.csv (5.000 filas)
    python ia/generar_dataset.py --n 10000  -> otro tamaño

Cambios de la Sesión 3 (respuesta al comentario #4 sobre confianza):
  - Incorpora las codificaciones del cuestionario conversacional en 2 tandas:
      * ahorro_mensual_rango: 1 ($5-$20), 2 ($20-$50), 3 ($50-$100), 4 (>$100) o faltante ("Prefiero no decirlo")
      * emergencia_200: ahorros | prestado | no_podria | faltante ("Prefiero no decirlo")
      * experiencia_tipo: ninguna | ahorro_dolares | caja_ahorro | acciones
      * tanda_completada: ~22% de usuarios solo completan la Tanda 1 antes de invertir
  - Mantiene la regla dura: sin fondo de emergencia ("no_podria" o faltante) nunca Agresivo.

No contiene datos de personas reales. Semilla fija (42): 100% reproducible.
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
from ia.comun import VARIABLES  # noqa: E402

SEMILLA = 42
N_POR_DEFECTO = 5000
DESV_RUIDO = 0.70
RUTA_CSV = RAIZ / "data" / "dataset_sintetico.csv"


def simular_respuestas(n: int, rng: np.random.Generator) -> pd.DataFrame:
    # Edad (viene del KYC): 70% en el segmento principal (20-40).
    grupo = rng.choice(3, size=n, p=[0.10, 0.70, 0.20])
    edad = np.where(grupo == 0, rng.integers(18, 20, n),
                    np.where(grupo == 1, rng.integers(20, 41, n), rng.integers(41, 66, n)))

    # Rasgo latente "tolerancia al riesgo" (no se guarda en el CSV).
    t = rng.normal(0, 1, n)

    # Rango de ahorro mensual (1..4) y su equivalencia en ingreso_rango / pct_invertible
    base_ahorro = rng.choice([1, 2, 3, 4], size=n, p=[0.30, 0.34, 0.23, 0.13])
    ahorro_num = np.clip(base_ahorro + (rng.random(n) < (edad - 18) / 140).astype(int), 1, 4)

    ingreso_mapa = np.array([0, 1, 2, 3, 5])
    ingreso_num = ingreso_mapa[ahorro_num]
    pct_num = np.clip(np.round(rng.gamma(2.0, 3.2 + 2.6 * ahorro_num + 1.4 * np.clip(t, -1, 2))), 2, 48)

    # ~11% elige "Prefiero no decirlo" en la pregunta de ahorro mensual
    ahorro_omitido = rng.random(n) < 0.11

    def ordinal(z, cortes, valores):
        return np.asarray(valores)[np.searchsorted(cortes, z)]

    # Experiencia en productos concretos
    z_exp = -1.1 + 0.85 * t + 0.35 * ahorro_num + rng.normal(0, 0.65, n)
    experiencia_tipo = ordinal(z_exp, [0.1, 0.8, 1.45],
                               ["ninguna", "ahorro_dolares", "caja_ahorro", "acciones"])
    experiencia_previa = experiencia_tipo != "ninguna"

    # Horizonte (años) derivado de "¿Para qué es este dinero?"
    z_h = 0.75 * t + 0.3 * (edad < 35) + rng.normal(0, 0.65, n)
    horizonte = ordinal(z_h, [-1.1, -0.1, 0.85], [0.5, 2.0, 4.0, 7.0])

    # Objetivo y reacción ante caída de $100 a $80
    objetivo = ordinal(0.95 * t + rng.normal(0, 0.55, n), [-0.45, 0.85],
                       ["proteger", "crecer", "ganar_rapido"])
    reaccion = ordinal(0.95 * t + 0.35 * experiencia_previa + rng.normal(0, 0.55, n), [-0.40, 0.72],
                       ["vender_todo", "esperar", "comprar_mas"])

    # Situación de gasto imprevisto de $200 (~6% elige "Prefiero no decirlo")
    z_em = -0.3 + 0.55 * ahorro_num + 0.25 * t + rng.normal(0, 0.7, n)
    emergencia_200 = ordinal(z_em, [0.55, 1.20], ["no_podria", "prestado", "ahorros"]).astype(object)
    emergencia_omitida = rng.random(n) < 0.06
    emergencia_200[emergencia_omitida] = None
    fondo_emergencia = (emergencia_200 == "ahorros")

    # Tanda 2 ("Afinemos tu perfil"): ~78% completa Tanda 2; ~22% opera inicialmente con solo Tanda 1
    completa_t2 = rng.random(n) >= 0.22
    tanda_completada = np.where(completa_t2, 2, 1)

    dependientes_raw = np.clip(rng.poisson(np.where(edad < 30, 0.3, 1.1)), 0, 5).astype(float)
    conocimiento_raw = np.clip(np.round(1.7 + 1.3 * experiencia_previa + 0.45 * t + rng.normal(0, 0.75, n)), 1, 5).astype(float)

    dependientes = np.where(completa_t2, dependientes_raw, np.nan)
    conocimiento = np.where(completa_t2, conocimiento_raw, np.nan)

    ahorro_col = np.where(ahorro_omitido, np.nan, ahorro_num.astype(float))
    ingreso_col = np.where(ahorro_omitido, np.nan, ingreso_num.astype(float))
    pct_col = np.where(ahorro_omitido, np.nan, pct_num.astype(float))

    return pd.DataFrame({
        "edad": edad.astype(int),
        "ingreso_rango": ingreso_col,
        "pct_invertible": pct_col,
        "horizonte_anios": horizonte,
        "objetivo": objetivo,
        "reaccion_caida_20": reaccion,
        "experiencia_previa": experiencia_previa,
        "fondo_emergencia": fondo_emergencia,
        "dependientes": dependientes,
        "conocimiento": conocimiento,
        "ahorro_mensual_rango": ahorro_col,
        "emergencia_200": emergencia_200,
        "experiencia_tipo": experiencia_tipo,
        "tanda_completada": tanda_completada.astype(int),
        "ahorro_omitido": ahorro_omitido,
        "emergencia_omitida": emergencia_omitida,
    })


def _fila_a_cuestionario(fila: dict) -> Cuestionario:
    def _opt_int(v):
        return None if pd.isna(v) else int(v)

    def _opt_float(v):
        return None if pd.isna(v) else float(v)

    em = None if pd.isna(fila["emergencia_200"]) else str(fila["emergencia_200"])
    return Cuestionario(
        edad=int(fila["edad"]),
        ingreso_rango=_opt_int(fila["ingreso_rango"]),
        pct_invertible=_opt_float(fila["pct_invertible"]),
        horizonte_anios=float(fila["horizonte_anios"]),
        objetivo=str(fila["objetivo"]),
        reaccion_caida_20=str(fila["reaccion_caida_20"]),
        experiencia_previa=bool(fila["experiencia_previa"]),
        fondo_emergencia=bool(fila["fondo_emergencia"]),
        dependientes=_opt_int(fila["dependientes"]),
        conocimiento=_opt_int(fila["conocimiento"]),
        ahorro_mensual_rango=_opt_int(fila["ahorro_mensual_rango"]),
        emergencia_200=em,
        experiencia_tipo=str(fila["experiencia_tipo"]),
        tanda_completada=int(fila["tanda_completada"]),
        ahorro_omitido=bool(fila["ahorro_omitido"]),
        emergencia_omitida=bool(fila["emergencia_omitida"]),
    )


def etiquetar(df: pd.DataFrame, rng: np.random.Generator, desv_ruido: float = DESV_RUIDO) -> pd.DataFrame:
    df = df.copy()
    cuestionarios = [_fila_a_cuestionario(fila) for fila in df[VARIABLES].to_dict("records")]
    puntajes = [round(sum(_puntos(c).values()), 2) for c in cuestionarios]
    df["puntaje_reglas"] = puntajes
    df["ruido"] = np.round(rng.normal(0, desv_ruido, len(df)), 2)
    df["puntaje_con_ruido"] = (df["puntaje_reglas"] + df["ruido"]).round(2)
    perfiles = []
    for c, puntaje in zip(cuestionarios, df["puntaje_con_ruido"]):
        perfil, _ = aplicar_reglas_seguridad(puntaje_a_perfil(puntaje), c)
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
    print(f"{len(df)} usuarios sintéticos (cuestionario S3) -> {args.salida}")
    print(df["perfil"].value_counts().to_string())
    print(f"Prefiero no decir (ahorro): {df['ahorro_omitido'].mean():.1%} · "
          f"(emergencia): {df['emergencia_omitida'].mean():.1%} · "
          f"solo Tanda 1: {(df['tanda_completada'] == 1).mean():.1%}")


if __name__ == "__main__":
    main()
