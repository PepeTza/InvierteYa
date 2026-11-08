"""Demo en consola: la transacción de María de punta a punta (sirve de respaldo para el speech).

Uso:  python scripts/demo_maria.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.perfil import Cuestionario  # noqa: E402
from app.core.servicio import InvierteYa  # noqa: E402


def titulo(t):
    print(f"\n{'=' * 70}\n{t}\n{'=' * 70}")


def mostrar(aporte):
    print(f"Aporte {aporte['id']}  ${aporte['monto']}  ->  {aporte['estado']}")
    for e in aporte["eventos"]:
        print(f"   · {e['estado']:<18} {e['detalle']}")
    print("   ISO 8583 (tramo pasarela-suiche, SIMULADO):")
    for m in aporte["iso8583"]:
        print(f"     MTI {m['mti']}  {m['campos']}")
    print(f"   Mensaje al usuario: {aporte['mensaje']}")
    if aporte["leccion"]:
        print(f"   Tutor: «{aporte['leccion']['titulo']}» {aporte['leccion']['texto']}")


s = InvierteYa()
titulo("1. Registro, KYC simulado y cuestionario")
maria = s.registrar("María (dato sintético)", "maria@example.com")
s.aprobar_kyc(maria.id)
p = s.evaluar_perfil(maria.id, Cuestionario(
    edad=24, ingreso_rango=2, pct_invertible=15, horizonte_anios=2, objetivo="proteger",
    reaccion_caida_20="vender_todo", experiencia_previa=False, fondo_emergencia=False,
    dependientes=0, conocimiento=2))
print(f"Perfil: {p['perfil']} ({p['puntaje']}/{p['puntaje_maximo']}) — {p['explicacion']}")
print(f"Tutor: «{p['leccion']['titulo']}»")

titulo("2. Contrato de adhesión al fideicomiso")
r = s.firmar_adhesion(maria.id, True)
print(f"Adhesión {r['adhesion']} · Tutor: «{r['leccion']['titulo']}» {r['leccion']['texto']}")
token = s.pasarela.tokenizar("4111111111111111")   # tarjeta de PRUEBA
print(f"La pasarela tokenizó la tarjeta: {token} (InvierteYa nunca ve el PAN)")

titulo("3. Aporte de $20 aprobado (diagramas 1 y 2)")
s.pasarela.forzar("APROBADA")
mostrar(s.crear_aporte(maria.id, 2000, token, "demo-1"))

titulo("4. Pago rechazado por saldo insuficiente (código 51)")
s.pasarela.forzar("51")
mostrar(s.crear_aporte(maria.id, 3000, token, "demo-2"))

titulo("5. Timeout del emisor -> reverso automático (diagrama 3)")
s.pasarela.forzar("TIMEOUT")
mostrar(s.crear_aporte(maria.id, 1000, token, "demo-3"))

titulo("6. María toca dos veces 'Aportar' (idempotencia)")
s.pasarela.forzar("APROBADA")
a = s.crear_aporte(maria.id, 1500, token, "demo-4")
b = s.crear_aporte(maria.id, 1500, token, "demo-4")
print(f"Primer intento: {a['estado']} · Segundo: duplicado={b['duplicado']}, mismo aporte={a['id'] == b['id']}")

titulo("7. Portafolio de María")
port = s.portafolio(maria.id)
print(f"{port['unidades']} unidades x ${port['valor_unidad']} = ${port['saldo']}  {port['composicion']}")
print(f"Tutor: «{port['leccion']['titulo']}»")

titulo("8. Cierre del día: conciliación en 3 niveles y batch (diagrama 4)")
c = s.cerrar_dia(date.today())
for n in c["niveles"]:
    print(f"Nivel {n['nivel']}: {'cuadra' if n['cuadra'] else 'NO cuadra'}")
print("Propuesta de órdenes (InvierteYa propone, el fiduciario aprueba):")
for o in c["propuesta_ordenes"]:
    print(f"   {o['portafolio']:<12} {o['instrumento']:<11} ${o['monto_centavos'] / 100:,.2f}")
print(f"Batch: {c['batch']}")
