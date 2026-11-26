"""Pruebas unitarias y de integración para auditoría inmutable y hardening HTTP (Track 4)."""
import json
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.auditoria import (
    HASH_GENESIS,
    BitacoraAuditoria,
    configurar_seguridad,
)


def test_bitacora_encadenamiento_e_integridad():
    bitacora = BitacoraAuditoria()
    r1 = bitacora.registrar(
        usuario_id="usr_001",
        ip="192.168.1.10",
        operacion="APORTE:OK",
        origen="usuario_app",
        destino="pasarela_y_fideicomiso",
    )
    r2 = bitacora.registrar(
        usuario_id="usr_001",
        ip="192.168.1.10",
        operacion="ADHESION_FIDEICOMISO:OK",
        origen="usuario_app",
        destino="fideicomiso_bancario",
    )

    assert r1.hash_previo == HASH_GENESIS
    assert r2.hash_previo == r1.hash_actual
    assert r1.hash_actual != r2.hash_actual
    assert bitacora.verificar_integridad() is True


def test_bitacora_detecta_alteracion_de_registro():
    bitacora = BitacoraAuditoria()
    bitacora.registrar(
        usuario_id="usr_001",
        ip="10.0.0.5",
        operacion="APORTE:OK",
        origen="usuario_app",
        destino="pasarela_y_fideicomiso",
    )
    bitacora.registrar(
        usuario_id="usr_002",
        ip="10.0.0.6",
        operacion="EVALUACION_PERFIL:OK",
        origen="usuario_app",
        destino="motor_ia_perfil",
    )

    # Simula manipulación directa del primer registro en memoria
    bitacora._registros[0] = replace(bitacora._registros[0], ip="10.0.0.99")
    assert bitacora.verificar_integridad() is False


def test_bitacora_persistencia_jsonl_y_filtros(tmp_path):
    archivo = tmp_path / "auditoria.jsonl"
    bitacora = BitacoraAuditoria(ruta_archivo=archivo)
    bitacora.registrar(
        usuario_id="usr_a",
        ip="127.0.0.1",
        operacion="APORTE:OK",
        origen="usuario_app",
        destino="pasarela_y_fideicomiso",
    )
    bitacora.registrar(
        usuario_id="usr_b",
        ip="127.0.0.2",
        operacion="ADHESION_FIDEICOMISO:OK",
        origen="usuario_app",
        destino="fideicomiso_bancario",
    )

    recargada = BitacoraAuditoria(ruta_archivo=archivo)
    assert recargada.verificar_integridad() is True
    assert len(recargada.listar()) == 2
    assert len(recargada.listar(usuario_id="usr_a")) == 1
    assert recargada.listar(operacion="ADHESION_FIDEICOMISO:OK")[0]["usuario_id"] == "usr_b"

    lineas = archivo.read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 2
    assert set(json.loads(lineas[0]).keys()) == {
        "timestamp",
        "usuario_id",
        "ip",
        "operacion",
        "origen",
        "destino",
        "hash_previo",
        "hash_actual",
    }


def _crear_app_prueba() -> tuple[FastAPI, BitacoraAuditoria]:
    app = FastAPI()
    bitacora = configurar_seguridad(
        app,
        origenes_cors=["https://app.invierteya.local"],
    )

    @app.get("/salud")
    def salud():
        return {"ok": True}

    @app.post("/v1/aportes", status_code=201)
    def aportar(payload: dict):
        return {"recibido": payload}

    @app.post("/v1/usuarios/{usuario_id}/adhesion")
    def adherir(usuario_id: str):
        return {"usuario_id": usuario_id, "adhesion": True}

    return app, bitacora


def test_middleware_cabeceras_cors_y_auditoria():
    app, bitacora = _crear_app_prueba()
    client = TestClient(app)

    res_salud = client.get("/salud", headers={"Origin": "https://app.invierteya.local"})
    assert res_salud.status_code == 200
    assert res_salud.headers["X-Content-Type-Options"] == "nosniff"
    assert res_salud.headers["X-Frame-Options"] == "DENY"
    assert res_salud.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Strict-Transport-Security" in res_salud.headers
    assert "default-src 'self'" in res_salud.headers["Content-Security-Policy"]
    assert res_salud.headers.get("access-control-allow-origin") == "https://app.invierteya.local"

    res_cors_bloqueado = client.get("/salud", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in res_cors_bloqueado.headers

    res_aporte = client.post(
        "/v1/aportes",
        json={"usuario_id": "usr_demo", "monto": 50},
        headers={"X-Forwarded-For": "203.0.113.42"},
    )
    assert res_aporte.status_code == 201

    res_adhesion = client.post("/v1/usuarios/usr_demo/adhesion")
    assert res_adhesion.status_code == 200

    registros = bitacora.listar()
    assert len(registros) == 2
    assert registros[0]["usuario_id"] == "usr_demo"
    assert registros[0]["ip"] == "203.0.113.42"
    assert registros[0]["operacion"] == "APORTE:OK"
    assert registros[1]["operacion"] == "ADHESION_FIDEICOMISO:OK"
    assert bitacora.verificar_integridad() is True
