"""Genera docs/openapi.yaml (OpenAPI 3.1) sin necesidad de levantar el servidor.

Los esquemas salen de los mismos modelos Pydantic que usa FastAPI, así que el archivo
coincide con lo que FastAPI publica en /openapi.json. Si tienen FastAPI instalado,
también pueden exportar la versión oficial con:
    python -c "import json,app.main as m; print(json.dumps(m.app.openapi(), indent=2))" > docs/openapi.json
"""
import sys
from pathlib import Path

import yaml
from pydantic.json_schema import models_json_schema

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from app.api import esquemas as E  # noqa: E402

MODELOS = [E.RegistroIn, E.UsuarioOut, E.AdhesionIn, E.CuestionarioIn, E.Leccion, E.PerfilOut,
           E.AporteIn, E.AporteOut, E.PortafolioOut, E.Error, E.TokenIn, E.TokenOut,
           E.AutorizacionIn, E.CapturaIn, E.ReversoIn, E.DevolucionIn, E.RespuestaPasarela]

_, defs = models_json_schema([(m, "validation") for m in MODELOS],
                             ref_template="#/components/schemas/{model}")
schemas = defs["$defs"]


def ref(nombre):
    return {"$ref": f"#/components/schemas/{nombre}"}


def cuerpo(nombre):
    return {"required": True, "content": {"application/json": {"schema": ref(nombre)}}}


def resp(nombre, desc="OK"):
    return {"description": desc, "content": {"application/json": {"schema": ref(nombre)}}}


ERR = {"404": resp("Error", "No encontrado"), "422": resp("Error", "Regla de negocio no cumplida")}
SEG = [{"bearerAuth": []}]
P_USUARIO = {"name": "usuario_id", "in": "path", "required": True, "schema": {"type": "string"}}

paths = {
    "/v1/usuarios": {"post": {"tags": ["Usuarios"], "summary": "Registrar usuario (datos sintéticos)",
                              "security": SEG, "requestBody": cuerpo("RegistroIn"),
                              "responses": {"201": resp("UsuarioOut", "Creado")}}},
    "/v1/usuarios/{usuario_id}/kyc": {"post": {
        "tags": ["Usuarios"], "summary": "KYC simulado (se comparte con el banco fiduciario)",
        "security": SEG, "parameters": [P_USUARIO],
        "responses": {"200": {"description": "KYC aprobado"}, **ERR}}},
    "/v1/usuarios/{usuario_id}/adhesion": {"post": {
        "tags": ["Usuarios"], "summary": "Firmar contrato de adhesión al fideicomiso",
        "security": SEG, "parameters": [P_USUARIO], "requestBody": cuerpo("AdhesionIn"),
        "responses": {"200": {"description": "Adhesión firmada"}, **ERR}}},
    "/v1/usuarios/{usuario_id}/perfil": {"post": {
        "tags": ["Perfil y tutor"], "summary": "Cuestionario de 10 preguntas -> perfil + explicación + lección",
        "security": SEG, "parameters": [P_USUARIO], "requestBody": cuerpo("CuestionarioIn"),
        "responses": {"200": resp("PerfilOut"), **ERR}}},
    "/v1/lecciones": {"get": {
        "tags": ["Perfil y tutor"], "summary": "Tutor predefinido: lección por paso, perfil y nivel",
        "security": SEG,
        "parameters": [
            {"name": "paso", "in": "query", "required": True, "schema": {"type": "string", "enum": [
                "CUESTIONARIO_COMPLETO", "ANTES_PRIMER_APORTE", "UNIDADES_ASIGNADAS",
                "VER_PORTAFOLIO", "ANTES_RESCATE"]}},
            {"name": "perfil", "in": "query", "schema": {"type": "string",
                                                          "enum": ["CONSERVADOR", "MODERADO", "AGRESIVO"]}},
            {"name": "conocimiento", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 5}}],
        "responses": {"200": resp("Leccion")}}},
    "/v1/aportes": {"post": {
        "tags": ["Aportes"],
        "summary": "Crear aporte: autorización -> captura -> asignación de unidades (reverso si falla)",
        "description": "Si se repite la misma Idempotency-Key se devuelve el resultado original "
                       "(`duplicado: true`) y no se cobra dos veces.",
        "security": SEG,
        "parameters": [{"name": "Idempotency-Key", "in": "header", "required": True,
                        "schema": {"type": "string"}}],
        "requestBody": cuerpo("AporteIn"),
        "responses": {"201": resp("AporteOut", "Aporte procesado (ver campo estado)"), **ERR}}},
    "/v1/aportes/{aporte_id}": {"get": {
        "tags": ["Aportes"], "summary": "Consultar un aporte", "security": SEG,
        "parameters": [{"name": "aporte_id", "in": "path", "required": True, "schema": {"type": "string"}}],
        "responses": {"200": resp("AporteOut"), "404": resp("Error", "No encontrado")}}},
    "/v1/usuarios/{usuario_id}/portafolio": {"get": {
        "tags": ["Aportes"], "summary": "Unidades, valor de la unidad y saldo", "security": SEG,
        "parameters": [P_USUARIO], "responses": {"200": resp("PortafolioOut"), **ERR}}},
    "/v1/operaciones/cierre": {"post": {
        "tags": ["Operaciones"],
        "summary": "Job T+1: liquidación, conciliación en 3 niveles y propuesta de órdenes por lote",
        "security": SEG,
        "parameters": [{"name": "fecha", "in": "query", "schema": {"type": "string", "format": "date"}},
                       {"name": "inyectar_descuadre", "in": "query", "schema": {"type": "boolean"}}],
        "responses": {"200": {"description": "Resultado de la conciliación y del batch"}}}},
    "/pasarela/v1/tokens": {"post": {
        "tags": ["Pasarela simulada"], "summary": "Tokenizar tarjeta de PRUEBA (el PAN no llega a InvierteYa)",
        "requestBody": cuerpo("TokenIn"), "responses": {"201": resp("TokenOut", "Token creado")}}},
    "/pasarela/v1/authorizations": {"post": {
        "tags": ["Pasarela simulada"], "summary": "Autorización (ISO 8583 0100/0110)",
        "requestBody": cuerpo("AutorizacionIn"), "responses": {"200": resp("RespuestaPasarela")}}},
    "/pasarela/v1/captures": {"post": {
        "tags": ["Pasarela simulada"], "summary": "Captura (ISO 8583 0220/0230)",
        "requestBody": cuerpo("CapturaIn"), "responses": {"200": resp("RespuestaPasarela")}}},
    "/pasarela/v1/reversals": {"post": {
        "tags": ["Pasarela simulada"], "summary": "Reverso (ISO 8583 0400/0410, 0421 si no hay respuesta)",
        "requestBody": cuerpo("ReversoIn"), "responses": {"200": resp("RespuestaPasarela")}}},
    "/pasarela/v1/refunds": {"post": {
        "tags": ["Pasarela simulada"], "summary": "Devolución de un cobro capturado",
        "requestBody": cuerpo("DevolucionIn"), "responses": {"200": resp("RespuestaPasarela")}}},
    "/pasarela/v1/settlements/{fecha}": {"get": {
        "tags": ["Pasarela simulada"], "summary": "Archivo de liquidación diario",
        "parameters": [{"name": "fecha", "in": "path", "required": True,
                        "schema": {"type": "string", "format": "date"}}],
        "responses": {"200": {"description": "Transacciones, comisiones y totales"}}}},
}

doc = {
    "openapi": "3.1.0",
    "info": {"title": "InvierteYa API (prototipo · Sesión 2)", "version": "0.2.0",
             "description": "Inversión fraccionada desde $5 a través de un fideicomiso. "
                            "Pasarela, adquirente, suiche, emisor, banco fiduciario, casa de bolsa y CVV "
                            "están SIMULADOS. Solo datos sintéticos."},
    "servers": [{"url": "http://127.0.0.1:8000", "description": "Local"}],
    "tags": [{"name": t} for t in ["Usuarios", "Perfil y tutor", "Aportes", "Operaciones", "Pasarela simulada"]],
    "paths": paths,
    "components": {"schemas": schemas, "securitySchemes": {
        "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT",
                       "description": "Simulado: usar `demo-token`. En producción, OAuth2/JWT en el API Gateway."}}},
}

salida = RAIZ / "docs" / "openapi.yaml"
class _SinAlias(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


salida.write_text(yaml.dump(doc, Dumper=_SinAlias, allow_unicode=True, sort_keys=False), encoding="utf-8")
print(f"Generado {salida} con {len(paths)} rutas y {len(schemas)} esquemas")
