"""Perfil de riesgo por reglas (puntaje de idoneidad).

Hoy cumple dos funciones:
  1. Asigna el perfil en el prototipo mientras se entrena el modelo baseline.
  2. Es la regla con la que se ETIQUETA el dataset sintético (más ruido aleatorio)
     para entrenar el árbol de decisión / regresión logística (ver ficha de IA, Sesión 1).

Las 10 variables son las de la ficha del componente de IA de la Sesión 1.
"""
from __future__ import annotations

from dataclasses import dataclass

OBJETIVOS = {"proteger": 0, "crecer": 2, "ganar_rapido": 3}
REACCIONES = {"vender_todo": 0, "esperar": 2, "comprar_mas": 3}
PUNTAJE_MAXIMO = 19


@dataclass
class Cuestionario:
    edad: int
    ingreso_rango: int            # 1 (más bajo) a 5 (más alto)
    pct_invertible: float         # % del ingreso que puede invertir
    horizonte_anios: float
    objetivo: str                 # proteger | crecer | ganar_rapido
    reaccion_caida_20: str        # vender_todo | esperar | comprar_mas
    experiencia_previa: bool
    fondo_emergencia: bool
    dependientes: int
    conocimiento: int             # autoevaluado, 1 a 5


def _puntos(c: Cuestionario) -> dict[str, float]:
    return {
        "horizonte": 0 if c.horizonte_anios < 1 else 1 if c.horizonte_anios < 3 else 2 if c.horizonte_anios < 5 else 3,
        "objetivo": OBJETIVOS[c.objetivo],
        "reaccion_caida": REACCIONES[c.reaccion_caida_20],
        "experiencia": 1 if c.experiencia_previa else 0,
        "conocimiento": (c.conocimiento - 1) / 2,
        "pct_invertible": 0 if c.pct_invertible < 10 else 1 if c.pct_invertible <= 25 else 2,
        "edad": 2 if c.edad < 30 else 1 if c.edad <= 45 else 0,
        "dependientes": 1 if c.dependientes == 0 else 0,
        "ingreso": (c.ingreso_rango - 1) / 2,
    }


EXPLICACIONES = {
    "horizonte": "tu horizonte de inversión",
    "objetivo": "tu objetivo",
    "reaccion_caida": "cómo reaccionarías ante una caída del 20%",
    "experiencia": "tu experiencia previa",
    "conocimiento": "tu conocimiento financiero",
    "pct_invertible": "la parte de tu ingreso que puedes invertir",
    "edad": "tu edad",
    "dependientes": "tus dependientes económicos",
    "ingreso": "tu nivel de ingreso",
}


# Frases para los factores que restan riesgo (puntaje 0), en orden de importancia.
EXPLICACIONES_CUIDADO = {
    "objetivo": "prefieres proteger tu dinero",
    "reaccion_caida": "venderías ante una caída del 20%",
    "horizonte": "tu horizonte es menor a un año",
    "experiencia": "no tienes experiencia previa invirtiendo",
    "pct_invertible": "puedes invertir menos del 10% de tu ingreso",
    "dependientes": "tienes dependientes económicos",
    "conocimiento": "tu conocimiento financiero es inicial",
    "ingreso": "tu nivel de ingreso",
    "edad": "tu edad",
}


def puntaje_a_perfil(puntaje: float) -> str:
    if puntaje < 7:
        return "CONSERVADOR"
    if puntaje < 13:
        return "MODERADO"
    return "AGRESIVO"


def aplicar_reglas_seguridad(perfil: str, c: Cuestionario) -> tuple[str, list[str]]:
    """Reglas que el modelo NUNCA puede saltarse (ficha de IA, mitigaciones)."""
    avisos = []
    if not c.fondo_emergencia and perfil == "AGRESIVO":
        perfil = "MODERADO"
        avisos.append("Sin fondo de emergencia nunca se asigna el perfil Agresivo.")
    return perfil, avisos


def evaluar(c: Cuestionario) -> dict:
    puntos = _puntos(c)
    total = round(sum(puntos.values()), 2)
    perfil, avisos = aplicar_reglas_seguridad(puntaje_a_perfil(total), c)
    return {"perfil": perfil, "puntaje": total, "puntaje_maximo": PUNTAJE_MAXIMO,
            "explicacion": explicar(puntos, perfil), "avisos": avisos, "detalle_puntos": puntos}


def explicar(puntos: dict[str, float], perfil: str) -> str:
    """Explicación en lenguaje simple: qué empujó hacia más riesgo y qué hacia menos.
    Se usa tanto con el perfil de las reglas como con el del modelo baseline."""
    ordenados = sorted(puntos.items(), key=lambda kv: kv[1], reverse=True)
    hacia_riesgo = [EXPLICACIONES[k] for k, v in ordenados[:2] if v > 0]
    hacia_cuidado = [frase for k, frase in EXPLICACIONES_CUIDADO.items() if puntos[k] == 0][:2]
    explicacion = f"Te asignamos el perfil {perfil.capitalize()}"
    if perfil == "CONSERVADOR" and hacia_cuidado:
        explicacion += f" sobre todo porque {' y '.join(hacia_cuidado)}"
    elif perfil == "AGRESIVO" and hacia_riesgo:
        explicacion += f" sobre todo por {' y '.join(hacia_riesgo)}"
    elif hacia_riesgo:
        explicacion += f": suben tu tolerancia {' y '.join(hacia_riesgo)}"
        if hacia_cuidado:
            explicacion += f"; la moderan que {' y '.join(hacia_cuidado)}"
    explicacion += "."
    return explicacion
