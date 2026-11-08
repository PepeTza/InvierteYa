"""Servicio central de InvierteYa (lógica de negocio, sin dependencias web).

Orquesta el flujo de los diagramas 1 a 4:
  registro -> KYC (simulado) -> adhesión al fideicomiso -> cuestionario/perfil
  aporte: autorización -> captura -> asignación de unidades (+ tutor)
          o reverso si hay timeout o falla
  cierre del día: liquidación T+1 -> conciliación en 3 niveles -> propuesta de órdenes -> batch

Todo se guarda en memoria: es un prototipo. Solo datos sintéticos.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from app.core import conciliacion, perfil as perfil_mod, tutor
from app.core.fideicomiso import FideicomisoSimulado, calcular_unidades, a_dolares
from app.core.pasarela_simulada import PasarelaSimulada, ConfigPasarela

MONTO_MINIMO = 500        # $5,00 en centavos
MONTO_MAXIMO = 100_000    # $1.000 por aporte (límite supuesto, validar con cumplimiento)

MENSAJES_RECHAZO = {
    "51": "Tu banco no aprobó el pago, posiblemente por saldo insuficiente.",
}
MENSAJE_RECHAZO_GENERICO = ("Tu banco no aprobó el pago. Comunícate con tu banco "
                            "o intenta con otra tarjeta.")  # se usa también para 59 (fraude)


class ErrorNegocio(Exception):
    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo, self.mensaje = codigo, mensaje


@dataclass
class Usuario:
    id: str
    nombre: str
    email: str
    kyc_aprobado: bool = False
    adhesion_firmada: bool = False
    perfil: str | None = None
    conocimiento: int = 1
    lecciones_vistas: set[str] = field(default_factory=set)


class InvierteYa:
    def __init__(self, config_pasarela: ConfigPasarela | None = None):
        self.pasarela = PasarelaSimulada(config_pasarela)
        self.fideicomiso = FideicomisoSimulado()
        self.usuarios: dict[str, Usuario] = {}
        self.aportes: dict[str, dict] = {}
        self.idempotencia: dict[tuple[str, str], str] = {}   # (usuario, clave) -> aporte_id
        self.excepciones: list[dict] = []
        self.cierres: dict[str, dict] = {}                   # fecha -> resultado (el cierre corre una vez)

    # ------------------------------------------------------------------ usuarios
    def registrar(self, nombre: str, email: str) -> Usuario:
        u = Usuario(id="usr_" + secrets.token_hex(4), nombre=nombre, email=email)
        self.usuarios[u.id] = u
        return u

    def _usuario(self, usuario_id: str) -> Usuario:
        if usuario_id not in self.usuarios:
            raise ErrorNegocio("USUARIO_NO_EXISTE", "El usuario no existe.")
        return self.usuarios[usuario_id]

    def aprobar_kyc(self, usuario_id: str) -> dict:
        """Proveedor de KYC SIMULADO: siempre aprueba. El resultado se comparte con el banco fiduciario."""
        u = self._usuario(usuario_id)
        u.kyc_aprobado = True
        return {"usuario_id": u.id, "kyc": "APROBADO", "compartido_con_fiduciario": True}

    def firmar_adhesion(self, usuario_id: str, acepta: bool) -> dict:
        u = self._usuario(usuario_id)
        if not u.kyc_aprobado:
            raise ErrorNegocio("KYC_PENDIENTE", "Primero debe aprobarse la verificación de identidad.")
        if not acepta:
            raise ErrorNegocio("ADHESION_RECHAZADA", "Sin aceptar el contrato de adhesión no se puede invertir.")
        u.adhesion_firmada = True
        leccion = self._leccion(u, "ANTES_PRIMER_APORTE") if u.perfil else None
        return {"usuario_id": u.id, "adhesion": "FIRMADA", "fideicomitente_y_beneficiario": True,
                "leccion": leccion}

    def evaluar_perfil(self, usuario_id: str, c: perfil_mod.Cuestionario) -> dict:
        u = self._usuario(usuario_id)
        resultado = perfil_mod.evaluar(c)
        u.perfil, u.conocimiento = resultado["perfil"], c.conocimiento
        resultado["leccion"] = self._leccion(u, "CUESTIONARIO_COMPLETO")
        resultado["motor"] = "reglas (el modelo baseline lo reemplaza; ver ia/)"
        return resultado

    def _leccion(self, u: Usuario, paso: str) -> dict | None:
        l = tutor.seleccionar(paso, u.perfil or "CONSERVADOR", u.conocimiento, u.lecciones_vistas)
        if l:
            u.lecciones_vistas.add(l["id"])
        return l

    # ------------------------------------------------------------------ aportes
    def crear_aporte(self, usuario_id: str, monto_centavos: int, token: str,
                     clave_idempotencia: str, momento: datetime | None = None) -> dict:
        t0 = time.perf_counter()
        u = self._usuario(usuario_id)

        # Caso A del diagrama 3: solicitud duplicada -> se devuelve el resultado original.
        previo = self.idempotencia.get((u.id, clave_idempotencia))
        if previo:
            return {**self.aportes[previo], "duplicado": True}

        if not u.kyc_aprobado:
            raise ErrorNegocio("KYC_PENDIENTE", "Debe completar la verificación de identidad.")
        if not u.adhesion_firmada:
            raise ErrorNegocio("ADHESION_PENDIENTE", "Debe firmar el contrato de adhesión al fideicomiso.")
        if not u.perfil:
            raise ErrorNegocio("PERFIL_PENDIENTE", "Debe completar el cuestionario de perfil.")
        if not MONTO_MINIMO <= monto_centavos <= MONTO_MAXIMO:
            raise ErrorNegocio("MONTO_INVALIDO", "El aporte debe estar entre $5 y $1.000.")

        momento = momento or datetime.now()
        aporte = {"id": "apt_" + secrets.token_hex(5), "usuario_id": u.id, "portafolio": u.perfil,
                  "monto_centavos": monto_centavos, "monto": str(a_dolares(monto_centavos)),
                  "estado": "PENDIENTE", "fecha": momento.date().isoformat(),
                  "authorization_id": None, "rrn": None, "auth_code": None,
                  "unidades": None, "mensaje": None, "leccion": None,
                  "eventos": [], "iso8583": [], "latencia_pasarela_ms": 0.0, "duplicado": False}
        self.aportes[aporte["id"]] = aporte
        self.idempotencia[(u.id, clave_idempotencia)] = aporte["id"]

        def evento(estado: str, detalle: str = ""):
            aporte["estado"] = estado
            aporte["eventos"].append({"estado": estado, "detalle": detalle})

        evento("PENDIENTE", "Validaciones de KYC, adhesión, perfil y monto superadas")

        # Diagrama 1: autorización
        r = self.pasarela.autorizar(token, monto_centavos, aporte["id"], momento)
        aporte["iso8583"] += r.iso
        aporte["latencia_pasarela_ms"] += r.latencia_ms
        aporte["authorization_id"], aporte["rrn"], aporte["auth_code"] = r.authorization_id, r.rrn, r.auth_code

        if r.status == "INVALID_TOKEN":
            evento("RECHAZADO", "Token de tarjeta inválido")
            aporte["mensaje"] = "No pudimos procesar tu tarjeta. Vuelve a ingresarla."
        elif r.status == "DECLINED":
            evento("RECHAZADO", f"Código de respuesta {r.response_code}")
            aporte["mensaje"] = MENSAJES_RECHAZO.get(r.response_code, MENSAJE_RECHAZO_GENERICO)
        elif r.status == "TIMEOUT":
            evento("EN_REVERSO", "Sin respuesta del emisor en 30 s")
            self._reversar(aporte, "TIMEOUT", evento, momento)
        else:
            evento("AUTORIZADO", f"Código de autorización {r.auth_code}")
            # Diagrama 2: captura inmediata
            c = self.pasarela.capturar(r.authorization_id, monto_centavos, momento)
            aporte["iso8583"] += c.iso
            aporte["latencia_pasarela_ms"] += c.latencia_ms
            if c.status != "CAPTURED":
                evento("EN_REVERSO", f"Falla en la captura ({c.response_code})")
                self._reversar(aporte, "FALLA_CAPTURA", evento, momento)
            else:
                evento("CAPTURADO", f"RRN {c.rrn}")
                unidades = calcular_unidades(monto_centavos, u.perfil)
                aporte["unidades"] = str(unidades)
                evento("ASIGNADO", f"{unidades} unidades del portafolio {u.perfil.capitalize()}")
                aporte["mensaje"] = f"¡Listo! Recibiste {unidades} unidades de participación."
                aporte["leccion"] = self._leccion(u, "UNIDADES_ASIGNADAS")

        aporte["latencia_total_ms"] = round(aporte["latencia_pasarela_ms"]
                                            + (time.perf_counter() - t0) * 1000, 1)
        return dict(aporte)

    def _reversar(self, aporte: dict, motivo: str, evento, momento: datetime):
        rv = self.pasarela.reversar(aporte["authorization_id"], motivo, momento)
        aporte["iso8583"] += rv.iso
        aporte["latencia_pasarela_ms"] += rv.latencia_ms
        if rv.status == "REVERSED":
            evento("REVERSADO", "Reverso confirmado (0410)")
            aporte["mensaje"] = "No se realizó el cobro. Si ves una retención, tu banco la liberará."
        else:
            evento("REVERSO_PENDIENTE", "Sin respuesta tras 3 reintentos (0421); va a conciliación")
            aporte["mensaje"] = "Estamos confirmando tu pago con el banco. No vuelvas a intentarlo aún."
            self.excepciones.append({"tipo": "REVERSO_PENDIENTE", "aporte_id": aporte["id"]})

    # ------------------------------------------------------------------ consultas
    def portafolio(self, usuario_id: str) -> dict:
        from app.core.fideicomiso import PORTAFOLIOS
        u = self._usuario(usuario_id)
        asignados = [a for a in self.aportes.values()
                     if a["usuario_id"] == u.id and a["estado"] == "ASIGNADO"]
        unidades = sum((Decimal(a["unidades"]) for a in asignados), Decimal(0))
        valor = PORTAFOLIOS[u.perfil]["valor_unidad"] if u.perfil else Decimal(0)
        return {"usuario_id": u.id, "portafolio": u.perfil, "unidades": str(unidades),
                "valor_unidad": str(valor), "saldo": str((unidades * valor).quantize(Decimal("0.01"))),
                "composicion": PORTAFOLIOS[u.perfil]["composicion"] if u.perfil else {},
                "aportes": len(asignados), "leccion": self._leccion(u, "VER_PORTAFOLIO")}

    # ------------------------------------------------------------------ cierre del día
    def cerrar_dia(self, fecha: date, inyectar_descuadre: bool = False) -> dict:
        """T+1: liquidación -> abono al fideicomiso -> conciliación 3 niveles -> batch de órdenes."""
        if fecha.isoformat() in self.cierres:
            # Un día se cierra una sola vez: repetirlo duplicaría el abono en el fideicomiso.
            return {**self.cierres[fecha.isoformat()], "ya_cerrado": True}
        del_dia = [a for a in self.aportes.values() if a["fecha"] == fecha.isoformat()]
        liquidacion = self.pasarela.liquidacion(fecha)

        if inyectar_descuadre and liquidacion["transacciones"]:
            # Para la demo: simulamos que la pasarela "pierde" una transacción del archivo.
            perdida = liquidacion["transacciones"].pop(0)
            liquidacion["total_bruto"] -= perdida["monto"]
            liquidacion["total_comisiones"] -= perdida["comision"]
            liquidacion["total_neto"] = liquidacion["total_bruto"] - liquidacion["total_comisiones"]

        asignados = [a for a in del_dia if a["estado"] == "ASIGNADO"]
        por_portafolio: dict[str, int] = {}
        cantidad: dict[str, int] = {}
        for a in asignados:
            por_portafolio[a["portafolio"]] = por_portafolio.get(a["portafolio"], 0) + a["monto_centavos"]
            cantidad[a["portafolio"]] = cantidad.get(a["portafolio"], 0) + 1

        # Banco fiduciario recibe el abono neto + la cobertura de comisión que paga InvierteYa
        cobertura = liquidacion["total_comisiones"]
        self.fideicomiso.recibir_abono(fecha.isoformat(), liquidacion["total_neto"], por_portafolio)

        n1 = conciliacion.nivel1_pagos_vs_liquidacion(del_dia, liquidacion)
        n2 = conciliacion.nivel2_aportes_vs_fideicomiso(sum(por_portafolio.values()),
                                                        liquidacion["total_neto"], cobertura)
        unidades: dict[str, Decimal] = {}
        for a in self.aportes.values():
            if a["estado"] == "ASIGNADO":
                unidades[a["portafolio"]] = unidades.get(a["portafolio"], Decimal(0)) + Decimal(a["unidades"])
        n3 = conciliacion.nivel3_unidades_vs_custodia(unidades, self.fideicomiso.estado_posiciones(), cantidad)

        excepciones = n1["excepciones"] + n2["excepciones"] + n3["excepciones"]
        # Propuesta de órdenes (InvierteYa propone, el fiduciario aprueba)
        propuesta = self.fideicomiso.proponer_ordenes(por_portafolio)
        batch = self.fideicomiso.aprobar_y_ejecutar(propuesta)
        resultado = {"fecha": fecha.isoformat(), "conciliado": not excepciones,
                     "niveles": [n1, n2, n3], "excepciones": excepciones,
                     "propuesta_ordenes": propuesta, "batch": batch,
                     "iso_cierre_pasarela": liquidacion["iso_cierre"], "ya_cerrado": False}
        self.cierres[fecha.isoformat()] = resultado
        return resultado
