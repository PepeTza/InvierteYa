"""Casos de prueba del backend de la Sesión 3 (Track 2 · catálogo, aportes repartidos, privacidad).

CP-30 a CP-49. Ejecutar:  python -m pytest -v tests/test_catalogo_s3.py
"""
import asyncio
import json
from datetime import date, datetime, timedelta

import pytest

from app.core import catalogo as cat
from app.core.perfil import Cuestionario
from app.core.seguridad_datos import (CifradorCampos, ErrorCifrado, KMSSimulado, a_capa_plata,
                                      agregar_capa_oro, hash_documento)
from app.core.servicio import ErrorNegocio, InvierteYa

TARJETA = "4111111111111111"      # PAN de PRUEBA
PAGO_MOVIL = "04140000000"        # teléfono sintético


def cuestionario(**cambios):
    base = dict(edad=24, ingreso_rango=2, pct_invertible=15, horizonte_anios=2, objetivo="proteger",
                reaccion_caida_20="vender_todo", experiencia_previa=False, fondo_emergencia=False,
                dependientes=0, conocimiento=2)
    base.update(cambios)
    return Cuestionario(**base)


MODERADO_S3 = dict(ahorro_mensual_rango=2, horizonte_anios=4.0, objetivo="crecer",
                   reaccion_caida_20="esperar", emergencia_200="ahorros", experiencia_tipo="ahorro_dolares")


def usuario_con_perfil(s: InvierteYa, perfil: str):
    """Crea un usuario y le fija el perfil (las reglas/modelo se prueban en test_ia*)."""
    u = s.registrar("Ana (sintética)", "ana@example.com")
    s.aprobar_kyc(u.id, edad=30)
    s.evaluar_perfil(u.id, cuestionario())
    u.perfil = perfil
    return u


@pytest.fixture
def moderado():
    s = InvierteYa()
    u = usuario_con_perfil(s, "MODERADO")
    return s, u, s.pasarela.tokenizar(TARJETA)


# ============================================================= catálogo e idoneidad
def test_cp30_catalogo_banco_5_fideicomisos_y_cache_diaria():
    banco = cat.catalogo_banco()
    assert [f["id"] for f in banco["fideicomisos"]] == ["liq_usd", "rf_usd", "mix_bal", "acc_bvc", "crec_ves"]
    cache = cat.CatalogoCache()
    hoy = date(2026, 11, 27)
    cache.obtener(hoy)
    cache.obtener(hoy)
    assert cache.consultas_al_banco == 1                  # mismo día: no se vuelve a consultar al banco
    cache.obtener(hoy + timedelta(days=1))
    assert cache.consultas_al_banco == 2


@pytest.mark.parametrize("perfil,esperado", [
    ("CONSERVADOR", [("rf_usd", "RECOMENDADO"), ("liq_usd", "COMPATIBLE"), ("mix_bal", "POR_ENCIMA_DEL_PERFIL"),
                     ("acc_bvc", "POR_ENCIMA_DEL_PERFIL"), ("crec_ves", "POR_ENCIMA_DEL_PERFIL")]),
    ("MODERADO", [("mix_bal", "RECOMENDADO"), ("rf_usd", "COMPATIBLE"), ("liq_usd", "COMPATIBLE"),
                  ("acc_bvc", "POR_ENCIMA_DEL_PERFIL"), ("crec_ves", "POR_ENCIMA_DEL_PERFIL")]),
    ("AGRESIVO", [("acc_bvc", "RECOMENDADO"), ("crec_ves", "RECOMENDADO"), ("mix_bal", "COMPATIBLE"),
                  ("rf_usd", "COMPATIBLE"), ("liq_usd", "COMPATIBLE")]),
])
def test_cp31_regla_de_idoneidad_etiqueta_y_ordena(perfil, esperado):
    s = InvierteYa()
    u = usuario_con_perfil(s, perfil)
    r = s.listar_fideicomisos(u.id)
    assert r["riesgo_maximo_perfil"] == cat.RIESGO_MAXIMO_PERFIL[perfil]
    assert [(f["id"], f["etiqueta"]) for f in r["fideicomisos"]] == esperado
    assert all(f["requiere_confirmacion_riesgo"] == (f["etiqueta"] == "POR_ENCIMA_DEL_PERFIL")
               for f in r["fideicomisos"])
    assert "no garantizan" in r["nota_rendimiento"]


def test_cp32_filtro_por_riesgo_maximo(moderado):
    s, u, _ = moderado
    assert {f["riesgo"] for f in s.listar_fideicomisos(u.id, riesgo_max=2)["fideicomisos"]} == {1, 2}


# ============================================================= adhesión por fideicomiso
def test_cp33_por_encima_del_perfil_exige_confirmacion_expresa(moderado):
    s, u, _ = moderado
    with pytest.raises(ErrorNegocio) as e:
        s.firmar_adhesion(u.id, True, "acc_bvc")
    assert e.value.codigo == "CONFIRMACION_RIESGO_REQUERIDA"
    r = s.firmar_adhesion(u.id, True, "acc_bvc", confirmacion_riesgo_extra=True)
    assert r["etiqueta"] == "POR_ENCIMA_DEL_PERFIL" and r["confirmacion_riesgo_extra"] is True


def test_cp34_adhesion_guarda_sello_de_tiempo_y_hash_sha256_verificable(moderado):
    s, u, _ = moderado
    r = s.firmar_adhesion(u.id, True, "mix_bal")
    assert len(r["hash_adhesion"]) == 64 and r["algoritmo_hash"] == "SHA-256"
    assert datetime.fromisoformat(r["sello_tiempo"]).tzinfo is not None
    documento = {k: v for k, v in u.adhesiones["mix_bal"].items() if k != "hash_adhesion"}
    assert hash_documento(documento) == r["hash_adhesion"]          # integridad verificable
    documento["confirmacion_riesgo_extra"] = True                     # cualquier alteración cambia el hash
    assert hash_documento(documento) != r["hash_adhesion"]


def test_cp35_sin_fideicomiso_adhiere_al_recomendado_del_perfil(moderado):
    s, u, _ = moderado
    assert s.firmar_adhesion(u.id, True)["fideicomiso_id"] == "mix_bal"


def test_cp36_fideicomiso_inexistente(moderado):
    s, u, _ = moderado
    with pytest.raises(ErrorNegocio) as e:
        s.firmar_adhesion(u.id, True, "cripto_x")
    assert e.value.codigo == "FIDEICOMISO_NO_EXISTE"


# ============================================================= aporte repartido
def test_cp37_sin_adhesion_a_ese_fideicomiso_no_aporta(moderado):
    s, u, t = moderado
    s.firmar_adhesion(u.id, True, "rf_usd")
    with pytest.raises(ErrorNegocio) as e:
        s.crear_aporte(u.id, 10000, t, "k1", distribucion=[{"fideicomiso_id": "rf_usd", "porcentaje": 70},
                                                           {"fideicomiso_id": "mix_bal", "porcentaje": 30}])
    assert e.value.codigo == "ADHESION_PENDIENTE" and "Mixto Balanceado" in e.value.mensaje


@pytest.mark.parametrize("distribucion", [
    [{"fideicomiso_id": "rf_usd", "porcentaje": 70}, {"fideicomiso_id": "mix_bal", "porcentaje": 20}],
    [{"fideicomiso_id": "rf_usd", "porcentaje": 70}, {"fideicomiso_id": "mix_bal", "porcentaje": 40}],
    [{"fideicomiso_id": "rf_usd", "porcentaje": 50}, {"fideicomiso_id": "rf_usd", "porcentaje": 50}],
])
def test_cp38_distribucion_debe_sumar_100(moderado, distribucion):
    s, u, t = moderado
    s.firmar_adhesion(u.id, True, "rf_usd")
    s.firmar_adhesion(u.id, True, "mix_bal")
    with pytest.raises(ErrorNegocio) as e:
        s.crear_aporte(u.id, 10000, t, "k2", distribucion=distribucion)
    assert e.value.codigo == "DISTRIBUCION_INVALIDA"


def test_cp39_monto_minimo_por_fideicomiso(moderado):
    s, u, t = moderado
    s.firmar_adhesion(u.id, True, "rf_usd")
    s.firmar_adhesion(u.id, True, "mix_bal")
    with pytest.raises(ErrorNegocio) as e:      # $10 -> Mixto recibiría $3 (< $10)
        s.crear_aporte(u.id, 1000, t, "k3", distribucion=[{"fideicomiso_id": "rf_usd", "porcentaje": 70},
                                                          {"fideicomiso_id": "mix_bal", "porcentaje": 30}])
    assert e.value.codigo == "MONTO_MINIMO_FIDEICOMISO"


def test_cp40_aporte_repartido_con_tarjeta_cobra_1_mas_2_y_asigna_por_fideicomiso(moderado):
    s, u, t = moderado
    s.firmar_adhesion(u.id, True, "rf_usd")
    s.firmar_adhesion(u.id, True, "mix_bal")
    s.pasarela.forzar("APROBADA")
    a = s.crear_aporte(u.id, 10000, t, "k4", medio_pago="TARJETA",
                       distribucion=[{"fideicomiso_id": "rf_usd", "porcentaje": 70},
                                     {"fideicomiso_id": "mix_bal", "porcentaje": 30}])
    assert a["estado"] == "ASIGNADO"
    assert (a["comision_aporte_usd"], a["recargo_medio_pago_usd"], a["comision_total_usd"]) == ("1.00", "2.00", "3.00")
    assert a["monto_cobrado"] == "103.00"
    assert s.pasarela.autorizaciones[a["authorization_id"]].monto == 10300   # se cobra encima del aporte
    asig = {x["fideicomiso_id"]: x for x in a["asignaciones"]}
    assert asig["rf_usd"]["monto"] == "70.00" and asig["rf_usd"]["unidades"] == "56.0000"    # 70 / 1,25
    assert asig["mix_bal"]["monto"] == "30.00" and asig["mix_bal"]["unidades"] == "22.7272"  # 30 / 1,32
    assert a["unidades"] == "78.7272"


def test_cp41_pago_movil_sin_recargo(moderado):
    s, u, _ = moderado
    s.firmar_adhesion(u.id, True, "mix_bal")
    s.pasarela.forzar("APROBADA")
    a = s.crear_aporte(u.id, 10000, s.pasarela.tokenizar(PAGO_MOVIL), "k5", medio_pago="PAGO_MOVIL")
    assert a["recargo_medio_pago_pct"] == 0.0 and a["comision_total_usd"] == "1.00"
    assert a["monto_cobrado"] == "101.00"
    assert a["asignaciones"][0]["fideicomiso_id"] == "mix_bal"


def test_cp42_perfil_baja_y_fideicomiso_queda_por_encima_exige_reconfirmar(moderado):
    s, u, t = moderado
    s.firmar_adhesion(u.id, True, "mix_bal")
    u.perfil = "CONSERVADOR"                      # p. ej. tras la Tanda 2 o la revisión del asesor
    s.firmar_adhesion(u.id, True, "rf_usd")
    with pytest.raises(ErrorNegocio) as e:
        s.crear_aporte(u.id, 2000, t, "k6", distribucion=[{"fideicomiso_id": "mix_bal", "porcentaje": 100}])
    assert e.value.codigo == "CONFIRMACION_RIESGO_REQUERIDA"


def test_cp43_portafolio_consolidado_y_desglose(moderado):
    s, u, t = moderado
    s.firmar_adhesion(u.id, True, "rf_usd")
    s.firmar_adhesion(u.id, True, "mix_bal")
    s.pasarela.forzar("APROBADA", "APROBADA")
    s.crear_aporte(u.id, 10000, t, "p1", distribucion=[{"fideicomiso_id": "rf_usd", "porcentaje": 70},
                                                       {"fideicomiso_id": "mix_bal", "porcentaje": 30}])
    s.crear_aporte(u.id, 2000, t, "p2", distribucion=[{"fideicomiso_id": "mix_bal", "porcentaje": 100}])
    p = s.portafolio(u.id)
    por_fid = {f["fideicomiso_id"]: f for f in p["fideicomisos"]}
    assert set(por_fid) == {"rf_usd", "mix_bal"}
    assert por_fid["rf_usd"]["saldo"] == "70.00"
    assert por_fid["mix_bal"]["aportes"] == 2
    assert float(p["saldo"]) == pytest.approx(sum(float(f["saldo"]) for f in p["fideicomisos"]))
    assert sum(p["composicion"].values()) == 100
    assert p["aportes"] == 2


def test_cp44_cierre_concilia_por_fideicomiso_con_comisiones(moderado):
    s, u, t = moderado
    s.firmar_adhesion(u.id, True, "rf_usd")
    s.firmar_adhesion(u.id, True, "mix_bal")
    tok_pm = s.pasarela.tokenizar(PAGO_MOVIL)
    for i in range(4):
        s.pasarela.forzar("APROBADA")
        s.crear_aporte(u.id, 5000 + i * 700, t if i % 2 else tok_pm, f"c{i}",
                       medio_pago="TARJETA" if i % 2 else "PAGO_MOVIL",
                       distribucion=[{"fideicomiso_id": "rf_usd", "porcentaje": 60},
                                     {"fideicomiso_id": "mix_bal", "porcentaje": 40}])
    r = s.cerrar_dia(date.today())
    assert r["conciliado"] is True, r["excepciones"]
    assert set(r["niveles"][1]["por_fideicomiso"]) == {"rf_usd", "mix_bal"}
    assert {o["fideicomiso_id"] for o in r["propuesta_ordenes"]} == {"rf_usd", "mix_bal"}
    assert r["batch"]["aprobada"] is True
    assert r["ingresos_invierteya"]["recargo_medio_pago_centavos"] > 0
    # Al fideicomiso llega el 100% de lo invertido (sin comisiones)
    assert sum(s.fideicomiso.estado_posiciones().values()) == sum(r["aportes_por_fideicomiso"].values())


def test_cp45_cierre_detecta_descuadre_con_aporte_repartido(moderado):
    s, u, t = moderado
    s.firmar_adhesion(u.id, True, "rf_usd")
    s.firmar_adhesion(u.id, True, "mix_bal")
    for i in range(2):
        s.pasarela.forzar("APROBADA")
        s.crear_aporte(u.id, 5000, t, f"d{i}", distribucion=[{"fideicomiso_id": "rf_usd", "porcentaje": 50},
                                                             {"fideicomiso_id": "mix_bal", "porcentaje": 50}])
    r = s.cerrar_dia(date.today(), inyectar_descuadre=True)
    assert r["conciliado"] is False
    assert {"CAPTURADO_SIN_LIQUIDAR", "DIFERENCIA_LIQUIDACION"} <= {e["tipo"] for e in r["excepciones"]}


# ============================================================= cuestionario 2 tandas, revisión e IA
def test_cp46_tanda1_usa_edad_del_kyc_y_tanda2_recalcula():
    s = InvierteYa()
    u = s.registrar("Luis (sintético)", "luis@example.com")
    s.aprobar_kyc(u.id, edad=52)
    r1 = s.evaluar_perfil_s3(u.id, {"tanda": 1, **MODERADO_S3})
    assert r1["tanda_completada"] == 1 and "dependientes" in r1["campos_omitidos"]
    assert r1["aviso_transparencia"] and r1["fideicomiso_recomendado"] in cat.IDS
    assert "edad" not in MODERADO_S3                                   # la edad no se preguntó
    r2 = s.completar_tanda2(u.id, dependientes=0, quiz_aciertos=2)
    assert r2["tanda_completada"] == 2 and r2["campos_omitidos"] == []


def test_cp47_prefiero_no_decirlo_nunca_agresivo_y_revision_humana():
    s = InvierteYa()
    u = s.registrar("Eva (sintética)", "eva@example.com")
    s.aprobar_kyc(u.id, edad=22)
    r = s.evaluar_perfil_s3(u.id, dict(ahorro_mensual_rango=4, horizonte_anios=7.0, objetivo="ganar_rapido",
                                       reaccion_caida_20="comprar_mas", emergencia_200=None,
                                       experiencia_tipo="acciones", dependientes=0, quiz_aciertos=2))
    assert r["perfil"] != "AGRESIVO" and "emergencia_200" in r["campos_omitidos"]
    rev = s.solicitar_revision(u.id, "Creo que soy más conservadora")
    assert rev["estado"] == "PENDIENTE_ASESOR" and rev["revision_id"].startswith("rev_")
    assert any(x["origen"] == "DESACUERDO_USUARIO" for x in s.revisiones_perfil)


def test_cp48_riesgo_abandono_solo_sugiere_y_respeta_consentimiento(moderado):
    s, u, _ = moderado
    r = s.riesgo_abandono(u.id, simular_inactivo=True)
    assert r["en_riesgo"] is True and r["sugerencia_suave"]
    assert r["accion_permitida"] == "SOLO_SUGERIR_RECORDATORIO"
    s.actualizar_consentimiento(u.id, alertas_ahorro=False)
    r2 = s.riesgo_abandono(u.id, simular_inactivo=True)
    assert r2["sugerencia_suave"] is None and r2["consentimiento_alertas"] is False


def test_cp49_pronostico_flujos_por_fideicomiso():
    r = InvierteYa().pronostico_flujos()
    assert {f["fideicomiso_id"] for f in r["por_fideicomiso"]} == set(cat.IDS)
    assert r["modelo_elegido"] and r["total_7d_usd"] == pytest.approx(
        sum(f["flujo_neto_7d_usd"] for f in r["por_fideicomiso"]), abs=0.05)


# ============================================================= cifrado, KMS, Plata/Oro, habeas data
def test_cp50_aes256gcm_cifra_descifra_y_detecta_alteraciones():
    c = CifradorCampos(KMSSimulado())
    sobre = c.cifrar({"email": "ana@example.com"}, "usuario:usr_1:pii")
    assert "ana@example.com" not in json.dumps(sobre)
    assert sobre["alg"] == "AES-256-GCM"
    assert c.descifrar(sobre) == {"email": "ana@example.com"}
    with pytest.raises(ErrorCifrado):                                  # copiado a otro usuario (AAD)
        c.descifrar({**sobre, "contexto": "usuario:usr_2:pii"})
    alterado = dict(sobre)
    ct = bytearray(__import__("base64").b64decode(sobre["ct"]))
    ct[0] ^= 1
    alterado["ct"] = __import__("base64").b64encode(bytes(ct)).decode()
    with pytest.raises(ErrorCifrado):
        c.descifrar(alterado)


def test_cp51_rotacion_kms_reenvuelve_sin_recifrar_datos():
    kms = KMSSimulado()
    c = CifradorCampos(kms)
    sobre = c.cifrar("dato sensible", "ctx")
    assert kms.rotar() == 2
    assert c.descifrar(sobre) == "dato sensible"                       # la v1 sigue sirviendo para leer
    nuevo = c.reenvolver(sobre)
    assert nuevo["dek_envuelta"]["version_kek"] == 2 and nuevo["ct"] == sobre["ct"]
    kms.destruir(1)
    assert c.descifrar(nuevo) == "dato sensible"
    with pytest.raises(ErrorCifrado):                                  # destrucción criptográfica
        c.descifrar(sobre)


def test_cp52_pii_cifrada_en_reposo_y_rotacion_desde_el_servicio(moderado):
    s, u, _ = moderado
    assert "ana@example.com" not in json.dumps(u.pii)
    r = s.rotar_llaves()
    assert r["version_activa"] == 2 and r["registros_reenvueltos"] >= 2
    assert s.datos_personales(u.id)["datos_identificacion"]["email"] == "ana@example.com"


def test_cp53_plata_seudonimiza_y_oro_suprime_celdas_con_menos_de_10():
    kms = KMSSimulado()
    bronce = ([{"usuario_id": f"u{i}", "nombre": "x", "email": "x@x", "edad": 30, "perfil": "MODERADO",
                "monto_usd": 10.0} for i in range(12)]
              + [{"usuario_id": f"v{i}", "nombre": "y", "email": "y@y", "edad": 50, "perfil": "AGRESIVO",
                  "monto_usd": 50.0} for i in range(3)])
    plata = a_capa_plata(bronce, kms)
    assert not {"usuario_id", "nombre", "email", "edad"} & set(plata[0])
    assert plata[0]["seudonimo"] == kms.seudonimo("u0") and plata[0]["rango_edad"] == "25-34"
    oro = agregar_capa_oro(plata, ["perfil"], "monto_usd")
    celdas = {c["perfil"]: c for c in oro["celdas"]}
    assert celdas["MODERADO"]["personas"] == 12 and celdas["MODERADO"]["total"] == 120.0
    assert celdas["AGRESIVO"]["suprimida"] is True and celdas["AGRESIVO"]["total"] is None
    assert oro["k_minimo"] == 10


def test_cp54_informe_agregado_solo_con_consentimiento_y_k10():
    s = InvierteYa()
    for i in range(11):
        u = usuario_con_perfil(s, "MODERADO")
        s.firmar_adhesion(u.id, True, "mix_bal")
        if i < 10:
            s.actualizar_consentimiento(u.id, informes_agregados=True)
        s.pasarela.forzar("APROBADA")
        s.crear_aporte(u.id, 2000, s.pasarela.tokenizar(TARJETA), f"oro{i}")
    oro = s.informe_agregado()
    assert oro["personas_que_consintieron"] == 10
    celda = next(c for c in oro["celdas"] if c["fideicomiso_id"] == "mix_bal")
    assert celda["personas"] == 10 and celda["total"] == 200.0          # el que no consintió no cuenta
    s.actualizar_consentimiento(next(iter(s.usuarios)), informes_agregados=False)
    assert s.informe_agregado()["celdas"][0]["suprimida"] is True       # baja a 9 < k


def test_cp55_habeas_data_acceso_y_supresion(moderado):
    s, u, t = moderado
    s.firmar_adhesion(u.id, True, "mix_bal")
    s.pasarela.forzar("APROBADA")
    s.crear_aporte(u.id, 2000, t, "h1")
    d = s.datos_personales(u.id)
    assert d["datos_identificacion"]["email"] == "ana@example.com"
    assert d["respuestas_cuestionario"] is not None and d["adhesiones"][0]["hash_adhesion"]
    r = s.suprimir_datos(u.id)
    assert r["estado"] == "DATOS_DE_USO_SUPRIMIDOS"
    d2 = s.datos_personales(u.id)
    assert d2["datos_identificacion"]["email"] is None and d2["respuestas_cuestionario"] is None
    assert d2["aportes"]["asignados"] == 1                              # registro contable conservado
    with pytest.raises(ErrorNegocio) as e:
        s.crear_aporte(u.id, 2000, t, "h2")
    assert e.value.codigo == "USUARIO_SUPRIMIDO"


# ============================================================= API HTTP de punta a punta (sin httpx)
async def _asgi(app, metodo, ruta, cuerpo=None, cabeceras=None):
    ruta, _, query = ruta.partition("?")
    body = json.dumps(cuerpo).encode() if cuerpo is not None else b""
    headers = [(k.lower().encode(), v.encode()) for k, v in (cabeceras or {}).items()]
    if cuerpo is not None:
        headers += [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": metodo,
             "scheme": "http", "path": ruta, "raw_path": ruta.encode(), "query_string": query.encode(),
             "headers": headers, "client": ("127.0.0.1", 5000), "server": ("testserver", 80)}
    enviado, fin, estado, resp_h, partes = False, asyncio.Event(), 500, {}, []

    async def receive():
        nonlocal enviado
        if not enviado:
            enviado = True
            return {"type": "http.request", "body": body, "more_body": False}
        await fin.wait()
        return {"type": "http.disconnect"}

    async def send(m):
        nonlocal estado
        if m["type"] == "http.response.start":
            estado = m["status"]
            resp_h.update({k.decode().lower(): v.decode() for k, v in m.get("headers", [])})
        elif m["type"] == "http.response.body":
            partes.append(m.get("body", b""))
            if not m.get("more_body", False):
                fin.set()

    await app(scope, receive, send)
    datos = b"".join(partes)
    return estado, resp_h, (json.loads(datos) if datos else None)


def test_cp56_api_flujo_s3_completo_con_auditoria_y_cabeceras():
    import app.main as m
    m.servicio = InvierteYa()
    m.bitacora.reiniciar()
    auth = {"Authorization": "Bearer demo-token"}

    def llamar(metodo, ruta, cuerpo=None, extra=None):
        return asyncio.run(_asgi(m.app, metodo, ruta, cuerpo, {**auth, **(extra or {})}))

    est, _, banco = llamar("GET", "/fiduciario/v1/fideicomisos")
    assert est == 200 and len(banco["fideicomisos"]) == 5
    _, _, u = llamar("POST", "/v1/usuarios", {"nombre": "María (sintética)", "email": "maria@example.com"})
    uid = u["usuario_id"]
    assert llamar("POST", f"/v1/usuarios/{uid}/kyc", {"edad": 24})[2]["edad_kyc"] == 24
    est, _, p = llamar("POST", f"/v1/usuarios/{uid}/perfil", {"tanda": 1, **MODERADO_S3})
    assert est == 200 and p["tanda_completada"] == 1
    perfil = p["perfil"]
    est, _, catalogo = llamar("GET", f"/v1/fideicomisos?usuario_id={uid}")
    assert est == 200 and catalogo["perfil_usuario"] == perfil
    assert catalogo["fideicomisos"][0]["etiqueta"] == "RECOMENDADO"
    encima = next((f["id"] for f in catalogo["fideicomisos"] if f["requiere_confirmacion_riesgo"]), None)
    if encima:
        est, _, err = llamar("POST", f"/v1/usuarios/{uid}/adhesion", {"acepta": True, "fideicomiso_id": encima})
        assert est == 422 and err["codigo"] == "CONFIRMACION_RIESGO_REQUERIDA"
    reco = catalogo["fideicomisos"][0]["id"]
    est, _, adh = llamar("POST", f"/v1/usuarios/{uid}/adhesion", {"acepta": True, "fideicomiso_id": reco})
    assert est == 200 and len(adh["hash_adhesion"]) == 64
    llamar("POST", f"/v1/usuarios/{uid}/adhesion", {"acepta": True, "fideicomiso_id": "liq_usd"})
    _, _, tok = llamar("POST", "/pasarela/v1/tokens", {"pan": TARJETA})
    llamar("POST", "/v1/demo/forzar-escenario?escenarios=APROBADA&reemplazar=true")
    est, _, a = llamar("POST", "/v1/aportes",
                       {"usuario_id": uid, "monto": 50, "token_tarjeta": tok["token"], "medio_pago": "TARJETA",
                        "distribucion": [{"fideicomiso_id": reco, "porcentaje": 60},
                                         {"fideicomiso_id": "liq_usd", "porcentaje": 40}]},
                       {"Idempotency-Key": "api-1"})
    assert est == 201 and a["estado"] == "ASIGNADO" and len(a["asignaciones"]) == 2
    assert a["comision_total_usd"] == "1.50"
    est, _, port = llamar("GET", f"/v1/usuarios/{uid}/portafolio")
    assert est == 200 and len(port["fideicomisos"]) == 2
    est, _, _ = llamar("PATCH", f"/v1/usuarios/{uid}/perfil/tanda2", {"dependientes": 1, "quiz_aciertos": 1})
    assert est == 200
    assert llamar("POST", f"/v1/usuarios/{uid}/perfil/revision", {"motivo": "No estoy de acuerdo"})[0] == 201
    assert llamar("GET", f"/v1/usuarios/{uid}/riesgo-abandono?simular_inactivo=true")[2]["en_riesgo"] is True
    assert llamar("PUT", f"/v1/usuarios/{uid}/consentimiento", {"informes_agregados": True})[0] == 200
    est, h, datos = llamar("GET", f"/v1/usuarios/{uid}/datos-personales")
    assert est == 200 and datos["consentimientos"]["informes_agregados"] is True
    assert h["x-content-type-options"] == "nosniff" and "content-security-policy" in h
    est, _, aud = llamar("GET", f"/v1/operaciones/auditoria?usuario_id={uid}")
    operaciones = [r["operacion"] for r in aud["registros"]]
    assert aud["integra"] is True
    assert "ADHESION_FIDEICOMISO:OK" in operaciones and "APORTE:OK" in operaciones
    assert "ADHESION_FIDEICOMISO:HTTP_422" in operaciones or not encima
    # Retrocompatibilidad S2: cuestionario de 10 variables y adhesión sin fideicomiso
    _, _, u2 = llamar("POST", "/v1/usuarios", {"nombre": "Pedro", "email": "pedro@example.com"})
    llamar("POST", f"/v1/usuarios/{u2['usuario_id']}/kyc")
    est, _, p2 = llamar("POST", f"/v1/usuarios/{u2['usuario_id']}/perfil",
                        dict(edad=24, ingreso_rango=2, pct_invertible=15, horizonte_anios=2, objetivo="proteger",
                             reaccion_caida_20="vender_todo", experiencia_previa=False, fondo_emergencia=False,
                             dependientes=0, conocimiento=2))
    assert est == 200 and p2["perfil"] == "CONSERVADOR"
    est, _, adh2 = llamar("POST", f"/v1/usuarios/{u2['usuario_id']}/adhesion", {"acepta": True})
    assert est == 200 and adh2["fideicomiso_id"] == "rf_usd"
    assert llamar("GET", "/v1/fiduciario/pronostico-flujos")[0] == 200
    assert llamar("GET", "/v1/fiduciario/informe-agregado")[0] == 200
    assert llamar("DELETE", f"/v1/usuarios/{uid}/datos-personales")[0] == 200
