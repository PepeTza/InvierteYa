"""Casos de prueba del flujo transaccional (base del plan de certificación).

Ejecutar:  python -m pytest -v
"""
from datetime import date

import pytest

from app.core.perfil import Cuestionario, evaluar
from app.core.servicio import ErrorNegocio, InvierteYa


def cuestionario(**cambios):
    base = dict(edad=24, ingreso_rango=2, pct_invertible=15, horizonte_anios=2, objetivo="proteger",
                reaccion_caida_20="vender_todo", experiencia_previa=False, fondo_emergencia=False,
                dependientes=0, conocimiento=2)
    base.update(cambios)
    return Cuestionario(**base)


@pytest.fixture
def entorno():
    s = InvierteYa()
    u = s.registrar("María (sintética)", "maria@example.com")
    s.aprobar_kyc(u.id)
    s.evaluar_perfil(u.id, cuestionario())
    s.firmar_adhesion(u.id, True)
    token = s.pasarela.tokenizar("4111111111111111")  # tarjeta de PRUEBA
    return s, u, token


def estados(aporte):
    return [e["estado"] for e in aporte["eventos"]]


# ---------- CP-01 a CP-04: autorización ----------
def test_cp01_aprobada_asigna_unidades_y_leccion(entorno):
    s, u, t = entorno
    s.pasarela.forzar("APROBADA")
    a = s.crear_aporte(u.id, 2000, t, "k1")
    assert estados(a) == ["PENDIENTE", "AUTORIZADO", "CAPTURADO", "ASIGNADO"]
    assert a["unidades"] == "16.0000"                      # $20 / $1,25
    assert [m["mti"] for m in a["iso8583"]] == ["0100", "0110", "0220", "0230"]
    assert a["leccion"]["paso"] == "UNIDADES_ASIGNADAS"


def test_cp02_rechazo_51_mensaje_de_saldo_y_sin_tutor(entorno):
    s, u, t = entorno
    s.pasarela.forzar("51")
    a = s.crear_aporte(u.id, 2000, t, "k2")
    assert a["estado"] == "RECHAZADO"
    assert "saldo insuficiente" in a["mensaje"]
    assert a["leccion"] is None                            # decisión del equipo


def test_cp03_rechazo_59_fraude_no_revela_motivo(entorno):
    s, u, t = entorno
    s.pasarela.forzar("59")
    a = s.crear_aporte(u.id, 2000, t, "k3")
    assert a["estado"] == "RECHAZADO"
    assert "fraude" not in a["mensaje"].lower()


def test_cp04_pan_nunca_llega_a_invierteya(entorno):
    s, u, t = entorno
    s.pasarela.forzar("APROBADA")
    a = s.crear_aporte(u.id, 2000, t, "k4")
    assert "4111111111111111" not in str(a)
    assert a["iso8583"][0]["campos"]["2"] == "4111********1111"


# ---------- CP-05 a CP-08: reverso e idempotencia ----------
def test_cp05_timeout_dispara_reverso(entorno):
    s, u, t = entorno
    s.pasarela.forzar("TIMEOUT")
    a = s.crear_aporte(u.id, 2000, t, "k5")
    assert estados(a)[-1] == "REVERSADO"
    assert "0400" in [m["mti"] for m in a["iso8583"]]
    assert "90" in a["iso8583"][1]["campos"]               # datos de la transacción original


def test_cp06_falla_de_captura_reversa_la_autorizacion(entorno):
    s, u, t = entorno
    s.pasarela.forzar("APROBADA", "FALLA_CAPTURA")
    a = s.crear_aporte(u.id, 2000, t, "k6")
    assert estados(a) == ["PENDIENTE", "AUTORIZADO", "EN_REVERSO", "REVERSADO"]
    assert a["unidades"] is None


def test_cp07_reverso_sin_respuesta_va_a_excepciones(entorno):
    s, u, t = entorno
    s.pasarela.forzar("TIMEOUT", "REVERSO_SIN_RESPUESTA")
    a = s.crear_aporte(u.id, 2000, t, "k7")
    assert a["estado"] == "REVERSO_PENDIENTE"
    assert [m["mti"] for m in a["iso8583"]].count("0421") == 3
    assert s.excepciones and s.excepciones[0]["aporte_id"] == a["id"]


def test_cp08_idempotencia_no_cobra_dos_veces(entorno):
    s, u, t = entorno
    s.pasarela.forzar("APROBADA")
    a1 = s.crear_aporte(u.id, 2000, t, "misma-clave")
    a2 = s.crear_aporte(u.id, 2000, t, "misma-clave")
    assert a2["duplicado"] is True and a2["id"] == a1["id"]
    assert len(s.pasarela.autorizaciones) == 1


def test_cp09_captura_sin_autorizacion_falla(entorno):
    s, _, _ = entorno
    r = s.pasarela.capturar("auth_inexistente", 2000)
    assert r.status == "NOT_CAPTURABLE"


# ---------- CP-10 a CP-12: reglas de negocio ----------
def test_cp10_monto_minimo_5_dolares(entorno):
    s, u, t = entorno
    with pytest.raises(ErrorNegocio) as e:
        s.crear_aporte(u.id, 499, t, "k10")
    assert e.value.codigo == "MONTO_INVALIDO"


def test_cp11_sin_adhesion_no_se_puede_aportar():
    s = InvierteYa()
    u = s.registrar("Pedro (sintético)", "pedro@example.com")
    s.aprobar_kyc(u.id)
    s.evaluar_perfil(u.id, cuestionario())
    with pytest.raises(ErrorNegocio) as e:
        s.crear_aporte(u.id, 2000, s.pasarela.tokenizar("4111111111111111"), "k11")
    assert e.value.codigo == "ADHESION_PENDIENTE"


def test_cp12_sin_fondo_de_emergencia_nunca_agresivo():
    r = evaluar(cuestionario(edad=22, ingreso_rango=5, pct_invertible=40, horizonte_anios=10,
                             objetivo="ganar_rapido", reaccion_caida_20="comprar_mas",
                             experiencia_previa=True, fondo_emergencia=False, conocimiento=5))
    assert r["perfil"] == "MODERADO" and r["avisos"]


# ---------- CP-13 y CP-14: conciliación ----------
def test_cp13_conciliacion_cuadra_y_batch_aprobado(entorno):
    s, u, t = entorno
    for i in range(5):
        s.pasarela.forzar("APROBADA")
        s.crear_aporte(u.id, 2000 + i * 100, t, f"c{i}")
    r = s.cerrar_dia(date.today())
    assert r["conciliado"] is True
    assert r["batch"]["aprobada"] is True
    assert {o["instrumento"] for o in r["propuesta_ordenes"]} == {"renta_fija", "fondos", "acciones"}


def test_cp14_conciliacion_detecta_descuadre(entorno):
    s, u, t = entorno
    for i in range(3):
        s.pasarela.forzar("APROBADA")
        s.crear_aporte(u.id, 2000, t, f"d{i}")
    r = s.cerrar_dia(date.today(), inyectar_descuadre=True)
    tipos = {e["tipo"] for e in r["excepciones"]}
    assert r["conciliado"] is False
    assert "CAPTURADO_SIN_LIQUIDAR" in tipos and "DIFERENCIA_LIQUIDACION" in tipos


def test_cp15_el_cierre_no_se_duplica(entorno):
    s, u, t = entorno
    s.pasarela.forzar("APROBADA")
    s.crear_aporte(u.id, 2000, t, "e1")
    primero = s.cerrar_dia(date.today())
    segundo = s.cerrar_dia(date.today())
    assert primero["conciliado"] and segundo["ya_cerrado"] is True
    assert s.fideicomiso.estado_posiciones()["CONSERVADOR"] == 2000
