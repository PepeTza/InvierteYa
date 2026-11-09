# InvierteYa · Prototipo backend + front-end (Sesión 2)

Inversión fraccionada desde **$5** a través de un **fideicomiso** administrado por un banco,
con perfil de riesgo y **tutor didáctico**. Equipo D · Fintech con IA.

> **Todo lo externo está SIMULADO:** pasarela de pago, adquirente, suiche, emisor (ISO 8583),
> banco fiduciario, casa de bolsa y CVV. **Solo datos sintéticos**: nunca usar tarjetas reales.

## Cómo ejecutarlo

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    ·    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python -m pytest -v                  # 15 casos de prueba (base del plan de certificación)
python scripts/demo_maria.py         # transacción de María de punta a punta (respaldo del speech)
python scripts/kpis.py               # prueba de carga simulada -> docs/kpis_tablero.png
python scripts/generar_openapi.py    # regenera docs/openapi.yaml

uvicorn app.main:app --reload        # API en http://127.0.0.1:8000/docs (Swagger UI)
```

En Swagger UI, pulsar **Authorize** y escribir `demo-token` (autenticación simulada).
Orden sugerido para la demo: `POST /pasarela/v1/tokens` → `POST /v1/usuarios` → `/kyc` →
`/perfil` → `/adhesion` → `POST /v1/aportes` (encabezado `Idempotency-Key`) →
`GET /v1/usuarios/{id}/portafolio` → `POST /v1/operaciones/cierre`.
Con `POST /v1/demo/forzar-escenario` se fuerza el próximo resultado:
`APROBADA`, `51`, `05`, `59`, `TIMEOUT`, `FALLA_CAPTURA`, `REVERSO_SIN_RESPUESTA`.

Sin instalar nada, el archivo `docs/openapi.yaml` se puede ver pegándolo en https://editor.swagger.io

## Front-end navegable (React)

App móvil en React + TypeScript + Vite + Tailwind CSS (`frontend/`), conectada a la API real.
Flujo: bienvenida → registro → KYC → cuestionario (10 preguntas) → perfil + lección del tutor →
contrato de adhesión → tarjeta (formulario de la pasarela, solo devuelve un token) → aporte →
autorización/captura/asignación en vivo → portafolio.

La versión compilada (`frontend/dist`) está incluida en el repositorio, así que para **ver** la app
basta con el backend:

```bash
uvicorn app.main:app                 # la app queda en http://127.0.0.1:8000/app
```

Para **modificar** el front-end se necesita Node.js 20 o superior:

```bash
cd frontend
npm install
npm run build                        # regenera frontend/dist: correrlo antes de cada commit que cambie el front
```

Para desarrollar con recarga en caliente: deja `uvicorn` corriendo y en otra terminal
`cd frontend && npm run dev` → http://localhost:5173/app/ (reenvía `/v1` y `/pasarela` al puerto 8000).

En pantallas anchas se ve la app, el mapa del flujo y el **panel de demo** (para el presentador):
- **Vista Móvil / Web:** la misma app dentro de un teléfono o dentro de un navegador de escritorio
  (landing de dos columnas, asistente de registro centrado y portafolio tipo dashboard).
- Forzar el **próximo** resultado del pago (aprobada, 51, 05, 59, timeout, falla de captura).
- Responder el cuestionario como María, abrir Swagger y ejecutar el cierre del día (conciliación en 3 niveles).
- **Reiniciar recorrido:** borra el estado de la app y del servidor (`POST /v1/demo/reiniciar`).

En el celular, el panel se abre con el botón flotante.

> Antes del primer aporte de la demo, pulsa **Aprobada** en el panel: la pasarela simulada usa una
> semilla fija y su primera transacción aleatoria sale rechazada (51).

## Estructura

| Ruta | Qué hay |
|---|---|
| `app/core/servicio.py` | Orquestación del flujo (diagramas 1 a 4): validaciones, autorización, captura, asignación de unidades, reverso, idempotencia y cierre del día |
| `app/core/pasarela_simulada.py` | Pasarela aliada simulada: tokenización, latencias, rechazos (51, 05, 59), timeouts, reintentos 0421 y archivo de liquidación |
| `app/core/iso8583.py` | Mensajes ISO 8583 simulados (0100/0110, 0220/0230, 0400/0410/0421, 0500) |
| `app/core/fideicomiso.py` | Un fideicomiso con 3 portafolios, valor de unidad, propuesta de órdenes y aprobación del fiduciario |
| `app/core/conciliacion.py` | Conciliación en 3 niveles |
| `app/core/perfil.py` | Perfil de riesgo por reglas (también etiqueta el dataset sintético del modelo baseline) |
| `app/core/tutor.py` | Tutor con contenido predefinido (10 lecciones) y regla de selección |
| `app/api/esquemas.py`, `app/main.py` | API REST con FastAPI (genera OpenAPI 3); sirve el front-end compilado en `/app` |
| `frontend/src/screens/` | Pantallas del front-end (una por paso del flujo) |
| `frontend/src/components/` | Componentes de UI, visor ISO 8583 y panel de demo |
| `frontend/src/lib/api.ts` | Cliente de la API y de la pasarela simulada |
| `tests/test_flujo.py` | Casos de prueba CP-01 a CP-15 |
| `docs/` | `openapi.yaml`, `kpis.json`, `kpis_tablero.png`, salida de la demo |

## Decisiones de diseño (resumen)

- InvierteYa **no es la pasarela**: en la fase 1 usa una pasarela certificada; el PAN nunca llega a
  nuestros servidores (alcance PCI: SAQ A).
- La captura es inmediata y las unidades se asignan al confirmarse (unidades = monto / valor de la unidad
  del portafolio). La compra de títulos ocurre después, en un batch diario.
- **InvierteYa propone y el fiduciario aprueba** las órdenes por lote.
- Solo se reversa **antes** de asignar unidades; después, cualquier devolución es un rescate.
- El tutor **no** interviene en un rechazo de pago (no conocemos la causa real); ante sospecha de fraude
  (59) el mensaje es genérico.
- La pasarela liquida neto de comisión; **InvierteYa cubre la comisión** para que al fideicomiso llegue el
  100% de lo aportado (nivel 2 de conciliación).

## Supuestos a validar

Comisión de la pasarela (3%), límite de $1.000 por aporte, composición de los portafolios Moderado y
Agresivo, tasas de rechazo y latencias simuladas, y los campos ISO 8583 contra el estándar.
