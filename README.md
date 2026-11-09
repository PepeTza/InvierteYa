# InvierteYa · Prototipo backend + front-end (Sesión 2)

Inversión fraccionada desde **$5** a través de un **fideicomiso** administrado por un banco,
con perfil de riesgo **por IA (modelo baseline)** y **tutor didáctico**. Equipo D · Fintech con IA.

> **Todo lo externo está SIMULADO:** pasarela de pago, adquirente, suiche, emisor (ISO 8583),
> banco fiduciario, casa de bolsa y CVV. **Solo datos sintéticos**: nunca usar tarjetas reales.

## Inicio rápido: ver la demo

Requiere Python 3.13 o 3.14. No hace falta Node: el front-end compilado ya está en el repositorio.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    ·    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app
```

Abrir **http://127.0.0.1:8000/app** (la app) o **http://127.0.0.1:8000/docs** (Swagger UI).

> Para la demo en vivo conviene correr `uvicorn` **sin** `--reload`: en Windows la recarga automática
> a veces se queda trabada. Los datos viven en memoria; si se reinicia el servidor, se pierden.

## Backend: IA, pruebas y scripts

```bash
python ia/generar_dataset.py         # dataset sintético de 5.000 usuarios -> data/
python ia/entrenar.py                # entrena el modelo de perfil -> ia/modelo_perfil.joblib + docs/ia/
python -m pytest -v                  # 21 casos de prueba (CP-01 a CP-21)
python scripts/demo_maria.py         # transacción de María de punta a punta (respaldo del speech)
python scripts/kpis.py               # prueba de carga simulada -> docs/kpis_tablero.png
python scripts/generar_openapi.py    # regenera docs/openapi.yaml
```

En Swagger UI, pulsar **Authorize** y escribir `demo-token` (autenticación simulada).
Orden sugerido: `POST /pasarela/v1/tokens` → `POST /v1/usuarios` → `/kyc` → `/perfil` → `/adhesion` →
`POST /v1/aportes` (encabezado `Idempotency-Key`) → `GET /v1/usuarios/{id}/portafolio` →
`POST /v1/operaciones/cierre`.

Endpoints solo para la demo:
- `POST /v1/demo/forzar-escenario?escenarios=…` fuerza el resultado de las próximas operaciones de la
  pasarela: `APROBADA`, `51`, `05`, `59`, `TIMEOUT`, `FALLA_CAPTURA`, `REVERSO_SIN_RESPUESTA`.
  Con `reemplazar=true` se vacía la cola antes de agregar.
- `POST /v1/demo/reiniciar` borra usuarios, aportes, cierres y escenarios forzados.

Sin instalar nada, `docs/openapi.yaml` se puede ver pegándolo en https://editor.swagger.io

## Front-end navegable (React)

React + TypeScript + Vite + Tailwind CSS (`frontend/`), conectado a la API real. Todas las decisiones
(perfil, resultado del pago, unidades) las toma el backend; el front-end solo las muestra.

**Flujo:** bienvenida → registro → KYC → cuestionario de 10 preguntas → perfil ("¿Por qué este perfil?"
y lección del tutor) → contrato de adhesión → tarjeta (formulario de la pasarela; InvierteYa solo recibe
un token) → aporte con monto libre de $5 a $1.000 → autorización, captura y asignación en vivo, con visor
de mensajes ISO 8583 → portafolio.

**Dos vistas** de la misma app (selector en el panel de demo):
- **Móvil:** la app dentro de un teléfono.
- **Web:** la app dentro de un navegador de escritorio: landing de dos columnas, registro con columna
  lateral de pasos y portafolio tipo dashboard (indicadores, composición con montos y tabla de actividad).

**Panel de demo** (para el presentador; no forma parte de la app):
- Forzar el **próximo** resultado del pago: aprobada (00), fondos insuficientes (51), no honrar (05),
  sospecha de fraude (59), timeout → reverso, falla de captura → reverso. El número es el código de
  respuesta del banco emisor (ISO 8583, campo 39).
- Responder el cuestionario como María y abrir Swagger.
- Ejecutar el cierre del día (conciliación en 3 niveles y órdenes por lote).
- **Reiniciar recorrido:** borra el estado de la app y del servidor.

En el celular, el panel se abre con el botón flotante.

> Antes del primer aporte de la demo, pulsa **Aprobada** en el panel: la pasarela simulada usa una
> semilla fija y su primera transacción aleatoria sale rechazada (51).

### Modificar el front-end

Requiere Node.js 20 o superior.

```bash
cd frontend
npm install
npm run build        # regenera frontend/dist: correrlo antes de cada commit que cambie el front-end
```

Para desarrollar con recarga en caliente: deja `uvicorn` corriendo y en otra terminal
`cd frontend && npm run dev` → http://localhost:5173/app/ (reenvía `/v1` y `/pasarela` al puerto 8000).

## Estructura

| Ruta | Qué hay |
|---|---|
| `app/core/servicio.py` | Orquestación del flujo (diagramas 1 a 4): validaciones, autorización, captura, asignación de unidades, reverso, idempotencia y cierre del día |
| `app/core/pasarela_simulada.py` | Pasarela aliada simulada: tokenización, latencias, rechazos (51, 05, 59), timeouts, aviso de reverso 0420 con repeticiones 0421 y archivo de liquidación |
| `app/core/iso8583.py` | Mensajes ISO 8583 simulados (0100/0110, 0220/0230, 0400/0410, 0420/0421, 0500); mapeo verificado en `docs/API_ISO8583.md` |
| `app/core/fideicomiso.py` | Un fideicomiso con 3 portafolios, valor de unidad, propuesta de órdenes y aprobación del fiduciario |
| `app/core/conciliacion.py` | Conciliación en 3 niveles |
| `app/core/perfil.py` | Puntaje de idoneidad por reglas: etiqueta el dataset, explica el perfil (texto y factores que suben o moderan la tolerancia) y es el respaldo si no hay modelo |
| `ia/generar_dataset.py` | Dataset sintético de 5.000 usuarios (10 variables + etiqueta con ruido) |
| `ia/entrenar.py` | Compara árbol de decisión y regresión logística, elige, mide y guarda el modelo |
| `ia/predictor.py` | Usa el modelo en la API: reglas de seguridad + revisión humana si la probabilidad es < 60% |
| `data/dataset_sintetico.csv` | El dataset (100% sintético) |
| `app/core/tutor.py` | Tutor con contenido predefinido (10 lecciones) y regla de selección |
| `app/api/esquemas.py`, `app/main.py` | API REST con FastAPI (genera OpenAPI 3); sirve el front-end compilado en `/app` |
| `frontend/src/screens/` | Pantallas del front-end (una por paso del flujo; cada una se adapta a móvil y web) |
| `frontend/src/components/` | Componentes de UI, visor ISO 8583 y panel de demo |
| `frontend/src/lib/` | Cliente de la API y de la pasarela simulada, preguntas del cuestionario y datos de los portafolios |
| `frontend/dist/` | Front-end compilado (lo que sirve FastAPI) |
| `tests/test_flujo.py` | Casos de prueba CP-01 a CP-15 (flujo transaccional) |
| `tests/test_ia.py` | Casos de prueba CP-16 a CP-21 (baseline de IA) |
| `docs/` | `openapi.yaml`, `kpis.json`, `kpis_tablero.png`, salida de la demo |
| `docs/ia/` | `DATASET.md`, `MODELO.md`, `metricas.json`, matriz de confusión e importancia de variables |
| `docs/diagramas/` | Diagramas de secuencia 1 a 4 (Mermaid + PNG) |
| `docs/equipo/` | Contexto de la Sesión 2 y bitácora de uso de IA |
| `docs/GUIA_SUBIDA_GITHUB.md` | Paso a paso para subir los cambios al repositorio |

## Baseline de IA (resumen)

Modelo: **regresión logística multinomial** (scikit-learn), entrenado con 5.000 usuarios **sintéticos**.
En el 20% de prueba: **exactitud 89,7%**, **F1 por clase 0,87 / 0,92 / 0,83**, **0 Conservadores
clasificados como Agresivos** y AUC de 0,978. Cumple las metas de la ficha de IA de la Sesión 1.
Reglas que el modelo no puede saltarse: sin fondo de emergencia nunca Agresivo; probabilidad < 60% →
revisión de un asesor (con perfil provisional más conservador). Detalle en `docs/ia/MODELO.md`.

## Decisiones de diseño (resumen)

- InvierteYa **no es la pasarela**: en la fase 1 usa una pasarela certificada; el PAN nunca llega a
  nuestros servidores (alcance PCI: SAQ A).
- La captura es inmediata y las unidades se asignan al confirmarse (unidades = monto / valor de la unidad
  del portafolio). La compra de títulos ocurre después, en un batch diario.
- **InvierteYa propone y el fiduciario aprueba** las órdenes por lote.
- Solo se reversa **antes** de asignar unidades; después, cualquier devolución es un rescate.
- El tutor aparece en momentos didácticos: fin del cuestionario, antes del primer aporte, al asignar
  unidades, en el portafolio y antes de un rescate.
- El tutor **no** interviene en un rechazo de pago (no conocemos la causa real); ante sospecha de fraude
  (59) el mensaje es genérico.
- La pasarela liquida neto de comisión; **InvierteYa cubre la comisión** para que al fideicomiso llegue el
  100% de lo aportado (nivel 2 de conciliación).
- Cada intento de aporte usa una **clave de idempotencia** nueva: si la red reintenta, no se cobra dos veces.
- La pregunta de dependientes se plantea como **"¿Cómo es tu hogar?"** (personas a cargo), no como tamaño
  del grupo familiar: convivir con alguien no es lo mismo que mantenerlo.

## Supuestos a validar

Comisión de la pasarela (3%), límite de $1.000 por aporte, composición de los portafolios Moderado y
Agresivo, tasas de rechazo y latencias simuladas, los campos ISO 8583 contra el estándar, las
distribuciones, puntajes y cortes del dataset sintético (validar con un asesor de inversiones) y los rangos
de ingreso del cuestionario (menos de $200, $200 a $500, $500 a $1.000, $1.000 a $2.500, más de $2.500).
