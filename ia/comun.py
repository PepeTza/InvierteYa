"""Piezas compartidas por el entrenamiento y el predictor (misma preparación de datos)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RUTA_MODELO = RAIZ / "ia" / "modelo_perfil.joblib"
RUTA_DATASET = RAIZ / "data" / "dataset_sintetico.csv"
DIR_DOCS = RAIZ / "docs" / "ia"

CLASES = ["CONSERVADOR", "MODERADO", "AGRESIVO"]   # orden de menor a mayor riesgo
UMBRAL_REVISION = 0.60                            # probabilidad < 60% -> revisión humana

# Las 10 variables del cuestionario (ficha de IA de la Sesión 1).
VARIABLES = ["edad", "ingreso_rango", "pct_invertible", "horizonte_anios", "objetivo",
             "reaccion_caida_20", "experiencia_previa", "fondo_emergencia", "dependientes",
             "conocimiento"]

# Columnas que ve el modelo. Las categóricas van en one-hot; el modelo NO recibe el
# puntaje de reglas, solo las respuestas (si no, la tarea sería trivial).
COLUMNAS_MODELO = [
    "edad", "ingreso_rango", "pct_invertible", "horizonte_anios", "experiencia_previa",
    "fondo_emergencia", "dependientes", "conocimiento",
    "objetivo_proteger", "objetivo_crecer", "objetivo_ganar_rapido",
    "reaccion_vender_todo", "reaccion_esperar", "reaccion_comprar_mas",
]


def preparar_x(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte respuestas del cuestionario en la matriz numérica del modelo."""
    x = pd.DataFrame(index=df.index)
    for c in ["edad", "ingreso_rango", "pct_invertible", "horizonte_anios", "dependientes",
              "conocimiento"]:
        x[c] = df[c].astype(float)
    for c in ["experiencia_previa", "fondo_emergencia"]:
        x[c] = df[c].astype(bool).astype(int)
    for v in ["proteger", "crecer", "ganar_rapido"]:
        x[f"objetivo_{v}"] = (df["objetivo"] == v).astype(int)
    for v in ["vender_todo", "esperar", "comprar_mas"]:
        x[f"reaccion_{v}"] = (df["reaccion_caida_20"] == v).astype(int)
    return x[COLUMNAS_MODELO]
