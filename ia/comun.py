"""Piezas compartidas por el entrenamiento y el predictor del perfil de riesgo (Sesión 3).

Soporta las nuevas codificaciones del cuestionario situacional en 2 tandas:
  - ahorro_mensual_rango (1..4 o faltante "Prefiero no decirlo")
  - emergencia_200 (ahorros | prestado | no_podria | faltante)
  - experiencia_tipo (ninguna | ahorro_dolares | caja_ahorro | acciones)
  - tanda_completada (1 o 2; en tanda 1, dependientes y conocimiento van como faltantes prudentes)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RUTA_MODELO = RAIZ / "ia" / "modelo_perfil.joblib"
RUTA_DATASET = RAIZ / "data" / "dataset_sintetico.csv"
DIR_DOCS = RAIZ / "docs" / "ia"

CLASES = ["CONSERVADOR", "MODERADO", "AGRESIVO"]   # orden de menor a mayor riesgo
UMBRAL_REVISION = 0.60                            # probabilidad < 60% -> revisión humana

# Variables del dataset sintético S3 (conserva las 10 columnas compatibles + nuevas codificaciones S3).
VARIABLES = [
    "edad", "ingreso_rango", "pct_invertible", "horizonte_anios", "objetivo",
    "reaccion_caida_20", "experiencia_previa", "fondo_emergencia", "dependientes",
    "conocimiento", "ahorro_mensual_rango", "emergencia_200", "experiencia_tipo",
    "tanda_completada", "ahorro_omitido", "emergencia_omitida",
]

COLUMNAS_MODELO = [
    "edad", "ingreso_rango", "pct_invertible", "horizonte_anios",
    "dependientes", "conocimiento", "ahorro_mensual_rango",
    "ahorro_omitido", "emergencia_omitida", "tanda_2_pendiente",
    "emergencia_ahorros", "emergencia_prestado", "emergencia_no_podria",
    "exp_ninguna", "exp_ahorro_dolares", "exp_caja_ahorro", "exp_acciones",
    "objetivo_proteger", "objetivo_crecer", "objetivo_ganar_rapido",
    "reaccion_vender_todo", "reaccion_esperar", "reaccion_comprar_mas",
]


def preparar_x(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte respuestas del cuestionario (S2 o S3, incluso con faltantes) en matriz numérica."""
    x = pd.DataFrame(index=df.index)
    x["edad"] = pd.to_numeric(df["edad"], errors="coerce").fillna(30.0)
    x["horizonte_anios"] = pd.to_numeric(df["horizonte_anios"], errors="coerce").fillna(1.0)

    # Faltantes por "Prefiero no decirlo" o Tanda 2 pendiente -> imputación prudente + indicador
    ing = pd.to_numeric(df["ingreso_rango"], errors="coerce") if "ingreso_rango" in df else pd.Series(index=df.index, dtype=float)
    pct = pd.to_numeric(df["pct_invertible"], errors="coerce") if "pct_invertible" in df else pd.Series(index=df.index, dtype=float)
    aho = pd.to_numeric(df["ahorro_mensual_rango"], errors="coerce") if "ahorro_mensual_rango" in df else ing.clip(1, 4)

    ahorro_omit = df["ahorro_omitido"].astype(bool) if "ahorro_omitido" in df else aho.isna()
    x["ahorro_omitido"] = ahorro_omit.astype(float)
    x["ingreso_rango"] = ing.fillna(1.0)
    x["pct_invertible"] = pct.fillna(5.0)
    x["ahorro_mensual_rango"] = aho.fillna(1.0)

    dep = pd.to_numeric(df["dependientes"], errors="coerce") if "dependientes" in df else pd.Series(index=df.index, dtype=float)
    con = pd.to_numeric(df["conocimiento"], errors="coerce") if "conocimiento" in df else pd.Series(index=df.index, dtype=float)
    tanda_pend = (dep.isna() | con.isna())
    if "tanda_completada" in df:
        tanda_pend = tanda_pend | (pd.to_numeric(df["tanda_completada"], errors="coerce").fillna(2) < 2)
    x["tanda_2_pendiente"] = tanda_pend.astype(float)
    x["dependientes"] = dep.fillna(1.0)     # prudente: no otorga punto extra de "sin dependientes"
    x["conocimiento"] = con.fillna(1.0)     # prudente: nivel inicial

    if "emergencia_200" in df:
        em = df["emergencia_200"].astype(object)
    else:
        em = df["fondo_emergencia"].map({True: "ahorros", False: "no_podria"})
    em_omit = df["emergencia_omitida"].astype(bool) if "emergencia_omitida" in df else em.isna()
    x["emergencia_omitida"] = em_omit.astype(float)
    for v in ["ahorros", "prestado", "no_podria"]:
        x[f"emergencia_{v}"] = (em == v).astype(float)

    if "experiencia_tipo" in df:
        exp = df["experiencia_tipo"].astype(object)
    else:
        exp = df["experiencia_previa"].map({True: "acciones", False: "ninguna"})
    for v in ["ninguna", "ahorro_dolares", "caja_ahorro", "acciones"]:
        x[f"exp_{v}"] = (exp == v).astype(float)

    for v in ["proteger", "crecer", "ganar_rapido"]:
        x[f"objetivo_{v}"] = (df["objetivo"] == v).astype(float)
    for v in ["vender_todo", "esperar", "comprar_mas"]:
        x[f"reaccion_{v}"] = (df["reaccion_caida_20"] == v).astype(float)
    return x[COLUMNAS_MODELO]
