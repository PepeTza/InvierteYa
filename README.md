# InvierteYa · Prototipo backend (Sesión 2)

Inversión fraccionada desde **$5** a través de un **fideicomiso** administrado por un banco,
con perfil de riesgo **por IA (modelo baseline)** y **tutor didáctico**. Equipo D · Fintech con IA.

> **Todo lo externo está SIMULADO:** pasarela de pago, adquirente, suiche, emisor (ISO 8583),
> banco fiduciario, casa de bolsa y CVV. **Solo datos sintéticos**: nunca usar tarjetas reales.

## Cómo ejecutarlo

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    ·    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python ia/generar_dataset.py         # dataset sintético de 5.000 usuarios -> data/
python ia/entrenar.py                # entrena el modelo de perfil -> ia/modelo_perfil.joblib + docs/ia/
python -m pytest -v                  # 21 casos de prueba (CP-01 a CP-21)
python scripts/demo_maria.py         # transacción de María de punta a punta (respaldo del speech)
python scripts/kpis.py               # prueba de carga simulada -> docs/kpis_tablero.png
python scripts/generar_openapi.py    # regenera docs/openapi.yaml

python -m uvicorn app.main:app      # API en http://127.0.0.1:8000/docs (Swagger UI)
```

En Swagger UI, pulsar **Authorize** y escribir `demo-token` (autenticación simulada).
Orden sugerido para la demo: `POST /pasarela/v1/tokens` → `POST /v1/usuarios` → `/kyc` →
`/perfil` → `/adhesion` → `POST /v1/aportes` (encabezado `Idempotency-Key`) →
`GET /v1/usuarios/{id}/portafolio` → `POST /v1/operaciones/cierre`.
Con `POST /v1/demo/forzar-escenario` se fuerza el próximo resultado:
`APROBADA`, `51`, `05`, `59`, `TIMEOUT`, `FALLA_CAPTURA`, `REVERSO_SIN_RESPUESTA`.

Sin instalar nada, el archivo `docs/openapi.yaml` se puede ver pegándolo en https://editor.swagger.io

## Estructura

| Ruta | Qué hay |
|---|---|
| `app/core/servicio.py` | Orquestación del flujo (diagramas 1 a 4): validaciones, autorización, captura, asignación de unidades, reverso, idempotencia y cierre del día |
| `app/core/pasarela_simulada.py` | Pasarela aliada simulada: tokenización, latencias, rechazos (51, 05, 59), timeouts, reintentos 0421 y archivo de liquidación |
| `app/core/iso8583.py` | Mensajes ISO 8583 simulados (0100/0110, 0220/0230, 0400/0410/0421, 0500) |
| `app/core/fideicomiso.py` | Un fideicomiso con 3 portafolios, valor de unidad, propuesta de órdenes y aprobación del fiduciario |
| `app/core/conciliacion.py` | Conciliación en 3 niveles |
| `app/core/perfil.py` | Puntaje de idoneidad por reglas: etiqueta el dataset, explica el perfil y es el respaldo si no hay modelo |
| `ia/generar_dataset.py` | Dataset sintético de 5.000 usuarios (10 variables + etiqueta con ruido) |
| `ia/entrenar.py` | Compara árbol de decisión y regresión logística, elige, mide y guarda el modelo |
| `ia/predictor.py` | Usa el modelo en la API: reglas de seguridad + revisión humana si la probabilidad es < 60% |
| `data/dataset_sintetico.csv` | El dataset (100% sintético) |
| `app/core/tutor.py` | Tutor con contenido predefinido (10 lecciones) y regla de selección |
| `app/api/esquemas.py`, `app/main.py` | API REST con FastAPI (genera OpenAPI 3) |
| `tests/test_flujo.py` | Casos de prueba CP-01 a CP-15 (flujo transaccional) |
| `tests/test_ia.py` | Casos de prueba CP-16 a CP-21 (baseline de IA) |
| `docs/` | `openapi.yaml`, `kpis.json`, `kpis_tablero.png`, salida de la demo |
| `docs/ia/` | `DATASET.md`, `MODELO.md`, `metricas.json`, matriz de confusión e importancia de variables |
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
- El tutor **no** interviene en un rechazo de pago (no conocemos la causa real); ante sospecha de fraude
  (59) el mensaje es genérico.
- La pasarela liquida neto de comisión; **InvierteYa cubre la comisión** para que al fideicomiso llegue el
  100% de lo aportado (nivel 2 de conciliación).

## Supuestos a validar

Comisión de la pasarela (3%), límite de $1.000 por aporte, composición de los portafolios Moderado y
Agresivo, tasas de rechazo y latencias simuladas, los campos ISO 8583 contra el estándar, y las
distribuciones, puntajes y cortes del dataset sintético (validar con un asesor de inversiones).
