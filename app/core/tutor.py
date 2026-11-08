"""Tutor didáctico con contenido PREDEFINIDO (sin LLM).

La "IA" del tutor no genera texto: SELECCIONA la microlección adecuada según
  - el paso del flujo en que está el usuario,
  - su perfil de riesgo,
  - su nivel de conocimiento (1-2 básico, 3-5 intermedio),
  - las lecciones que ya vio (no repite).
Ventaja: el contenido lo revisa una persona y no hay riesgo de alucinaciones
ni de prometer rendimientos.

Decisión del equipo: el tutor NO interviene cuando un pago es rechazado
(InvierteYa no conoce la causa real); ahí solo se muestra un mensaje según el código.
"""
from __future__ import annotations

PASOS = ("CUESTIONARIO_COMPLETO", "ANTES_PRIMER_APORTE", "UNIDADES_ASIGNADAS",
         "VER_PORTAFOLIO", "ANTES_RESCATE")

LECCIONES = [
    {"id": "L01", "paso": "CUESTIONARIO_COMPLETO", "perfil": "CONSERVADOR", "nivel": "basico",
     "titulo": "¿Qué significa ser Conservador?",
     "texto": "Prefieres no perder dinero aunque eso signifique ganar menos. Por eso tu portafolio "
              "tiene sobre todo renta fija: instrumentos que pagan intereses conocidos de antemano."},
    {"id": "L02", "paso": "CUESTIONARIO_COMPLETO", "perfil": "MODERADO", "nivel": "basico",
     "titulo": "¿Qué significa ser Moderado?",
     "texto": "Aceptas algunos altibajos a cambio de que tu dinero crezca más. Tu portafolio "
              "combina renta fija, fondos y acciones en partes parecidas."},
    {"id": "L03", "paso": "CUESTIONARIO_COMPLETO", "perfil": "AGRESIVO", "nivel": "basico",
     "titulo": "¿Qué significa ser Agresivo?",
     "texto": "Buscas el mayor crecimiento posible y toleras caídas temporales. Tu portafolio "
              "tiene más acciones, que pueden subir mucho pero también bajar."},
    {"id": "L04", "paso": "ANTES_PRIMER_APORTE", "perfil": "TODOS", "nivel": "basico",
     "titulo": "¿Dónde queda mi dinero?",
     "texto": "Tu dinero no queda en InvierteYa: entra a un fideicomiso administrado por un banco "
              "regulado. Ese patrimonio está separado del banco y de nosotros."},
    {"id": "L05", "paso": "UNIDADES_ASIGNADAS", "perfil": "TODOS", "nivel": "basico",
     "titulo": "¿Qué es una unidad de participación?",
     "texto": "Es tu parte del fideicomiso. Si aportaste $20 y cada unidad vale $1,25, recibiste 16 "
              "unidades. Si las inversiones suben, el valor de cada unidad sube y tu saldo también."},
    {"id": "L06", "paso": "UNIDADES_ASIGNADAS", "perfil": "TODOS", "nivel": "intermedio",
     "titulo": "¿Por qué compramos por lotes?",
     "texto": "Juntamos los aportes de muchas personas y el fideicomiso compra títulos completos una vez "
              "al día. Así una inversión de $5 accede a instrumentos que normalmente piden mucho más."},
    {"id": "L07", "paso": "VER_PORTAFOLIO", "perfil": "CONSERVADOR", "nivel": "basico",
     "titulo": "¿Qué es la renta fija?",
     "texto": "Es prestarle dinero a una empresa o al Estado a cambio de intereses. Es la parte más "
              "estable de tu portafolio, aunque no está libre de riesgo."},
    {"id": "L08", "paso": "VER_PORTAFOLIO", "perfil": "TODOS", "nivel": "basico",
     "titulo": "¿Por qué sube y baja mi saldo?",
     "texto": "El valor de tu unidad cambia con el precio de los títulos del fideicomiso. Una baja de "
              "un día es normal; lo importante es tu horizonte de inversión."},
    {"id": "L09", "paso": "VER_PORTAFOLIO", "perfil": "AGRESIVO", "nivel": "intermedio",
     "titulo": "Diversificar no es opcional",
     "texto": "Aunque tu perfil acepte más riesgo, repartir el dinero entre varios instrumentos reduce "
              "el golpe si a uno le va mal."},
    {"id": "L10", "paso": "ANTES_RESCATE", "perfil": "TODOS", "nivel": "basico",
     "titulo": "Antes de retirar",
     "texto": "Retirar se llama rescatar unidades: se venden al valor del día. Si el mercado está bajo, "
              "podrías recibir menos de lo que aportaste."},
]


def nivel_desde_conocimiento(conocimiento: int) -> str:
    return "basico" if conocimiento <= 2 else "intermedio"


def seleccionar(paso: str, perfil: str, conocimiento: int = 1,
                vistas: set[str] | None = None) -> dict | None:
    """Regla de selección: mismo paso; perfil exacto antes que TODOS; nivel del usuario
    antes que otro nivel; nunca repetir una lección vista."""
    if paso not in PASOS:
        raise ValueError(f"Paso desconocido: {paso}")
    vistas = vistas or set()
    nivel = nivel_desde_conocimiento(conocimiento)
    candidatas = [l for l in LECCIONES if l["paso"] == paso and l["id"] not in vistas
                  and l["perfil"] in (perfil, "TODOS")]
    if not candidatas:
        return None
    candidatas.sort(key=lambda l: (l["perfil"] != perfil, l["nivel"] != nivel, l["id"]))
    return candidatas[0]
