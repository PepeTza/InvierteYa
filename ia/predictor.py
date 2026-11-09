"""Predictor del perfil de riesgo con el modelo baseline (lo usa la API).

Orden de decisión (ficha de IA, Sesión 1):
  1. El modelo estima la probabilidad de cada perfil a partir de las 10 respuestas.
  2. Reglas de seguridad que el modelo NUNCA puede saltarse (app/core/perfil.py):
     sin fondo de emergencia nunca Agresivo.
  3. Supervisión humana: si la probabilidad del perfil es < 60%, el caso va a revisión de un
     asesor (lo decide el servicio; aquí solo se marca).

Si el modelo no existe o no se puede cargar (p. ej., otra versión de scikit-learn), devuelve
None y el servicio usa las reglas: la demo nunca se cae por el modelo.
"""
from __future__ import annotations

import logging
import warnings
from dataclasses import asdict

import pandas as pd

from app.core.perfil import Cuestionario, aplicar_reglas_seguridad
from ia.comun import CLASES, RUTA_MODELO, UMBRAL_REVISION, preparar_x

log = logging.getLogger("invierteya.ia")
NOMBRES = {"regresion_logistica": "regresión logística", "arbol_decision": "árbol de decisión"}
_cache: dict | None = None
_cargado = False


def cargar(forzar: bool = False) -> dict | None:
    global _cache, _cargado
    if _cargado and not forzar:
        return _cache
    _cargado = True
    try:
        import joblib
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _cache = joblib.load(RUTA_MODELO)
    except Exception as e:  # archivo ausente, scikit-learn no instalado o versión incompatible
        log.warning("Modelo de perfil no disponible (%s); se usarán las reglas.", e)
        _cache = None
    return _cache


def predecir(c: Cuestionario) -> dict | None:
    paquete = cargar()
    if paquete is None:
        return None
    modelo = paquete["modelo"]
    x = preparar_x(pd.DataFrame([asdict(c)]))
    fila = modelo.predict_proba(x)[0]
    proba = {clase: float(fila[list(modelo.classes_).index(clase)]) for clase in CLASES}
    perfil_modelo = max(proba, key=proba.get)
    perfil, avisos = aplicar_reglas_seguridad(perfil_modelo, c)
    probabilidad = proba[perfil_modelo]
    return {
        "perfil": perfil,
        "perfil_modelo": perfil_modelo,
        "probabilidad": round(probabilidad, 4),
        "probabilidades": {k: round(v, 4) for k, v in proba.items()},
        "revision_humana": probabilidad < UMBRAL_REVISION,
        "avisos": avisos,
        "motor": f"modelo baseline: {NOMBRES.get(paquete['nombre'], paquete['nombre'])} "
                 "(entrenado con datos sintéticos)",
    }
