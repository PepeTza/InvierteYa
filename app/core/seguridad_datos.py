"""Protección de datos sensibles · Sesión 3 (criterio "Cifrado y protección de datos").

Implementa en código lo que describe `docs/seguridad/CIFRADO_Y_DATOS.md`:

1. **Cifrado en reposo AES-256-GCM** con *cifrado por sobre* (envelope encryption), el mismo
   patrón que usan AWS KMS / Google Cloud KMS / HashiCorp Vault:
     - cada registro se cifra con una llave de datos (DEK) aleatoria de 256 bits;
     - la DEK se guarda envuelta (cifrada) con la llave maestra (KEK) que custodia el KMS;
     - el contexto (p. ej. `usuario:usr_1:campo:email`) va como dato asociado (AAD): un texto
       cifrado copiado a otro usuario o campo no se puede descifrar.
2. **KMS SIMULADO con rotación de llaves**: `rotar()` crea una nueva versión de KEK; las
   versiones anteriores quedan solo para descifrar y `reenvolver()` migra las DEK a la versión
   activa sin volver a cifrar los datos.
3. **Capa Plata (seudonimización)**: el identificador del usuario se reemplaza por un token
   HMAC-SHA256 con una llave secreta separada (no reversible sin el KMS); se eliminan los
   identificadores directos y se generalizan los cuasi-identificadores (edad -> rango).
4. **Capa Oro (agregación con k-anonimato)**: solo se publican celdas con k >= 10 personas
   distintas; las celdas con menos se suprimen. InvierteYa nunca vende datos individuales.

En producción las llaves maestras viven en un HSM/KMS administrado; aquí la llave maestra se
toma de la variable de entorno `INVIERTEYA_KMS_LLAVE_MAESTRA` (base64, 32 bytes) o se genera al
iniciar el proceso (solo para la demo: los datos no sobreviven a un reinicio).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ALGORITMO = "AES-256-GCM"
BYTES_LLAVE = 32          # 256 bits
BYTES_NONCE = 12          # 96 bits, recomendado por NIST SP 800-38D para GCM
K_MINIMO = 10             # k-anonimato de la capa Oro
VARIABLE_LLAVE_MAESTRA = "INVIERTEYA_KMS_LLAVE_MAESTRA"


class ErrorCifrado(Exception):
    """El texto cifrado fue alterado, el contexto no coincide o la llave fue destruida."""


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


def _desde_b64(texto: str) -> bytes:
    return base64.b64decode(texto.encode("ascii"))


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# =============================================================================== KMS simulado
@dataclass
class VersionLlave:
    version: int
    material: bytes = field(repr=False)
    creada_en: str
    estado: str = "ACTIVA"          # ACTIVA | SOLO_DESCIFRADO | DESTRUIDA


class KMSSimulado:
    """Servicio de gestión de llaves SIMULADO: custodia las KEK, las rota y envuelve DEK."""

    def __init__(self, llave_maestra: bytes | None = None, llave_seudonimos: bytes | None = None):
        if llave_maestra is None:
            crudo = os.getenv(VARIABLE_LLAVE_MAESTRA)
            llave_maestra = _desde_b64(crudo) if crudo else secrets.token_bytes(BYTES_LLAVE)
        if len(llave_maestra) != BYTES_LLAVE:
            raise ValueError("La llave maestra debe tener 32 bytes (AES-256).")
        self._versiones: dict[int, VersionLlave] = {1: VersionLlave(1, llave_maestra, _ahora())}
        self._activa = 1
        # La llave de seudónimos es independiente: rotar la KEK no cambia los tokens de la capa Plata.
        self._llave_seudonimos = llave_seudonimos or hashlib.sha256(b"seudonimos|" + llave_maestra).digest()
        self.historial: list[dict] = [{"evento": "CREADA", "version": 1, "fecha": _ahora()}]

    @property
    def version_activa(self) -> int:
        return self._activa

    def rotar(self) -> int:
        """Crea una nueva KEK activa; la anterior queda solo para descifrar."""
        self._versiones[self._activa].estado = "SOLO_DESCIFRADO"
        nueva = max(self._versiones) + 1
        self._versiones[nueva] = VersionLlave(nueva, secrets.token_bytes(BYTES_LLAVE), _ahora())
        self._activa = nueva
        self.historial.append({"evento": "ROTADA", "version": nueva, "fecha": _ahora()})
        return nueva

    def destruir(self, version: int):
        """Destrucción criptográfica: lo cifrado con esa versión queda ilegible para siempre."""
        if version == self._activa:
            raise ValueError("No se puede destruir la versión activa; rote primero.")
        v = self._versiones[version]
        v.material, v.estado = b"", "DESTRUIDA"
        self.historial.append({"evento": "DESTRUIDA", "version": version, "fecha": _ahora()})

    def _llave(self, version: int) -> bytes:
        v = self._versiones.get(version)
        if v is None or v.estado == "DESTRUIDA":
            raise ErrorCifrado(f"La versión de llave {version} no existe o fue destruida.")
        return v.material

    def envolver(self, dek: bytes, contexto: str) -> dict:
        nonce = secrets.token_bytes(BYTES_NONCE)
        cifrada = AESGCM(self._llave(self._activa)).encrypt(nonce, dek, contexto.encode("utf-8"))
        return {"version_kek": self._activa, "nonce": _b64(nonce), "dek": _b64(cifrada)}

    def desenvolver(self, envuelta: dict, contexto: str) -> bytes:
        try:
            return AESGCM(self._llave(envuelta["version_kek"])).decrypt(
                _desde_b64(envuelta["nonce"]), _desde_b64(envuelta["dek"]), contexto.encode("utf-8"))
        except InvalidTag as e:
            raise ErrorCifrado("No se pudo desenvolver la llave de datos (contexto o datos alterados).") from e

    def seudonimo(self, identificador: str, prefijo: str = "seu_") -> str:
        """Token determinista HMAC-SHA256: mismo usuario -> mismo token, sin poder revertirlo."""
        digest = hmac.new(self._llave_seudonimos, identificador.encode("utf-8"), hashlib.sha256).hexdigest()
        return prefijo + digest[:20]

    def estado(self) -> dict:
        return {"algoritmo": ALGORITMO, "modo": "cifrado por sobre (DEK por registro + KEK en KMS)",
                "version_activa": self._activa,
                "versiones": [{"version": v.version, "estado": v.estado, "creada_en": v.creada_en}
                              for v in self._versiones.values()],
                "historial": list(self.historial)}


# =============================================================================== cifrado en reposo
class CifradorCampos:
    """Cifra y descifra campos sensibles (PII) con AES-256-GCM y llaves del KMS."""

    def __init__(self, kms: KMSSimulado | None = None):
        self.kms = kms or KMSSimulado()

    def cifrar(self, valor: Any, contexto: str) -> dict:
        """Devuelve un sobre serializable. `valor` puede ser cualquier dato JSON."""
        dek = AESGCM.generate_key(bit_length=256)
        nonce = secrets.token_bytes(BYTES_NONCE)
        texto = json.dumps(valor, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        cifrado = AESGCM(dek).encrypt(nonce, texto, contexto.encode("utf-8"))
        return {"alg": ALGORITMO, "contexto": contexto, "nonce": _b64(nonce), "ct": _b64(cifrado),
                "dek_envuelta": self.kms.envolver(dek, contexto)}

    def descifrar(self, sobre: dict, contexto: str | None = None) -> Any:
        contexto = contexto or sobre["contexto"]
        if contexto != sobre["contexto"]:
            raise ErrorCifrado("El contexto no coincide con el del registro cifrado.")
        dek = self.kms.desenvolver(sobre["dek_envuelta"], contexto)
        try:
            texto = AESGCM(dek).decrypt(_desde_b64(sobre["nonce"]), _desde_b64(sobre["ct"]),
                                        contexto.encode("utf-8"))
        except InvalidTag as e:
            raise ErrorCifrado("El texto cifrado fue alterado.") from e
        return json.loads(texto.decode("utf-8"))

    def reenvolver(self, sobre: dict) -> dict:
        """Tras una rotación: re-cifra solo la DEK con la KEK activa (los datos no se tocan)."""
        if sobre["dek_envuelta"]["version_kek"] == self.kms.version_activa:
            return sobre
        dek = self.kms.desenvolver(sobre["dek_envuelta"], sobre["contexto"])
        return {**sobre, "dek_envuelta": self.kms.envolver(dek, sobre["contexto"])}


# =============================================================================== capas Plata y Oro
IDENTIFICADORES_DIRECTOS = {"nombre", "email", "cedula", "telefono", "direccion", "pan", "token_tarjeta", "ip"}


def rango_edad(edad: int | None) -> str:
    if edad is None:
        return "no_informada"
    if edad < 25:
        return "18-24"
    if edad < 35:
        return "25-34"
    if edad < 45:
        return "35-44"
    if edad < 60:
        return "45-59"
    return "60+"


def a_capa_plata(registros: Iterable[dict], kms: KMSSimulado, campo_id: str = "usuario_id") -> list[dict]:
    """Bronce -> Plata: quita identificadores directos, seudonimiza el id y generaliza la edad."""
    plata = []
    for r in registros:
        fila = {k: v for k, v in r.items() if k not in IDENTIFICADORES_DIRECTOS and k != campo_id}
        fila["seudonimo"] = kms.seudonimo(str(r[campo_id]))
        if "edad" in fila:
            fila["rango_edad"] = rango_edad(fila.pop("edad"))
        plata.append(fila)
    return plata


def agregar_capa_oro(filas_plata: Iterable[dict], dimensiones: list[str], metrica: str | None = None,
                     k: int = K_MINIMO) -> dict:
    """Plata -> Oro: agrega por dimensiones y suprime celdas con menos de k personas distintas.
    Las celdas suprimidas se informan sin valores (ni conteo exacto) para evitar re-identificación."""
    if k < 2:
        raise ValueError("k debe ser al menos 2.")
    grupos: dict[tuple, dict] = {}
    for f in filas_plata:
        clave = tuple(f.get(d) for d in dimensiones)
        g = grupos.setdefault(clave, {"personas": set(), "suma": 0.0})
        g["personas"].add(f["seudonimo"])
        if metrica:
            g["suma"] += float(f.get(metrica) or 0)
    celdas, suprimidas = [], 0
    for clave, g in sorted(grupos.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        n = len(g["personas"])
        celda = dict(zip(dimensiones, clave))
        if n < k:
            suprimidas += 1
            celdas.append({**celda, "suprimida": True, "personas": f"< {k}", "total": None, "promedio": None})
            continue
        celdas.append({**celda, "suprimida": False, "personas": n,
                       "total": round(g["suma"], 2) if metrica else None,
                       "promedio": round(g["suma"] / n, 2) if metrica else None})
    return {"k_minimo": k, "dimensiones": dimensiones, "metrica": metrica,
            "celdas": celdas, "celdas_publicadas": len(celdas) - suprimidas, "celdas_suprimidas": suprimidas,
            "nota": "Solo se publican agregados con al menos k personas; nunca datos individuales."}


def enmascarar_email(email: str) -> str:
    usuario, _, dominio = email.partition("@")
    return (usuario[:1] + "***@" + dominio) if dominio else "***"


def hash_documento(contenido: dict) -> str:
    """SHA-256 canónico (JSON ordenado) para sellar documentos firmados electrónicamente."""
    canonico = json.dumps(contenido, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()
