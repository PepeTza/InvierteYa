"""Predictor de riesgo de abandono del ahorro (lo consume GET /v1/usuarios/{id}/riesgo-abandono).

Límites éticos y operativos (Model Card Sesión 3):
  - Este modelo NUNCA mueve dinero, NUNCA cambia el perfil ni cobra comisiones extra.
  - Solo genera un aviso suave para ayudar al usuario a mantener su hábito de ahorro.
  - Si el archivo del modelo no está disponible, utiliza un respaldo transparente por reglas
    para que la demo nunca falle.
"""
from __future__ import annotations

import logging
import warnings

import pandas as pd

from ia.entrenar_abandono import RUTA_MODELO_ABANDONO, preparar_x_abandono

log = logging.getLogger("invierteya.ia.abandono")
NOMBRES = {"regresion_logistica": "regresión logística", "gradient_boosting": "gradient boosting"}
AVISO_ETICO = ("Este aviso solo busca ayudarte a mantener tu meta; "
               "nunca genera cobros ni restricciones.")

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
            _cache = joblib.load(RUTA_MODELO_ABANDONO)
    except Exception as e:
        log.warning("Modelo de abandono no disponible (%s); se usará el respaldo por reglas.", e)
        _cache = None
    return _cache


def _factores_explicativos(datos: dict) -> list[str]:
    factores = []
    dias = int(datos.get("dias_desde_ultimo_aporte", 0))
    if dias >= 30:
        factores.append(f"Llevas {dias} días sin realizar un aporte")
    pct_rech = float(datos.get("pct_pagos_rechazados", 0.0))
    if pct_rech >= 0.15:
        factores.append(f"Tienes {round(pct_rech * 100)}% de intentos de pago rechazados recientemente")
    if float(datos.get("sesiones_por_mes", 0.0)) < 1.5:
        factores.append("Tu actividad reciente en la app bajó respecto a meses anteriores")
    if int(datos.get("aportes_90d", 0)) == 0:
        factores.append("No registras aportes en los últimos 90 días")
    if bool(datos.get("tuvo_caida_unidad", False)):
        factores.append("Hubo una baja temporal en el valor de la unidad")
    if not factores:
        factores.append("Tu frecuencia de ahorro se mantiene constante")
    return factores[:3]


def _sugerencia_suave(en_riesgo: bool, datos: dict) -> str | None:
    if not en_riesgo:
        return None
    monto = float(datos.get("monto_promedio") or 20.0)
    sugerido = max(5, min(50, int(round(monto / 2.0 / 5.0) * 5) or 10))
    if float(datos.get("pct_pagos_rechazados", 0.0)) >= 0.25:
        return (f"Notamos algunos pagos rechazados. ¿Quieres probar Pago Móvil sin recargo "
                f"con un aporte de ${sugerido}?")
    return f"¿Quieres programar tu aporte de ${sugerido} cada quincena?"


def _respaldo_reglas(datos: dict) -> float:
    """Heurística de respaldo si el modelo .joblib no está disponible."""
    puntaje = 0.15
    if int(datos.get("dias_desde_ultimo_aporte", 0)) >= 45:
        puntaje += 0.35
    elif int(datos.get("dias_desde_ultimo_aporte", 0)) >= 25:
        puntaje += 0.15
    if int(datos.get("aportes_90d", 1)) == 0:
        puntaje += 0.20
    if float(datos.get("pct_pagos_rechazados", 0.0)) >= 0.20:
        puntaje += 0.15
    if float(datos.get("sesiones_por_mes", 2.0)) < 1.0:
        puntaje += 0.12
    if bool(datos.get("tuvo_caida_unidad", False)):
        puntaje += 0.08
    return min(0.95, round(puntaje, 4))


def predecir_abandono(datos_usuario: dict) -> dict:
    """Estima la probabilidad de que un usuario no aporte en los próximos 60 días."""
    fila = {
        "meses_activo": int(datos_usuario.get("meses_activo", 1)),
        "aportes_90d": int(datos_usuario.get("aportes_90d", 0)),
        "dias_desde_ultimo_aporte": int(datos_usuario.get("dias_desde_ultimo_aporte", 0)),
        "pct_pagos_rechazados": float(datos_usuario.get("pct_pagos_rechazados", 0.0)),
        "sesiones_por_mes": float(datos_usuario.get("sesiones_por_mes", 1.0)),
        "lecciones_vistas": int(datos_usuario.get("lecciones_vistas", 0)),
        "perfil": str(datos_usuario.get("perfil") or "MODERADO").upper(),
        "monto_promedio": float(datos_usuario.get("monto_promedio", 20.0)),
        "tuvo_caida_unidad": int(bool(datos_usuario.get("tuvo_caida_unidad", False))),
    }

    paquete = cargar()
    if paquete is None:
        prob = _respaldo_reglas(fila)
        umbral = 0.45
        motor = "reglas de respaldo (correr python ia/entrenar_abandono.py)"
    else:
        modelo = paquete["modelo"]
        umbral = float(paquete["umbral"])
        x = preparar_x_abandono(pd.DataFrame([fila]))
        prob = round(float(modelo.predict_proba(x)[0, 1]), 4)
        nombre = NOMBRES.get(paquete["nombre"], paquete["nombre"])
        motor = f"modelo abandono: {nombre} (entrenado con datos sintéticos)"

    en_riesgo = prob >= umbral
    nivel = "ALTO" if prob >= max(umbral + 0.18, 0.65) else ("MEDIO" if en_riesgo else "BAJO")

    return {
        "probabilidad_abandono": prob,
        "en_riesgo": en_riesgo,
        "nivel_riesgo": nivel,
        "umbral_alerta": umbral,
        "factores": _factores_explicativos(fila),
        "sugerencia_suave": _sugerencia_suave(en_riesgo, fila),
        "accion_permitida": "SOLO_SUGERIR_RECORDATORIO",
        "aviso_etico": AVISO_ETICO,
        "motor": motor,
    }
