"""Casos de prueba del baseline de IA (CP-16 a CP-21).

Ejecutar:  python -m pytest -v tests/test_ia.py
"""
import pandas as pd
import pytest

from app.core.perfil import Cuestionario
from app.core.servicio import InvierteYa
from ia import predictor
from ia.comun import VARIABLES
from ia.entrenar import entrenar
from ia.generar_dataset import generar


def cuestionario(**cambios):
    base = dict(edad=24, ingreso_rango=2, pct_invertible=15, horizonte_anios=2, objetivo="proteger",
                reaccion_caida_20="vender_todo", experiencia_previa=False, fondo_emergencia=False,
                dependientes=0, conocimiento=2)
    base.update(cambios)
    return Cuestionario(**base)


ARRIESGADO = dict(edad=22, ingreso_rango=5, pct_invertible=40, horizonte_anios=10,
                  objetivo="ganar_rapido", reaccion_caida_20="comprar_mas",
                  experiencia_previa=True, conocimiento=5)


@pytest.fixture(scope="module")
def resultado():
    return entrenar(generar(), guardar=False, con_estabilidad=False)


@pytest.fixture
def servicio_con_usuario():
    s = InvierteYa()
    u = s.registrar("Usuario sintético", "u@example.com")
    s.aprobar_kyc(u.id)
    return s, u


# CP-16: el modelo elegido cumple las metas de la ficha de IA en el 20% de prueba.
def test_cp16_modelo_cumple_metas(resultado):
    m = resultado["comparacion"][resultado["modelo_elegido"]]["prueba_con_reglas_de_seguridad"]
    assert m["exactitud"] >= 0.85
    assert all(f1 >= 0.80 for f1 in m["f1_por_clase"].values())
    assert m["conservador_como_agresivo"] == 0


# CP-17: con el modelo conectado, sin fondo de emergencia nunca se asigna Agresivo.
def test_cp17_modelo_respeta_regla_fondo_de_emergencia(servicio_con_usuario):
    if predictor.cargar() is None:
        pytest.skip("Modelo no entrenado: correr python ia/entrenar.py")
    s, u = servicio_con_usuario
    r = s.evaluar_perfil(u.id, cuestionario(**ARRIESGADO, fondo_emergencia=False))
    assert r["perfil"] != "AGRESIVO"
    r2 = s.evaluar_perfil(u.id, cuestionario(**ARRIESGADO, fondo_emergencia=True))
    assert r2["perfil"] == "AGRESIVO" and r2["probabilidad"] >= 0.60


# CP-18: probabilidad < 60% -> revisión humana y perfil provisional MÁS conservador.
def test_cp18_baja_confianza_va_a_revision_humana(servicio_con_usuario, monkeypatch):
    s, u = servicio_con_usuario
    monkeypatch.setattr(predictor, "predecir", lambda c: {
        "perfil": "AGRESIVO", "perfil_modelo": "AGRESIVO", "probabilidad": 0.48,
        "probabilidades": {"CONSERVADOR": 0.05, "MODERADO": 0.47, "AGRESIVO": 0.48},
        "revision_humana": True, "avisos": [], "motor": "modelo (simulado en la prueba)"})
    r = s.evaluar_perfil(u.id, cuestionario())          # las reglas dicen CONSERVADOR
    assert r["revision_humana"] is True
    assert r["perfil"] == "CONSERVADOR"                 # nunca se arriesga de más
    assert any("asesor" in a for a in r["avisos"])
    assert s.revisiones_perfil and s.revisiones_perfil[0]["usuario_id"] == u.id


# CP-19: si el modelo no está disponible, la API sigue funcionando con las reglas.
def test_cp19_sin_modelo_se_usan_las_reglas(servicio_con_usuario, monkeypatch):
    s, u = servicio_con_usuario
    monkeypatch.setattr(predictor, "predecir", lambda c: None)
    r = s.evaluar_perfil(u.id, cuestionario())
    assert r["perfil"] == r["perfil_reglas"] == "CONSERVADOR"
    assert r["motor"].startswith("reglas") and r["probabilidad"] is None


# CP-20: el dataset es reproducible y solo contiene datos sintéticos (sin datos personales).
def test_cp20_dataset_reproducible_y_sintetico():
    a, b = generar(n=300), generar(n=300)
    pd.testing.assert_frame_equal(a, b)
    assert a["id"].str.startswith("syn_").all()
    columnas_permitidas = {"id", *VARIABLES, "puntaje_reglas", "ruido", "puntaje_con_ruido", "perfil"}
    assert set(a.columns) == columnas_permitidas          # sin nombres, cédulas, correos ni tarjetas
    sin_fondo = a[~a["fondo_emergencia"]]
    assert (sin_fondo["perfil"] != "AGRESIVO").all()      # la etiqueta también respeta la regla


# CP-21: no hay sesgo grueso por edad: la exactitud de cada grupo de edad es >= 80%.
def test_cp21_metricas_por_grupo_de_edad(resultado):
    for grupo in resultado["metricas_por_grupo"]["edad"]:
        assert grupo["exactitud"] >= 0.80, grupo
