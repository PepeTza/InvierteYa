"""Pruebas unitarias y de integración para auditoría inmutable y hardening HTTP (Track 4)."""
import asyncio
import json
from dataclasses import replace

from fastapi import FastAPI

from app.core.auditoria import (
    HASH_GENESIS,
    BitacoraAuditoria,
    configurar_seguridad,
)


async def _ejecutar_asgi(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Invoca una app ASGI 3.0 usando solo stdlib sin depender de httpx."""
    body_bytes = (
        json.dumps(json_body).encode("utf-8") if json_body is not None else b""
    )
    raw_headers: list[tuple[bytes, bytes]] = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    if json_body is not None:
        raw_headers.append((b"content-type", b"application/json"))
        raw_headers.append((b"content-length", str(len(body_bytes)).encode("latin-1")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    enviado_body = False
    terminado = asyncio.Event()
    status_code = 500
    resp_headers: dict[str, str] = {}
    chunks: list[bytes] = []

    async def receive():
        nonlocal enviado_body
        if not enviado_body:
            enviado_body = True
            return {"type": "http.request", "body": body_bytes, "more_body": False}
        await terminado.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
            resp_headers.update(
                {
                    k.decode("latin-1").lower(): v.decode("latin-1")
                    for k, v in message.get("headers", [])
                }
            )
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))
            if not message.get("more_body", False):
                terminado.set()

    await app(scope, receive, send)
    return status_code, resp_headers, b"".join(chunks)


def _llamar_asgi(
    app: FastAPI,
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    return asyncio.run(
        _ejecutar_asgi(app, method, path, json_body=json_body, headers=headers)
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

    status_salud, hdrs_salud, _ = _llamar_asgi(
        app,
        "GET",
        "/salud",
        headers={"Origin": "https://app.invierteya.local"},
    )
    assert status_salud == 200
    assert hdrs_salud["x-content-type-options"] == "nosniff"
    assert hdrs_salud["x-frame-options"] == "DENY"
    assert hdrs_salud["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "strict-transport-security" in hdrs_salud
    assert "default-src 'self'" in hdrs_salud["content-security-policy"]
    assert hdrs_salud.get("access-control-allow-origin") == "https://app.invierteya.local"

    _, hdrs_cors_bloqueado, _ = _llamar_asgi(
        app,
        "GET",
        "/salud",
        headers={"Origin": "https://evil.example"},
    )
    assert "access-control-allow-origin" not in hdrs_cors_bloqueado

    status_aporte, _, _ = _llamar_asgi(
        app,
        "POST",
        "/v1/aportes",
        json_body={"usuario_id": "usr_demo", "monto": 50},
        headers={"X-Forwarded-For": "203.0.113.42"},
    )
    assert status_aporte == 201

    status_adhesion, _, _ = _llamar_asgi(
        app,
        "POST",
        "/v1/usuarios/usr_demo/adhesion",
    )
    assert status_adhesion == 200

    registros = bitacora.listar()
    assert len(registros) == 2
    assert registros[0]["usuario_id"] == "usr_demo"
    assert registros[0]["ip"] == "203.0.113.42"
    assert registros[0]["operacion"] == "APORTE:OK"
    assert registros[1]["operacion"] == "ADHESION_FIDEICOMISO:OK"
    assert bitacora.verificar_integridad() is True
