"""Casos de prueba de la IA predictiva y cuestionario nuevo · Sesión 3 (CP-22 a CP-29).

Ejecutar:  python -m pytest -v tests/test_ia_s3.py
"""
import pandas as pd

from app.core.perfil import Cuestionario, evaluar
from ia import predictor, predictor_abandono
from ia.entrenar_abandono import entrenar_abandono
from ia.generar_dataset_comportamiento import (FIDEICOMISOS_CATALOGO,
                                               generar_comportamiento,
                                               generar_flujos_diarios)
from ia.pronostico_flujos import evaluar_y_pronosticar


# CP-22: dataset sintético de comportamiento reproducible y libre de PII.
def test_cp22_dataset_comportamiento_reproducible_y_sin_pii():
    a = generar_comportamiento(n_usuarios=300)
    b = generar_comportamiento(n_usuarios=300)
    pd.testing.assert_frame_equal(a, b)
    assert a["usuario_id"].str.startswith("syn_").all()
    assert a["mes"].min() == 1 and a["mes"].max() == 12
    prohibidas = {"nombre", "email", "cedula", "telefono", "pan", "tarjeta"}
    assert prohibidas.isdisjoint(set(a.columns))
    etiquetados = a.dropna(subset=["abandona_60d"])
    assert 0.10 < etiquetados["abandona_60d"].mean() < 0.70


# CP-23: modelo de abandono usa split temporal estricto (1-9 vs 10-12) y cumple AUC >= 0,80 y recall >= 0,70.
def test_cp23_modelo_abandono_split_temporal_y_metas():
    df = generar_comportamiento(n_usuarios=1500)
    r = entrenar_abandono(df=df, guardar=False)
    split = r["dataset"]["split_temporal"]
    assert max(split["entrenamiento_cortes_meses"]) <= 7
    assert split["etiquetas_entrenamiento_hasta_mes"] <= 9
    assert split["prueba_corte_mes"] >= 10
    m = r["comparacion"][r["modelo_elegido"]]["prueba_meses_10_12"]
    assert m["auc_roc"] >= 0.80, m
    assert m["recall"] >= 0.70, m


# CP-24: el modelo de abandono mantiene desempeño parejo por grupo de edad y ahorro (sin sesgo grueso).
def test_cp24_modelo_abandono_sesgo_por_grupo():
    df = generar_comportamiento(n_usuarios=1500)
    r = entrenar_abandono(df=df, guardar=False)
    for grupo in r["metricas_por_grupo"]["edad"]:
        assert grupo["auc_roc"] >= 0.78, grupo
    for grupo in r["metricas_por_grupo"]["ahorro_mensual"]:
        assert grupo["auc_roc"] >= 0.78, grupo


# CP-25: predictor de abandono distingue activo vs en riesgo, solo sugiere y tiene respaldo.
def test_cp25_predictor_abandono_y_respaldo():
    activo = predictor_abandono.predecir_abandono({
        "meses_activo": 6, "aportes_90d": 5, "dias_desde_ultimo_aporte": 7,
        "pct_pagos_rechazados": 0.0, "sesiones_por_mes": 6.0, "lecciones_vistas": 5,
        "perfil": "MODERADO", "monto_promedio": 25.0, "tuvo_caida_unidad": False,
    })
    en_riesgo = predictor_abandono.predecir_abandono({
        "meses_activo": 6, "aportes_90d": 0, "dias_desde_ultimo_aporte": 65,
        "pct_pagos_rechazados": 0.40, "sesiones_por_mes": 0.2, "lecciones_vistas": 1,
        "perfil": "CONSERVADOR", "monto_promedio": 20.0, "tuvo_caida_unidad": True,
    })
    assert en_riesgo["probabilidad_abandono"] > activo["probabilidad_abandono"]
    assert en_riesgo["en_riesgo"] is True
    assert en_riesgo["sugerencia_suave"] is not None
    assert en_riesgo["accion_permitida"] == "SOLO_SUGERIR_RECORDATORIO"

    # Respaldo si no hubiera modelo disponible
    prev_cargado, prev_cache = predictor_abandono._cargado, predictor_abandono._cache
    try:
        predictor_abandono._cargado, predictor_abandono._cache = True, None
        respaldo = predictor_abandono.predecir_abandono({
            "dias_desde_ultimo_aporte": 60, "aportes_90d": 0, "pct_pagos_rechazados": 0.3,
            "sesiones_por_mes": 0.5, "tuvo_caida_unidad": True,
        })
        assert respaldo["en_riesgo"] is True
        assert respaldo["motor"].startswith("reglas")
    finally:
        predictor_abandono._cargado, predictor_abandono._cache = prev_cargado, prev_cache


# CP-26: pronóstico de flujos cubre los 5 fideicomisos con MAE y MAPE y mejora sobre media móvil.
def test_cp26_pronostico_flujos_5_fideicomisos():
    df_flujos = generar_flujos_diarios(n_dias=365)
    r = evaluar_y_pronosticar(df=df_flujos, guardar=False)
    ids = {f["fideicomiso_id"] for f in r["por_fideicomiso"]}
    assert ids == {f["id"] for f in FIDEICOMISOS_CATALOGO}
    assert r["total_manana_usd"] > 0 and r["total_7d_usd"] > r["total_manana_usd"]
    comp = r["comparacion_total"]
    assert comp["regresion_lineal_rezagos"]["mape_pct"] < comp["media_movil_7d"]["mape_pct"]


# CP-27: cuestionario S3 con "Prefiero no decirlo" o "no_podria" nunca asigna Agresivo.
def test_cp27_cuestionario_s3_prefiero_no_decir_y_no_podria_nunca_agresivo():
    c_no_podria = Cuestionario.desde_s3(
        edad=23, ahorro_mensual_rango=4, horizonte_anios=7.0,
        objetivo="ganar_rapido", reaccion_caida_20="comprar_mas",
        emergencia_200="no_podria", experiencia_tipo="acciones",
        dependientes=0, quiz_aciertos=2,
    )
    c_omitido = Cuestionario.desde_s3(
        edad=23, ahorro_mensual_rango=None, horizonte_anios=7.0,
        objetivo="ganar_rapido", reaccion_caida_20="comprar_mas",
        emergencia_200=None, experiencia_tipo="acciones",
        dependientes=0, quiz_aciertos=2,
    )
    assert evaluar(c_no_podria)["perfil"] != "AGRESIVO"
    assert evaluar(c_omitido)["perfil"] != "AGRESIVO"
    assert "ahorro_mensual_rango" in c_omitido.campos_omitidos()
    assert "emergencia_200" in c_omitido.campos_omitidos()

    if predictor.cargar() is not None:
        assert predictor.predecir(c_no_podria)["perfil"] != "AGRESIVO"
        assert predictor.predecir(c_omitido)["perfil"] != "AGRESIVO"


# CP-28: cuestionario S3 en 2 tandas funciona prudente en Tanda 1 y se afina en Tanda 2.
def test_cp28_cuestionario_s3_dos_tandas():
    t1 = Cuestionario.desde_s3(
        edad=24, ahorro_mensual_rango=2, horizonte_anios=2.0,
        objetivo="crecer", reaccion_caida_20="esperar",
        emergencia_200="ahorros", experiencia_tipo="ahorro_dolares",
        dependientes=None, quiz_aciertos=None,
    )
    t2 = Cuestionario.desde_s3(
        edad=24, ahorro_mensual_rango=2, horizonte_anios=2.0,
        objetivo="crecer", reaccion_caida_20="esperar",
        emergencia_200="ahorros", experiencia_tipo="ahorro_dolares",
        dependientes=0, quiz_aciertos=2,
    )
    r1, r2 = evaluar(t1), evaluar(t2)
    assert r1["tanda_completada"] == 1 and r2["tanda_completada"] == 2
    assert r1["puntaje"] <= r2["puntaje"]
    assert any("Afinemos tu perfil" in a for a in r1["avisos"])


# CP-29: explicabilidad y transparencia S3 (contrafactuales + aviso modelo automático).
def test_cp29_transparencia_y_contrafactuales():
    c = Cuestionario.desde_s3(
        edad=24, ahorro_mensual_rango=2, horizonte_anios=2.0,
        objetivo="crecer", reaccion_caida_20="esperar",
        emergencia_200="ahorros", experiencia_tipo="ahorro_dolares",
        dependientes=0, quiz_aciertos=1,
    )
    r = evaluar(c)
    assert "modelo automático" in r["aviso_transparencia"]
    assert "no garantiza" in r["nota_rendimiento"]
    assert isinstance(r["que_cambiaria"], list) and len(r["que_cambiaria"]) >= 1
