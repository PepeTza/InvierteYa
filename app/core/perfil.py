"""Perfil de riesgo por reglas (puntaje de idoneidad) · Sesión 3 (cuestionario conversacional en 2 tandas).

Soporta tanto el cuestionario situacional de la Sesión 3 (6 preguntas Tanda 1 + 3 Tanda 2,
edad desde KYC y opción "Prefiero no decirlo" tratada de forma prudente) como el formato
de 10 variables de la Sesión 2 (retrocompatibilidad con pruebas CP-01..CP-21).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

OBJETIVOS = {"proteger": 0, "crecer": 2, "ganar_rapido": 3}
REACCIONES = {"vender_todo": 0, "esperar": 2, "comprar_mas": 3}
EXPERIENCIA_PUNTOS = {"ninguna": 0.0, "ahorro_dolares": 0.5, "caja_ahorro": 0.5, "acciones": 1.0}
EMERGENCIA_PUNTOS = {"ahorros": 1.0, "prestado": 0.0, "no_podria": 0.0}
QUIZ_A_CONOCIMIENTO = {0: 1, 1: 3, 2: 5}
PUNTAJE_MAXIMO = 19

AVISO_TRANSPARENCIA = ("Esta sugerencia la hace un modelo automático; "
                       "tú decides y un asesor puede revisarla.")
NOTA_RENDIMIENTO = "El rendimiento histórico no garantiza resultados futuros."


@dataclass
class Cuestionario:
    edad: int
    ingreso_rango: int | None = 2               # S2 (1..5) o derivado de ahorro_mensual_rango; None = omitido
    pct_invertible: float | None = 15.0         # S2 (0..50) o derivado; None = omitido
    horizonte_anios: float = 2.0
    objetivo: str = "proteger"                  # proteger | crecer | ganar_rapido
    reaccion_caida_20: str = "vender_todo"      # vender_todo | esperar | comprar_mas
    experiencia_previa: bool = False
    fondo_emergencia: bool = False
    dependientes: int | None = 0                # Tanda 2: None si aún no se completa
    conocimiento: int | None = 2                # Tanda 2 (1..5 o derivado del quiz): None si pendiente
    # Extensiones Sesión 3 (cuestionario situacional en 2 tandas)
    ahorro_mensual_rango: int | None = None     # 1 ($5-$20), 2 ($20-$50), 3 ($50-$100), 4 (>$100), None (no dice)
    emergencia_200: str | None = None           # ahorros | prestado | no_podria | None (no dice)
    experiencia_tipo: str | None = None         # ninguna | ahorro_dolares | caja_ahorro | acciones
    tanda_completada: int = 2
    ahorro_omitido: bool = False
    emergencia_omitida: bool = False

    def __post_init__(self):
        # Completar campos S3 cuando se construye con el formato clásico de S2
        if self.emergencia_200 is None and not self.emergencia_omitida:
            self.emergencia_200 = "ahorros" if self.fondo_emergencia else "no_podria"
        elif self.emergencia_200 is not None:
            self.fondo_emergencia = self.emergencia_200 == "ahorros"
        elif self.emergencia_omitida:
            self.fondo_emergencia = False

        if self.experiencia_tipo is None:
            self.experiencia_tipo = "acciones" if self.experiencia_previa else "ninguna"
        else:
            self.experiencia_previa = self.experiencia_tipo != "ninguna"

        if self.ahorro_mensual_rango is None and not self.ahorro_omitido:
            if self.ingreso_rango is not None:
                self.ahorro_mensual_rango = min(4, max(1, int(self.ingreso_rango)))
        elif self.ahorro_mensual_rango is not None:
            if self.ingreso_rango is None:
                self.ingreso_rango = min(5, max(1, int(self.ahorro_mensual_rango) + (1 if self.ahorro_mensual_rango == 4 else 0)))
            if self.pct_invertible is None:
                self.pct_invertible = {1: 8.0, 2: 15.0, 3: 24.0, 4: 32.0}[int(self.ahorro_mensual_rango)]
        elif self.ahorro_omitido:
            self.ingreso_rango = None
            self.pct_invertible = None

        if self.dependientes is None or self.conocimiento is None:
            self.tanda_completada = 1

    @classmethod
    def desde_s3(
        cls,
        *,
        edad: int,
        horizonte_anios: float,
        objetivo: str,
        reaccion_caida_20: str,
        ahorro_mensual_rango: int | None = None,
        emergencia_200: str | None = None,
        experiencia_tipo: str = "ninguna",
        dependientes: int | None = None,
        quiz_aciertos: int | None = None,
    ) -> "Cuestionario":
        """Constructor del cuestionario conversacional en 2 tandas (Sesión 3)."""
        ahorro_omitido = ahorro_mensual_rango is None
        emergencia_omitida = emergencia_200 is None
        conocimiento = QUIZ_A_CONOCIMIENTO.get(quiz_aciertos) if quiz_aciertos is not None else None
        tanda = 2 if (dependientes is not None and conocimiento is not None) else 1
        ingreso = None if ahorro_omitido else {1: 1, 2: 2, 3: 3, 4: 5}[int(ahorro_mensual_rango)]
        pct = None if ahorro_omitido else {1: 8.0, 2: 15.0, 3: 24.0, 4: 32.0}[int(ahorro_mensual_rango)]
        return cls(
            edad=edad,
            ingreso_rango=ingreso,
            pct_invertible=pct,
            horizonte_anios=horizonte_anios,
            objetivo=objetivo,
            reaccion_caida_20=reaccion_caida_20,
            experiencia_previa=experiencia_tipo != "ninguna",
            fondo_emergencia=(emergencia_200 == "ahorros"),
            dependientes=dependientes,
            conocimiento=conocimiento,
            ahorro_mensual_rango=ahorro_mensual_rango,
            emergencia_200=emergencia_200,
            experiencia_tipo=experiencia_tipo,
            tanda_completada=tanda,
            ahorro_omitido=ahorro_omitido,
            emergencia_omitida=emergencia_omitida,
        )

    def campos_omitidos(self) -> list[str]:
        omitidos = []
        if self.ahorro_omitido or self.ahorro_mensual_rango is None:
            omitidos.append("ahorro_mensual_rango")
        if self.emergencia_omitida or self.emergencia_200 is None:
            omitidos.append("emergencia_200")
        if self.dependientes is None:
            omitidos.append("dependientes")
        if self.conocimiento is None:
            omitidos.append("conocimiento")
        return omitidos


def _puntos(c: Cuestionario) -> dict[str, float]:
    # Si un dato fue omitido ("Prefiero no decirlo" o Tanda 2 pendiente), se asigna puntaje
    # prudente (0) para nunca sobreestimar la tolerancia al riesgo.
    if c.pct_invertible is None:
        pts_pct = 0.0
    else:
        pts_pct = 0.0 if c.pct_invertible < 10 else 1.0 if c.pct_invertible <= 25 else 2.0

    if c.ingreso_rango is None:
        pts_ingreso = 0.0
    else:
        pts_ingreso = (c.ingreso_rango - 1) / 2.0

    pts_exp = EXPERIENCIA_PUNTOS.get(c.experiencia_tipo or "ninguna", 1.0 if c.experiencia_previa else 0.0)
    pts_conoc = 0.0 if c.conocimiento is None else (c.conocimiento - 1) / 2.0
    pts_dep = 0.0 if c.dependientes is None else (1.0 if c.dependientes == 0 else 0.0)

    return {
        "horizonte": 0 if c.horizonte_anios < 1 else 1 if c.horizonte_anios < 3 else 2 if c.horizonte_anios < 5 else 3,
        "objetivo": OBJETIVOS[c.objetivo],
        "reaccion_caida": REACCIONES[c.reaccion_caida_20],
        "experiencia": pts_exp,
        "conocimiento": pts_conoc,
        "pct_invertible": pts_pct,
        "edad": 2 if c.edad < 30 else 1 if c.edad <= 45 else 0,
        "dependientes": pts_dep,
        "ingreso": pts_ingreso,
    }


EXPLICACIONES = {
    "horizonte": "tu horizonte de inversión",
    "objetivo": "tu objetivo",
    "reaccion_caida": "cómo reaccionarías si $100 bajan a $80",
    "experiencia": "tu experiencia previa",
    "conocimiento": "tu conocimiento financiero",
    "pct_invertible": "el monto que puedes apartar al mes",
    "edad": "tu edad (tomada de tu KYC)",
    "dependientes": "tu hogar",
    "ingreso": "tu capacidad de ahorro mensual",
}

EXPLICACIONES_CUIDADO = {
    "objetivo": "prefieres proteger tu dinero",
    "reaccion_caida": "venderías si tu inversión cae de $100 a $80",
    "horizonte": "tu horizonte es menor a un año",
    "experiencia": "estás dando tus primeros pasos invirtiendo",
    "pct_invertible": "prefieres empezar con un monto mensual moderado",
    "dependientes": "tienes personas a tu cargo",
    "conocimiento": "tu conocimiento financiero es inicial",
    "ingreso": "tu capacidad de ahorro mensual es prudente",
    "edad": "tu edad",
}


def puntaje_a_perfil(puntaje: float) -> str:
    if puntaje < 7:
        return "CONSERVADOR"
    if puntaje < 13:
        return "MODERADO"
    return "AGRESIVO"


def aplicar_reglas_seguridad(perfil: str, c: Cuestionario) -> tuple[str, list[str]]:
    """Reglas que el modelo NUNCA puede saltarse (ficha de IA y Model Card S3)."""
    avisos = []
    sin_colchon = (not c.fondo_emergencia) or (c.emergencia_200 in ("no_podria", None))
    if sin_colchon and perfil == "AGRESIVO":
        perfil = "MODERADO"
        if c.emergencia_omitida or c.emergencia_200 is None:
            avisos.append("Al no confirmar respaldo para imprevistos, aplicamos un criterio prudente: nunca Agresivo.")
        else:
            avisos.append("Sin fondo de emergencia nunca se asigna el perfil Agresivo.")
    if c.tanda_completada < 2:
        avisos.append("Perfil inicial con 6 preguntas. Puedes afinarlo luego en 'Afinemos tu perfil'.")
    return perfil, avisos


def que_cambiaria_perfil(c: Cuestionario, perfil_actual: str) -> list[str]:
    """Contrafactuales simples: explica qué cambio de respuesta movería el perfil."""
    cambios = []
    pruebas = [
        ("si tu horizonte fuera de más de 5 años", replace(c, horizonte_anios=7.0)),
        ("si ante una caída de $100 a $80 eligieras vender todo", replace(c, reaccion_caida_20="vender_todo")),
        ("si ante una caída de $100 a $80 decidieras esperar o aprovechar para comprar más",
         replace(c, reaccion_caida_20="comprar_mas")),
        ("si pudieras cubrir un imprevisto de $200 con ahorros propios",
         replace(c, fondo_emergencia=True, emergencia_200="ahorros", emergencia_omitida=False)),
        ("si tu objetivo principal fuera proteger tu capital", replace(c, objetivo="proteger")),
    ]
    for texto, mod in pruebas:
        nuevo = puntaje_a_perfil(round(sum(_puntos(mod).values()), 2))
        nuevo, _ = aplicar_reglas_seguridad(nuevo, mod)
        if nuevo != perfil_actual:
            cambios.append(f"Por ejemplo, {texto}, tu perfil cambiaría a {nuevo.capitalize()}.")
        if len(cambios) >= 2:
            break
    return cambios


def evaluar(c: Cuestionario) -> dict:
    puntos = _puntos(c)
    total = round(sum(puntos.values()), 2)
    perfil, avisos = aplicar_reglas_seguridad(puntaje_a_perfil(total), c)
    suben, moderan = factores(puntos)
    return {
        "perfil": perfil,
        "puntaje": total,
        "puntaje_maximo": PUNTAJE_MAXIMO,
        "explicacion": explicar(puntos, perfil),
        "avisos": avisos,
        "detalle_puntos": puntos,
        "factores_suben": suben,
        "factores_moderan": moderan,
        "tanda_completada": c.tanda_completada,
        "campos_omitidos": c.campos_omitidos(),
        "que_cambiaria": que_cambiaria_perfil(c, perfil),
        "aviso_transparencia": AVISO_TRANSPARENCIA,
        "nota_rendimiento": NOTA_RENDIMIENTO,
    }


def _riesgo_y_cuidado(puntos: dict[str, float]) -> tuple[list[str], list[str]]:
    ordenados = sorted(puntos.items(), key=lambda kv: kv[1], reverse=True)
    hacia_riesgo = [EXPLICACIONES[k] for k, v in ordenados[:2] if v > 0]
    hacia_cuidado = [frase for k, frase in EXPLICACIONES_CUIDADO.items() if puntos[k] == 0][:2]
    return hacia_riesgo, hacia_cuidado


def factores(puntos: dict[str, float]) -> tuple[list[str], list[str]]:
    capitalizar = lambda t: t[:1].upper() + t[1:]
    suben, moderan = _riesgo_y_cuidado(puntos)
    return [capitalizar(t) for t in suben], [capitalizar(t) for t in moderan]


def explicar(puntos: dict[str, float], perfil: str) -> str:
    hacia_riesgo, hacia_cuidado = _riesgo_y_cuidado(puntos)
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
