"""Servicio central de InvierteYa (lógica de negocio, sin dependencias web) · Sesión 3.

Orquesta el flujo de los diagramas 1 a 4 con el catálogo de fideicomisos:
  registro -> KYC simulado (aporta la edad) -> cuestionario en 2 tandas / perfil
  catálogo etiquetado por idoneidad -> adhesión POR FIDEICOMISO (sello de tiempo + SHA-256)
  aporte repartido entre fideicomisos (suma 100%) con comisión transparente por medio de pago:
          autorización -> captura -> asignación de unidades por fideicomiso (+ tutor)
          o reverso si hay timeout o falla
  cierre del día: liquidación T+1 -> conciliación 3 niveles por fideicomiso -> órdenes por lote
  IA: riesgo de abandono (solo sugiere) y pronóstico de flujos para el fiduciario
  privacidad: consentimiento separado, habeas data (acceso y supresión), PII cifrada en reposo,
          informes agregados Oro con k >= 10.

Todo se guarda en memoria: es un prototipo. Solo datos sintéticos.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from app.core import catalogo as cat
from app.core import conciliacion, perfil as perfil_mod, tutor
from app.core.fideicomiso import FideicomisoSimulado, a_dolares, calcular_unidades
from app.core.pasarela_simulada import ConfigPasarela, PasarelaSimulada
from app.core.seguridad_datos import (CifradorCampos, KMSSimulado, a_capa_plata, agregar_capa_oro,
                                      hash_documento)
from ia import predictor

ORDEN_RIESGO = ["CONSERVADOR", "MODERADO", "AGRESIVO"]

MONTO_MINIMO = 500        # $5,00 en centavos
MONTO_MAXIMO = 100_000    # $1.000 por aporte (límite supuesto, validar con cumplimiento)
EDAD_KYC_DEFECTO = 24     # contrato S3 §2.1

# Transparencia de comisiones (Res. SUDEBAN 063.15) · contrato S3 §3.2
COMISION_APORTE_PCT = Decimal("1.0")
RECARGO_MEDIO_PAGO_PCT = {"TARJETA": Decimal("2.0"), "PAGO_MOVIL": Decimal("0.0"),
                          "TRANSFERENCIA": Decimal("0.0")}
VERSION_CONTRATO_ADHESION = "ADH-FID-2026.11-S3"

MENSAJES_RECHAZO = {
    "51": "Tu banco no aprobó el pago, posiblemente por saldo insuficiente.",
}
MENSAJE_RECHAZO_GENERICO = ("Tu banco no aprobó el pago. Comunícate con tu banco "
                            "o intenta con otra tarjeta.")  # se usa también para 59 (fraude)

CONSENTIMIENTOS_DEFECTO = {
    # Separado de los términos y desactivado por defecto (opt-in): informes agregados Oro.
    "informes_agregados": False,
    # Avisos suaves de ahorro (modelo de abandono). Se puede retirar en cualquier momento.
    "alertas_ahorro": True,
}


class ErrorNegocio(Exception):
    def __init__(self, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.codigo, self.mensaje = codigo, mensaje


@dataclass
class Usuario:
    id: str
    nombre: str
    pii: dict = field(default_factory=dict, repr=False)   # email y edad KYC cifrados (AES-256-GCM)
    kyc_aprobado: bool = False
    adhesion_firmada: bool = False                        # firmó al menos una adhesión
    adhesiones: dict[str, dict] = field(default_factory=dict)   # fideicomiso_id -> documento firmado
    adhesion_general: dict | None = None                  # S2: adhesión sin fideicomiso antes del perfil
    perfil: str | None = None
    conocimiento: int = 1
    lecciones_vistas: set[str] = field(default_factory=set)
    cuestionario_cifrado: dict | None = field(default=None, repr=False)
    registrado_en: datetime = field(default_factory=datetime.now)
    consentimientos: dict[str, bool] = field(default_factory=lambda: dict(CONSENTIMIENTOS_DEFECTO))
    historial_consentimientos: list[dict] = field(default_factory=list)
    consultas: int = 0                                    # sesiones/consultas (insumo del modelo de abandono)
    suprimido: bool = False


def _centavos_pct(monto_centavos: int, pct: Decimal) -> int:
    return int((Decimal(monto_centavos) * pct / 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


class InvierteYa:
    def __init__(self, config_pasarela: ConfigPasarela | None = None, kms: KMSSimulado | None = None):
        self.pasarela = PasarelaSimulada(config_pasarela)
        self.fideicomiso = FideicomisoSimulado()
        self.catalogo = cat.CatalogoCache()
        self.kms = kms or KMSSimulado()
        self.cifrador = CifradorCampos(self.kms)
        self.usuarios: dict[str, Usuario] = {}
        self.aportes: dict[str, dict] = {}
        self.idempotencia: dict[tuple[str, str], str] = {}   # (usuario, clave) -> aporte_id
        self.excepciones: list[dict] = []
        self.cierres: dict[str, dict] = {}                   # fecha -> resultado (el cierre corre una vez)
        self.revisiones_perfil: list[dict] = []              # probabilidad < 60% o desacuerdo del usuario
        self._pronostico: tuple[date, dict] | None = None

    # ------------------------------------------------------------------ usuarios y PII cifrada
    def registrar(self, nombre: str, email: str) -> Usuario:
        u = Usuario(id="usr_" + secrets.token_hex(4), nombre=nombre)
        u.pii = self.cifrador.cifrar({"email": email, "edad": None}, self._ctx_pii(u.id))
        self.usuarios[u.id] = u
        return u

    @staticmethod
    def _ctx_pii(usuario_id: str) -> str:
        return f"usuario:{usuario_id}:pii"

    @staticmethod
    def _ctx_cuestionario(usuario_id: str) -> str:
        return f"usuario:{usuario_id}:cuestionario"

    def _leer_pii(self, u: Usuario) -> dict:
        return self.cifrador.descifrar(u.pii, self._ctx_pii(u.id))

    def _guardar_pii(self, u: Usuario, datos: dict):
        u.pii = self.cifrador.cifrar(datos, self._ctx_pii(u.id))

    def _usuario(self, usuario_id: str) -> Usuario:
        if usuario_id not in self.usuarios:
            raise ErrorNegocio("USUARIO_NO_EXISTE", "El usuario no existe.")
        return self.usuarios[usuario_id]

    def _usuario_activo(self, usuario_id: str) -> Usuario:
        u = self._usuario(usuario_id)
        if u.suprimido:
            raise ErrorNegocio("USUARIO_SUPRIMIDO", "El usuario ejerció su derecho de supresión de datos.")
        return u

    def edad_kyc(self, usuario_id: str) -> int:
        edad = self._leer_pii(self._usuario(usuario_id)).get("edad")
        return edad if edad is not None else EDAD_KYC_DEFECTO

    def aprobar_kyc(self, usuario_id: str, edad: int | None = None) -> dict:
        """Proveedor de KYC SIMULADO: siempre aprueba y aporta la edad (ya no se pregunta en el
        cuestionario). El resultado se comparte con el banco fiduciario."""
        u = self._usuario_activo(usuario_id)
        datos = self._leer_pii(u)
        datos["edad"] = edad if edad is not None else (datos.get("edad") or EDAD_KYC_DEFECTO)
        self._guardar_pii(u, datos)
        u.kyc_aprobado = True
        return {"usuario_id": u.id, "kyc": "APROBADO", "compartido_con_fiduciario": True,
                "edad_kyc": datos["edad"]}

    # ------------------------------------------------------------------ catálogo
    def _fideicomiso(self, fideicomiso_id: str) -> dict:
        f = self.catalogo.fideicomiso(fideicomiso_id)
        if f is None:
            raise ErrorNegocio("FIDEICOMISO_NO_EXISTE", f"El fideicomiso '{fideicomiso_id}' no existe en el catálogo.")
        return f

    def _adheridos(self, u: Usuario) -> set[str]:
        ids = set(u.adhesiones)
        if u.adhesion_general and u.perfil:
            ids.add(cat.FIDEICOMISO_POR_DEFECTO[u.perfil])   # compatibilidad S2
        return ids

    def listar_fideicomisos(self, usuario_id: str | None = None, riesgo_max: int | None = None) -> dict:
        u = self._usuario(usuario_id) if usuario_id else None
        perfil = u.perfil if u else None
        return {
            "usuario_id": u.id if u else None,
            "perfil_usuario": perfil,
            "riesgo_maximo_perfil": cat.RIESGO_MAXIMO_PERFIL.get(perfil) if perfil else None,
            "nota_rendimiento": cat.NOTA_RENDIMIENTO,
            "actualizado_en": self.catalogo.actualizado_en if self.catalogo.obtener() else None,
            "fideicomisos": cat.listar_para_perfil(self.catalogo.obtener(), perfil, riesgo_max,
                                                   self._adheridos(u) if u else set()),
        }

    # ------------------------------------------------------------------ adhesión por fideicomiso
    def firmar_adhesion(self, usuario_id: str, acepta: bool, fideicomiso_id: str | None = None,
                        confirmacion_riesgo_extra: bool = False, momento: datetime | None = None) -> dict:
        u = self._usuario_activo(usuario_id)
        if not u.kyc_aprobado:
            raise ErrorNegocio("KYC_PENDIENTE", "Primero debe aprobarse la verificación de identidad.")
        if not acepta:
            raise ErrorNegocio("ADHESION_RECHAZADA", "Sin aceptar el contrato de adhesión no se puede invertir.")
        if fideicomiso_id is None and u.perfil:
            fideicomiso_id = cat.FIDEICOMISO_POR_DEFECTO[u.perfil]

        f, etiqueta = None, None
        if fideicomiso_id is not None:
            f = self._fideicomiso(fideicomiso_id)
            if not u.perfil:
                raise ErrorNegocio("PERFIL_PENDIENTE",
                                   "Completa el cuestionario para evaluar si el fideicomiso es adecuado para ti.")
            etiqueta = cat.etiquetar(f["riesgo"], u.perfil)
            if etiqueta == "POR_ENCIMA_DEL_PERFIL" and not confirmacion_riesgo_extra:
                raise ErrorNegocio("CONFIRMACION_RIESGO_REQUERIDA",
                                   f"'{f['nombre']}' tiene más riesgo que tu perfil {u.perfil.capitalize()}. "
                                   "Puedes elegirlo, pero necesitamos tu confirmación expresa.")

        sello = (momento or datetime.now()).astimezone().isoformat(timespec="seconds")
        documento = {"contrato": "ADHESION_FIDEICOMISO", "version_contrato": VERSION_CONTRATO_ADHESION,
                     "usuario_id": u.id, "fideicomiso_id": fideicomiso_id, "perfil": u.perfil,
                     "etiqueta_idoneidad": etiqueta,
                     "confirmacion_riesgo_extra": bool(confirmacion_riesgo_extra),
                     "acepta": True, "sello_tiempo": sello}
        firmado = {**documento, "hash_adhesion": hash_documento(documento)}
        if fideicomiso_id is None:
            u.adhesion_general = firmado
        else:
            u.adhesiones[fideicomiso_id] = firmado
        u.adhesion_firmada = True

        leccion = self._leccion(u, "ANTES_PRIMER_APORTE") if u.perfil else None
        return {"usuario_id": u.id, "adhesion": "FIRMADA", "fideicomitente_y_beneficiario": True,
                "fideicomiso_id": fideicomiso_id, "nombre_fideicomiso": f["nombre"] if f else None,
                "etiqueta": etiqueta, "confirmacion_riesgo_extra": bool(confirmacion_riesgo_extra),
                "sello_tiempo": sello, "hash_adhesion": firmado["hash_adhesion"], "algoritmo_hash": "SHA-256",
                "version_contrato": VERSION_CONTRATO_ADHESION,
                "base_legal": "Decreto-Ley sobre Mensajes de Datos y Firmas Electrónicas",
                "leccion": leccion}

    # ------------------------------------------------------------------ perfil (2 tandas)
    def evaluar_perfil(self, usuario_id: str, c: perfil_mod.Cuestionario) -> dict:
        """Perfil con el modelo (ia/) + reglas de seguridad + supervisión humana.
        Si el modelo no está disponible, se usan las reglas de app/core/perfil.py."""
        u = self._usuario_activo(usuario_id)
        resultado = perfil_mod.evaluar(c)          # reglas: puntaje, explicación y respaldo
        resultado.update({"perfil_reglas": resultado["perfil"], "probabilidad": None,
                          "probabilidades": None, "revision_humana": False,
                          "motor": "reglas (modelo no disponible; correr python ia/entrenar.py)"})
        pred = predictor.predecir(c)
        if pred:
            perfil = pred["perfil"]
            avisos = list(pred["avisos"])
            if pred["revision_humana"]:
                # Probabilidad < 60%: un asesor revisa el caso. Mientras tanto se asigna el perfil
                # MÁS CONSERVADOR entre el modelo y las reglas (nunca se arriesga de más).
                perfil = min(perfil, resultado["perfil_reglas"], key=ORDEN_RIESGO.index)
                avisos.append("Tu perfil será revisado por un asesor. Mientras tanto te asignamos "
                              f"provisionalmente el perfil {perfil.capitalize()}.")
                self.revisiones_perfil.append({"revision_id": "rev_" + secrets.token_hex(4),
                                               "origen": "PROBABILIDAD_BAJA", "usuario_id": u.id,
                                               "perfil_modelo": pred["perfil_modelo"],
                                               "perfil_reglas": resultado["perfil_reglas"],
                                               "perfil_provisional": perfil,
                                               "probabilidad": pred["probabilidad"],
                                               "estado": "PENDIENTE_ASESOR"})
            resultado.update({"perfil": perfil, "avisos": avisos,
                              "explicacion": perfil_mod.explicar(resultado["detalle_puntos"], perfil),
                              "probabilidad": pred["probabilidad"],
                              "probabilidades": pred["probabilidades"],
                              "revision_humana": pred["revision_humana"], "motor": pred["motor"]})
        u.perfil, u.conocimiento = resultado["perfil"], c.conocimiento or 1
        # Las respuestas (situación financiera) son sensibles: se guardan cifradas.
        u.cuestionario_cifrado = self.cifrador.cifrar(asdict(c), self._ctx_cuestionario(u.id))
        resultado["fideicomiso_recomendado"] = cat.FIDEICOMISO_POR_DEFECTO[u.perfil]
        resultado["leccion"] = self._leccion(u, "CUESTIONARIO_COMPLETO")
        return resultado

    def evaluar_perfil_s3(self, usuario_id: str, respuestas: dict) -> dict:
        """Tanda 1 (o 1+2) del cuestionario conversacional. La edad sale del KYC si no se envía."""
        datos = {k: v for k, v in respuestas.items() if k != "tanda"}
        if datos.get("edad") is None:
            datos["edad"] = self.edad_kyc(usuario_id)
        return self.evaluar_perfil(usuario_id, perfil_mod.Cuestionario.desde_s3(**datos))

    def _cuestionario_guardado(self, u: Usuario) -> perfil_mod.Cuestionario:
        if u.cuestionario_cifrado is None:
            raise ErrorNegocio("PERFIL_PENDIENTE", "Primero completa la Tanda 1 del cuestionario.")
        return perfil_mod.Cuestionario(**self.cifrador.descifrar(u.cuestionario_cifrado,
                                                                 self._ctx_cuestionario(u.id)))

    def completar_tanda2(self, usuario_id: str, dependientes: int | None, quiz_aciertos: int | None) -> dict:
        """'Afinemos tu perfil': combina la Tanda 1 guardada con hogar + quiz y recalcula."""
        u = self._usuario_activo(usuario_id)
        c = self._cuestionario_guardado(u)
        conocimiento = perfil_mod.QUIZ_A_CONOCIMIENTO.get(quiz_aciertos) if quiz_aciertos is not None else None
        c2 = replace(c, dependientes=dependientes, conocimiento=conocimiento, tanda_completada=2)
        return self.evaluar_perfil(u.id, c2)

    def solicitar_revision(self, usuario_id: str, motivo: str) -> dict:
        """Botón 'No estoy de acuerdo con mi perfil': el caso pasa a un asesor humano."""
        u = self._usuario_activo(usuario_id)
        if not u.perfil:
            raise ErrorNegocio("PERFIL_PENDIENTE", "Aún no tienes un perfil que revisar.")
        revision = {"revision_id": "rev_" + secrets.token_hex(4), "origen": "DESACUERDO_USUARIO",
                    "usuario_id": u.id, "perfil_actual": u.perfil, "motivo": motivo.strip()[:500],
                    "estado": "PENDIENTE_ASESOR",
                    "creada_en": datetime.now().astimezone().isoformat(timespec="seconds")}
        self.revisiones_perfil.append(revision)
        return {"revision_id": revision["revision_id"], "estado": revision["estado"],
                "perfil_actual": u.perfil, "mensaje": "Un asesor humano revisará tu perfil."}

    def _leccion(self, u: Usuario, paso: str) -> dict | None:
        l = tutor.seleccionar(paso, u.perfil or "CONSERVADOR", u.conocimiento, u.lecciones_vistas)
        if l:
            u.lecciones_vistas.add(l["id"])
        return l

    # ------------------------------------------------------------------ aportes repartidos
    def _validar_distribucion(self, u: Usuario, monto_centavos: int,
                              distribucion: list[dict] | None) -> list[dict]:
        if not distribucion:
            distribucion = [{"fideicomiso_id": cat.FIDEICOMISO_POR_DEFECTO[u.perfil], "porcentaje": 100}]
        ids = [d["fideicomiso_id"] for d in distribucion]
        porcentajes = [Decimal(str(d["porcentaje"])) for d in distribucion]
        if len(set(ids)) != len(ids) or any(p <= 0 for p in porcentajes) or sum(porcentajes) != 100:
            raise ErrorNegocio("DISTRIBUCION_INVALIDA",
                               "La distribución debe sumar exactamente 100%, sin fideicomisos repetidos.")
        adheridos = self._adheridos(u)
        montos = cat.distribuir_centavos(monto_centavos, [float(p) for p in porcentajes])
        tramos = []
        for fid, pct, monto in zip(ids, porcentajes, montos):
            f = self._fideicomiso(fid)
            if fid not in adheridos:
                raise ErrorNegocio("ADHESION_PENDIENTE",
                                   f"Debes firmar la adhesión al fideicomiso '{f['nombre']}' antes de aportar.")
            if cat.requiere_confirmacion(f["riesgo"], u.perfil) and \
                    not u.adhesiones.get(fid, {}).get("confirmacion_riesgo_extra"):
                # El perfil bajó después de la adhesión: hay que volver a confirmar expresamente.
                raise ErrorNegocio("CONFIRMACION_RIESGO_REQUERIDA",
                                   f"'{f['nombre']}' quedó por encima de tu perfil actual; confirma de nuevo la adhesión.")
            minimo = int(Decimal(str(f["minimo_usd"])) * 100)
            if monto < minimo:
                raise ErrorNegocio("MONTO_MINIMO_FIDEICOMISO",
                                   f"A '{f['nombre']}' le tocarían ${a_dolares(monto)}; su aporte mínimo es "
                                   f"${a_dolares(minimo)}.")
            tramos.append({"fideicomiso_id": fid, "nombre": f["nombre"], "porcentaje": float(pct),
                           "monto_centavos": monto, "valor_unidad": f["valor_unidad"]})
        return tramos

    def crear_aporte(self, usuario_id: str, monto_centavos: int, token: str,
                     clave_idempotencia: str, momento: datetime | None = None,
                     distribucion: list[dict] | None = None, medio_pago: str = "TARJETA") -> dict:
        t0 = time.perf_counter()
        u = self._usuario(usuario_id)

        # Caso A del diagrama 3: solicitud duplicada -> se devuelve el resultado original.
        previo = self.idempotencia.get((u.id, clave_idempotencia))
        if previo:
            return {**self.aportes[previo], "duplicado": True}

        if u.suprimido:
            raise ErrorNegocio("USUARIO_SUPRIMIDO", "El usuario ejerció su derecho de supresión de datos.")
        if not u.kyc_aprobado:
            raise ErrorNegocio("KYC_PENDIENTE", "Debe completar la verificación de identidad.")
        if not u.adhesion_firmada:
            raise ErrorNegocio("ADHESION_PENDIENTE", "Debe firmar el contrato de adhesión al fideicomiso.")
        if not u.perfil:
            raise ErrorNegocio("PERFIL_PENDIENTE", "Debe completar el cuestionario de perfil.")
        if not MONTO_MINIMO <= monto_centavos <= MONTO_MAXIMO:
            raise ErrorNegocio("MONTO_INVALIDO", "El aporte debe estar entre $5 y $1.000.")
        if medio_pago not in RECARGO_MEDIO_PAGO_PCT:
            raise ErrorNegocio("MEDIO_PAGO_INVALIDO", "Medio de pago no soportado.")
        tramos = self._validar_distribucion(u, monto_centavos, distribucion)

        # Comisión transparente: se cobra encima del aporte, así se invierte el 100% del monto.
        comision = _centavos_pct(monto_centavos, COMISION_APORTE_PCT)
        recargo = _centavos_pct(monto_centavos, RECARGO_MEDIO_PAGO_PCT[medio_pago])
        cobrado = monto_centavos + comision + recargo

        momento = momento or datetime.now()
        aporte = {"id": "apt_" + secrets.token_hex(5), "usuario_id": u.id, "portafolio": u.perfil,
                  "monto_centavos": monto_centavos, "monto": str(a_dolares(monto_centavos)),
                  "medio_pago": medio_pago,
                  "comision_aporte_pct": float(COMISION_APORTE_PCT),
                  "recargo_medio_pago_pct": float(RECARGO_MEDIO_PAGO_PCT[medio_pago]),
                  "comision_aporte_centavos": comision, "recargo_medio_pago_centavos": recargo,
                  "comision_aporte_usd": str(a_dolares(comision)),
                  "recargo_medio_pago_usd": str(a_dolares(recargo)),
                  "comision_total_usd": str(a_dolares(comision + recargo)),
                  "monto_cobrado_centavos": cobrado, "monto_cobrado": str(a_dolares(cobrado)),
                  "distribucion": [{"fideicomiso_id": t["fideicomiso_id"], "porcentaje": t["porcentaje"]}
                                   for t in tramos],
                  "asignaciones": [],
                  "estado": "PENDIENTE", "fecha": momento.date().isoformat(),
                  "creado_en": momento.isoformat(timespec="seconds"),
                  "authorization_id": None, "rrn": None, "auth_code": None,
                  "unidades": None, "mensaje": None, "leccion": None,
                  "eventos": [], "iso8583": [], "latencia_pasarela_ms": 0.0, "duplicado": False}
        self.aportes[aporte["id"]] = aporte
        self.idempotencia[(u.id, clave_idempotencia)] = aporte["id"]
        u.consultas += 1

        def evento(estado: str, detalle: str = ""):
            aporte["estado"] = estado
            aporte["eventos"].append({"estado": estado, "detalle": detalle})

        evento("PENDIENTE", "Validaciones de KYC, adhesión, perfil, monto y distribución superadas")

        # Diagrama 1: autorización (por el monto cobrado: aporte + comisión + recargo)
        r = self.pasarela.autorizar(token, cobrado, aporte["id"], momento)
        aporte["iso8583"] += r.iso
        aporte["latencia_pasarela_ms"] += r.latencia_ms
        aporte["authorization_id"], aporte["rrn"], aporte["auth_code"] = r.authorization_id, r.rrn, r.auth_code

        if r.status == "INVALID_TOKEN":
            evento("RECHAZADO", "Token del medio de pago inválido")
            aporte["mensaje"] = "No pudimos procesar tu medio de pago. Vuelve a ingresarlo."
        elif r.status == "DECLINED":
            evento("RECHAZADO", f"Código de respuesta {r.response_code}")
            aporte["mensaje"] = MENSAJES_RECHAZO.get(r.response_code, MENSAJE_RECHAZO_GENERICO)
        elif r.status == "TIMEOUT":
            evento("EN_REVERSO", "Sin respuesta del emisor en 30 s")
            self._reversar(aporte, "TIMEOUT", evento, momento)
        else:
            evento("AUTORIZADO", f"Código de autorización {r.auth_code}")
            # Diagrama 2: captura inmediata
            c = self.pasarela.capturar(r.authorization_id, cobrado, momento)
            aporte["iso8583"] += c.iso
            aporte["latencia_pasarela_ms"] += c.latencia_ms
            if c.status != "CAPTURED":
                evento("EN_REVERSO", f"Falla en la captura ({c.response_code})")
                self._reversar(aporte, "FALLA_CAPTURA", evento, momento)
            else:
                evento("CAPTURADO", f"RRN {c.rrn}")
                total = Decimal(0)
                for t in tramos:
                    unidades = calcular_unidades(t["monto_centavos"], t["fideicomiso_id"], t["valor_unidad"])
                    total += unidades
                    aporte["asignaciones"].append({
                        "fideicomiso_id": t["fideicomiso_id"], "nombre": t["nombre"],
                        "porcentaje": t["porcentaje"], "monto_centavos": t["monto_centavos"],
                        "monto": str(a_dolares(t["monto_centavos"])), "unidades": str(unidades),
                        "valor_unidad": str(t["valor_unidad"])})
                aporte["unidades"] = str(total)
                detalle = ", ".join(f"{a['nombre']} {a['porcentaje']:g}%" for a in aporte["asignaciones"])
                evento("ASIGNADO", f"{total} unidades · {detalle}")
                aporte["mensaje"] = f"¡Listo! Recibiste {total} unidades de participación."
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
            evento("REVERSO_PENDIENTE", "Sin respuesta: aviso 0420 + 3 repeticiones 0421; va a conciliación")
            aporte["mensaje"] = "Estamos confirmando tu pago con el banco. No vuelvas a intentarlo aún."
            self.excepciones.append({"tipo": "REVERSO_PENDIENTE", "aporte_id": aporte["id"]})

    # ------------------------------------------------------------------ portafolio consolidado
    def portafolio(self, usuario_id: str) -> dict:
        u = self._usuario(usuario_id)
        u.consultas += 1
        catalogo = self.catalogo.obtener()
        asignados = [a for a in self.aportes.values()
                     if a["usuario_id"] == u.id and a["estado"] == "ASIGNADO"]
        por_fid: dict[str, dict] = {}
        for a in asignados:
            for asg in a["asignaciones"]:
                p = por_fid.setdefault(asg["fideicomiso_id"], {"unidades": Decimal(0), "aportes": 0})
                p["unidades"] += Decimal(asg["unidades"])
                p["aportes"] += 1

        fideicomisos, saldo_total, unidades_total = [], Decimal(0), Decimal(0)
        mezcla = {"renta_fija": Decimal(0), "fondos": Decimal(0), "acciones": Decimal(0)}
        for fid in cat.IDS:
            if fid not in por_fid:
                continue
            f, p = catalogo[fid], por_fid[fid]
            saldo = (p["unidades"] * f["valor_unidad"]).quantize(Decimal("0.01"))
            saldo_total += saldo
            unidades_total += p["unidades"]
            for instrumento, pct in f["composicion"].items():
                mezcla[instrumento] += saldo * pct
            fideicomisos.append({"fideicomiso_id": fid, "nombre": f["nombre"], "riesgo": f["riesgo"],
                                 "unidades": str(p["unidades"]), "valor_unidad": str(f["valor_unidad"]),
                                 "saldo": str(saldo), "composicion": f["composicion"],
                                 "comision_anual_pct": f["comision_anual_pct"], "aportes": p["aportes"],
                                 "etiqueta": cat.etiquetar(f["riesgo"], u.perfil)})

        principal = catalogo[cat.FIDEICOMISO_POR_DEFECTO[u.perfil]] if u.perfil else None
        if saldo_total > 0:
            composicion = {k: int((v / saldo_total).to_integral_value(rounding=ROUND_HALF_UP))
                           for k, v in mezcla.items()}
            composicion["renta_fija"] += 100 - sum(composicion.values())   # que sume 100
            valor_unidad = (saldo_total / unidades_total).quantize(Decimal("0.0001"))
        else:
            composicion = dict(principal["composicion"]) if principal else {}
            valor_unidad = principal["valor_unidad"] if principal else Decimal(0)
        return {"usuario_id": u.id, "portafolio": u.perfil, "unidades": str(unidades_total),
                "valor_unidad": str(valor_unidad), "saldo": str(saldo_total.quantize(Decimal("0.01"))),
                "composicion": composicion, "aportes": len(asignados), "fideicomisos": fideicomisos,
                "nota_rendimiento": cat.NOTA_RENDIMIENTO,
                "leccion": self._leccion(u, "VER_PORTAFOLIO") if not u.suprimido else None}

    # ------------------------------------------------------------------ IA predictiva
    VARIABLES_DEMO_INACTIVO = {"meses_activo": 6, "aportes_90d": 0, "dias_desde_ultimo_aporte": 65,
                               "pct_pagos_rechazados": 0.20, "sesiones_por_mes": 0.3,
                               "lecciones_vistas": 1, "tuvo_caida_unidad": True}

    def variables_abandono(self, u: Usuario, ahora: datetime | None = None) -> dict:
        """Variables del modelo de abandono calculadas con la actividad real del usuario."""
        ahora = ahora or datetime.now()
        intentos = [a for a in self.aportes.values() if a["usuario_id"] == u.id]
        asignados = [a for a in intentos if a["estado"] == "ASIGNADO"]
        meses = max(1, (ahora - u.registrado_en).days // 30 + 1)
        fechas = [datetime.fromisoformat(a["creado_en"]) for a in asignados]
        ultimo = max(fechas) if fechas else u.registrado_en
        montos = [float(a["monto"]) for a in asignados]
        return {
            "meses_activo": meses,
            "aportes_90d": sum(1 for f in fechas if f >= ahora - timedelta(days=90)),
            "dias_desde_ultimo_aporte": max(0, (ahora - ultimo).days),
            "pct_pagos_rechazados": round(sum(1 for a in intentos if a["estado"] == "RECHAZADO")
                                          / len(intentos), 4) if intentos else 0.0,
            "sesiones_por_mes": round((u.consultas + 1) / meses, 2),
            "lecciones_vistas": len(u.lecciones_vistas),
            "perfil": u.perfil or "MODERADO",
            "monto_promedio": round(sum(montos) / len(montos), 2) if montos else 20.0,
            "tuvo_caida_unidad": False,
        }

    def riesgo_abandono(self, usuario_id: str, simular_inactivo: bool = False,
                        ahora: datetime | None = None) -> dict:
        """Llama al modelo de Daniel (ia/predictor_abandono.py). Solo sugiere; nunca cobra ni restringe."""
        from ia.predictor_abandono import predecir_abandono

        u = self._usuario(usuario_id)
        variables = self.variables_abandono(u, ahora)
        if simular_inactivo:                      # solo para la demo de la presentación
            variables.update(self.VARIABLES_DEMO_INACTIVO)
        r = predecir_abandono(variables)
        consiente = u.consentimientos.get("alertas_ahorro", False) and not u.suprimido
        if not consiente:
            r["sugerencia_suave"] = None          # retiró el consentimiento: no se le envían avisos
        return {"usuario_id": u.id, **r, "consentimiento_alertas": consiente,
                "datos_simulados": simular_inactivo, "variables": variables}

    def pronostico_flujos(self, hoy: date | None = None) -> dict:
        """Llama a ia/pronostico_flujos.py (Daniel); se cachea una vez al día."""
        hoy = hoy or date.today()
        if self._pronostico and self._pronostico[0] == hoy:
            return self._pronostico[1]
        try:
            from ia.pronostico_flujos import obtener_pronostico_fiduciario
            r = obtener_pronostico_fiduciario()
        except Exception as e:  # el endpoint nunca debe tumbar la API
            raise ErrorNegocio("PRONOSTICO_NO_DISPONIBLE",
                               f"No se pudo calcular el pronóstico ({type(e).__name__}).") from e
        catalogo = self.catalogo.obtener()
        for f in r.get("por_fideicomiso", []):
            if f["fideicomiso_id"] in catalogo:
                f["nombre"] = catalogo[f["fideicomiso_id"]]["nombre"]
        self._pronostico = (hoy, r)
        return r

    # ------------------------------------------------------------------ privacidad / habeas data
    def actualizar_consentimiento(self, usuario_id: str, informes_agregados: bool | None = None,
                                  alertas_ahorro: bool | None = None) -> dict:
        u = self._usuario_activo(usuario_id)
        cambios = {k: v for k, v in {"informes_agregados": informes_agregados,
                                     "alertas_ahorro": alertas_ahorro}.items() if v is not None}
        ahora = datetime.now().astimezone().isoformat(timespec="seconds")
        for k, v in cambios.items():
            if u.consentimientos.get(k) != v:
                u.historial_consentimientos.append({"consentimiento": k, "valor": v, "fecha": ahora})
            u.consentimientos[k] = v
        return {"usuario_id": u.id, "consentimientos": dict(u.consentimientos),
                "actualizado_en": ahora, "historial": list(u.historial_consentimientos),
                "nota": "Este consentimiento es independiente de los términos y puedes cambiarlo cuando quieras."}

    def datos_personales(self, usuario_id: str) -> dict:
        """Derecho de acceso (habeas data, Constitución art. 28)."""
        u = self._usuario(usuario_id)
        pii = self._leer_pii(u)
        respuestas = None
        if u.cuestionario_cifrado is not None:
            c = self._cuestionario_guardado(u)
            respuestas = {k: getattr(c, k) for k in (
                "ahorro_mensual_rango", "horizonte_anios", "objetivo", "reaccion_caida_20",
                "emergencia_200", "experiencia_tipo", "dependientes", "conocimiento", "tanda_completada")}
        intentos = [a for a in self.aportes.values() if a["usuario_id"] == u.id]
        asignados = [a for a in intentos if a["estado"] == "ASIGNADO"]
        adhesiones = list(u.adhesiones.values()) + ([u.adhesion_general] if u.adhesion_general else [])
        return {
            "usuario_id": u.id,
            "suprimido": u.suprimido,
            "datos_identificacion": {"nombre": u.nombre, "email": pii.get("email"), "edad_kyc": pii.get("edad")},
            "kyc_aprobado": u.kyc_aprobado,
            "perfil": u.perfil,
            "respuestas_cuestionario": respuestas,
            "adhesiones": adhesiones,
            "aportes": {"intentos": len(intentos), "asignados": len(asignados),
                        "total_invertido_usd": str(a_dolares(sum(a["monto_centavos"] for a in asignados)))},
            "consentimientos": dict(u.consentimientos),
            "historial_consentimientos": list(u.historial_consentimientos),
            "revisiones_perfil": [r for r in self.revisiones_perfil if r["usuario_id"] == u.id],
            "finalidades": ["Prestar el servicio de inversión a través del fideicomiso",
                            "Evaluar la idoneidad (perfil de riesgo) exigida por la regulación",
                            "Avisos suaves de ahorro (solo si lo consientes)",
                            "Informes agregados anónimos con k >= 10 (solo si lo consientes)"],
            "destinatarios": [{"destinatario": "Banco fiduciario aliado", "datos": "KYC, adhesiones y aportes"},
                              {"destinatario": "Pasarela de pago aliada", "datos": "Solo el token del medio de pago"}],
            "proteccion": {"cifrado_en_reposo": "AES-256-GCM (cifrado por sobre)",
                           "campos_cifrados": ["email", "edad_kyc", "respuestas_cuestionario"],
                           "version_llave_activa": self.kms.version_activa,
                           "seudonimo_analitica": self.kms.seudonimo(u.id)},
            "conservacion": ("Los registros contables y de aportes se conservan el plazo exigido por la "
                             "normativa contra la legitimación de capitales (LC/FT); los datos de uso se "
                             "pueden suprimir con DELETE /v1/usuarios/{id}/datos-personales."),
            "base_legal": "Constitución de la República Bolivariana de Venezuela, art. 28 (habeas data)",
        }

    def suprimir_datos(self, usuario_id: str) -> dict:
        """Derecho de supresión: anonimiza los datos de uso y conserva solo el registro contable."""
        u = self._usuario(usuario_id)
        seudonimo = self.kms.seudonimo(u.id)
        if not u.suprimido:
            ahora = datetime.now().astimezone().isoformat(timespec="seconds")
            u.nombre = "Usuario suprimido"
            self._guardar_pii(u, {"email": None, "edad": None})
            u.cuestionario_cifrado = None
            u.lecciones_vistas.clear()
            u.consultas = 0
            for k in u.consentimientos:
                u.consentimientos[k] = False
            u.historial_consentimientos.append({"consentimiento": "*", "valor": False, "fecha": ahora})
            u.suprimido = True
        return {"usuario_id": u.id, "estado": "DATOS_DE_USO_SUPRIMIDOS", "seudonimo": seudonimo,
                "suprimido": ["nombre", "email", "edad_kyc", "respuestas_cuestionario",
                              "lecciones_vistas", "actividad_en_la_app", "consentimientos"],
                "conservado": ["aportes y movimientos contables", "adhesiones firmadas (hash SHA-256)",
                               "perfil de idoneidad vigente al invertir"],
                "motivo_conservacion": ("Obligación de conservar registros de operaciones para el banco "
                                        "fiduciario (normativa LC/FT y SUDEBAN).")}

    def informe_agregado(self, k: int = 10) -> dict:
        """Capa Oro: saldo invertido por perfil y fideicomiso, solo de quienes consintieron y con k >= 10."""
        bronce = []
        for a in self.aportes.values():
            u = self.usuarios.get(a["usuario_id"])
            if a["estado"] != "ASIGNADO" or u is None or u.suprimido \
                    or not u.consentimientos.get("informes_agregados"):
                continue
            edad = self._leer_pii(u).get("edad")
            for asg in a["asignaciones"]:
                bronce.append({"usuario_id": u.id, "nombre": u.nombre, "edad": edad, "perfil": a["portafolio"],
                               "fideicomiso_id": asg["fideicomiso_id"],
                               "monto_usd": asg["monto_centavos"] / 100})
        plata = a_capa_plata(bronce, self.kms)
        oro = agregar_capa_oro(plata, ["perfil", "fideicomiso_id"], "monto_usd", k=k)
        oro["personas_que_consintieron"] = sum(1 for u in self.usuarios.values()
                                              if u.consentimientos.get("informes_agregados") and not u.suprimido)
        return oro

    def rotar_llaves(self) -> dict:
        """Rotación de la llave maestra (KMS simulado) y re-envoltura de todas las llaves de datos."""
        anterior = self.kms.version_activa
        nueva = self.kms.rotar()
        reenvueltos = 0
        for u in self.usuarios.values():
            u.pii = self.cifrador.reenvolver(u.pii)
            reenvueltos += 1
            if u.cuestionario_cifrado is not None:
                u.cuestionario_cifrado = self.cifrador.reenvolver(u.cuestionario_cifrado)
                reenvueltos += 1
        return {"version_anterior": anterior, "version_activa": nueva,
                "registros_reenvueltos": reenvueltos, "kms": self.kms.estado()}

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
        por_fid: dict[str, int] = {}
        for a in asignados:
            for asg in a["asignaciones"]:
                por_fid[asg["fideicomiso_id"]] = por_fid.get(asg["fideicomiso_id"], 0) + asg["monto_centavos"]
        comision_aporte = sum(a["comision_aporte_centavos"] for a in asignados)
        recargo = sum(a["recargo_medio_pago_centavos"] for a in asignados)
        ingresos_iya = comision_aporte + recargo

        # El banco fiduciario recibe: abono neto del adquirente + cobertura de la comisión de la
        # pasarela (la paga InvierteYa) - ingresos de InvierteYa (comisión de aporte + recargo).
        cobertura = liquidacion["total_comisiones"]
        abono = liquidacion["total_neto"] + cobertura - ingresos_iya
        self.fideicomiso.recibir_abono(fecha.isoformat(), abono, por_fid)

        n1 = conciliacion.nivel1_pagos_vs_liquidacion(del_dia, liquidacion)
        n2 = conciliacion.nivel2_aportes_vs_fideicomiso(
            por_fid, liquidacion["total_neto"], cobertura, ingresos_iya,
            self.fideicomiso.abonos_por_fideicomiso.get(fecha.isoformat(), {}))
        unidades: dict[str, Decimal] = {}
        tramos: dict[str, int] = {}
        for a in self.aportes.values():
            if a["estado"] == "ASIGNADO":
                for asg in a["asignaciones"]:
                    fid = asg["fideicomiso_id"]
                    unidades[fid] = unidades.get(fid, Decimal(0)) + Decimal(asg["unidades"])
                    tramos[fid] = tramos.get(fid, 0) + 1
        valores = {fid: f["valor_unidad"] for fid, f in self.catalogo.obtener().items()}
        n3 = conciliacion.nivel3_unidades_vs_custodia(unidades, self.fideicomiso.estado_posiciones(),
                                                      tramos, valores)

        excepciones = n1["excepciones"] + n2["excepciones"] + n3["excepciones"]
        # Propuesta de órdenes por fideicomiso (InvierteYa propone, el fiduciario aprueba)
        propuesta = self.fideicomiso.proponer_ordenes(por_fid)
        batch = self.fideicomiso.aprobar_y_ejecutar(propuesta)
        resultado = {"fecha": fecha.isoformat(), "conciliado": not excepciones,
                     "niveles": [n1, n2, n3], "excepciones": excepciones,
                     "aportes_por_fideicomiso": por_fid,
                     "ingresos_invierteya": {"comision_aporte_centavos": comision_aporte,
                                             "recargo_medio_pago_centavos": recargo,
                                             "costo_pasarela_centavos": cobertura,
                                             "margen_neto_centavos": ingresos_iya - cobertura},
                     "propuesta_ordenes": propuesta, "batch": batch,
                     "iso_cierre_pasarela": liquidacion["iso_cierre"], "ya_cerrado": False}
        self.cierres[fecha.isoformat()] = resultado
        return resultado
