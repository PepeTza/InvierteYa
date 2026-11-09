# InvierteYa — Contexto para la Sesión 2 (para continuar con Claude)

> **Cómo usar este archivo:** súbelo a una conversación nueva con Claude junto con
> `S1_EquipoD_Concepto` (documento de la Sesión 1) y las instrucciones del profesor (PDF).
> Luego escribe algo como: *"Lee el contexto y continuemos la Sesión 2 desde la sección
> 'Estado actual'."*

---

## 1. Datos clave

- **Cátedra:** Fintech con IA · **Docente:** José Leonardo González
- **Equipo D:** Jesus Sayago, Daniel Haro, Ronald Gomez, David Crespo
- **Línea D:** plataforma de inversión · **IA:** perfil de riesgo, recomendación de portafolio y tutor didáctico
- **Sesión 2 — Diseño transaccional y prototipo (20% de la nota)**
  - **Carga en el aula virtual: domingo 8-nov-2026 a las 23:59** (cada día de retraso descuenta 2 de 20 puntos)
  - Presentación: martes 10-nov-2026 · Speech de 12 min + 5 de preguntas
- **Nombre de los archivos:** `S2_EquipoD_<Entregable>.pdf` (ej.: `S2_EquipoD_Diseno.pdf`)
- Todo se carga en PDF, salvo el código, que va al repositorio Git compartido con el docente.

---

## 2. Cambios acordados a partir del feedback de la Sesión 1

### 2.1 Nuevo enfoque: "inversión asistida con IA didáctica"
- Seguimos ayudando a personas a quienes invertir se les hace difícil.
- La IA ya no solo recomienda dónde invertir según el perfil; también **enseña paso a paso** el mundo de las inversiones.
- La IA queda dividida en dos partes:
  1. **Clasificador de perfil de riesgo** (scikit-learn: árbol de decisión o regresión logística) → Conservador / Moderado / Agresivo + portafolio recomendado. **Es el baseline medible de esta entrega.**
  2. **Tutor didáctico con contenido PREDEFINIDO** (decisión tomada, sin LLM). Un catálogo de microlecciones que la IA selecciona según el perfil del usuario y el paso del flujo en que se encuentra (registro, cuestionario, primer aporte, ver portafolio, retiro). En la Sesión 2 basta con el diseño y una maqueta en el front-end.

### 2.2 Fideicomiso (sugerencia del profesor)
Resuelve el riesgo abierto de la Sesión 1 sobre la figura legal de la inversión fraccionada.
- **Fideicomitente/beneficiario:** cada usuario. **Fiduciario:** un banco aliado autorizado por SUDEBAN que administra el patrimonio.
  - ⚠️ **Confirmar con el profesor** si el fiduciario es un banco o la casa de bolsa.
- El dinero forma un **patrimonio autónomo**: no pertenece ni a InvierteYa ni al fiduciario.
- **Flujo:** el usuario aporta → el dinero entra a la cuenta del fideicomiso → el usuario recibe **unidades de participación** → el fideicomiso agrupa los aportes y da **órdenes por lotes** a la casa de bolsa → los títulos quedan en la CVV a nombre del fideicomiso.
- **Retiro = rescate de unidades**, que es una operación distinta del reverso.
- Hay que agregar el **banco fiduciario** al mapa de stakeholders y a los diagramas.

### 2.3 Pasarela de pago externa (aclaración importante)
- **InvierteYa NO es la pasarela.** Como startup, no tenemos dinero para certificaciones (PCI completo, homologación con el suiche). Por eso nos apoyamos **temporalmente en una pasarela de pago ya certificada** y buscamos independencia más adelante.
- **Consecuencias:**
  - El PAN se captura en el formulario/SDK de la pasarela; InvierteYa solo recibe un **token**. El alcance PCI baja a **SAQ A / SAQ A-EP**.
  - La "bóveda de tokens" de la Sesión 1 pasa a ser de la pasarela en la fase 1.
  - **Cadena:** Usuario → App InvierteYa → **Pasarela aliada** → Banco adquirente → **Suiche** → Banco emisor.
- **Dos tramos de mensajería en los diagramas:**
  1. InvierteYa ↔ Pasarela: **API REST/JSON**, especificada en **OpenAPI 3**.
  2. Pasarela ↔ Adquirente ↔ Suiche ↔ Emisor: **ISO 8583**, con una tabla de correspondencia entre campos de la API y campos ISO.
- No usar nombres de pasarelas reales salvo que el equipo lo valide; por defecto, "pasarela aliada".

---

## 3. Flujo transaccional propuesto (base para los diagramas de secuencia)

**Actores:** Usuario · App (React) · API Gateway · Backend InvierteYa (FastAPI) · Servicio de pagos · Pasarela aliada · Adquirente · Suiche · Emisor · Banco fiduciario (cuenta del fideicomiso) · Servicio de órdenes · Casa de bolsa · CVV · Motor IA.

### 3.1 Autorización
1. El usuario elige el monto (mín. \$5) en la app y la pasarela tokeniza la tarjeta.
2. El backend valida KYC, perfil, límites y antifraude básico, y crea un `aporte` en estado `PENDIENTE` con una clave de idempotencia.
3. El servicio de pagos llama `POST /authorizations` a la pasarela.
4. La pasarela envía una **0100** al adquirente → suiche → emisor y recibe la **0110** (campo 39 = `00` si se aprueba).
5. El aporte pasa a `AUTORIZADO`.

### 3.2 Captura
6. Inmediatamente después se llama `POST /captures`. Con el fideicomiso **no hay que esperar a que se ejecute la orden en la BVC**, porque eso se resolvía como problema de la Sesión 1. El adquirente liquida al día siguiente por clearing.
7. Se acredita el aporte en la cuenta del fideicomiso → **asignación de unidades** al usuario → el aporte pasa a `CAPTURADO`/`ASIGNADO`.
8. **Proceso separado (batch diario):** el fideicomiso consolida los aportes y envía órdenes a la casa de bolsa, que ejecuta en la BVC y registra en la CVV.

### 3.3 Reverso
- **Casos:** timeout sin respuesta del emisor; error al capturar o asignar después de una autorización aprobada; duplicado detectado por idempotencia.
- InvierteYa llama `POST /reversals` y la pasarela envía **0400/0410** (o **0420** como aviso), con el **campo 90** (datos de la transacción original).
- Solo se reversa **antes de asignar las unidades**. Después de eso, cualquier devolución es un **rescate**.

### 3.4 Conciliación (diaria, en tres niveles)
1. **Pagos vs. archivo de liquidación de la pasarela/suiche:** monto, RRN (campo 37), código de autorización (campo 38).
2. **Aportes capturados vs. saldo de la cuenta del fideicomiso** en el banco fiduciario.
3. **Unidades asignadas vs. posiciones custodiadas en la CVV** (estado de cuenta de la casa de bolsa).
- Las diferencias van a una cola de excepciones para revisión manual o reverso automático.

---

## 4. Mapeo ISO 8583 (borrador)

| Concepto | API InvierteYa ↔ Pasarela | ISO 8583 |
|---|---|---|
| Autorización | `POST /authorizations` | MTI 0100 / 0110 |
| Captura | `POST /captures` | 0220 (aviso de completación) o clearing por lote |
| Reverso | `POST /reversals` | 0400 / 0410 (0420 aviso) |
| Cierre / conciliación | `GET /settlements/{fecha}` | 0500 / 0510 (reconciliación) |
| PAN | (nunca lo tocamos: token) | Campo 2 |
| Código de proceso | `operation` | Campo 3 |
| Monto | `amount` | Campo 4 |
| Fecha/hora de transmisión | `timestamp` | Campo 7 |
| Número de traza | `trace_id` | Campo 11 (STAN) |
| Referencia de recuperación | `reference` | Campo 37 (RRN) |
| Código de autorización | `auth_code` | Campo 38 |
| Código de respuesta | `status` / `response_code` | Campo 39 (`00` aprobada, `05` no honrar, `51` fondos insuficientes, `91` emisor no disponible) |
| Terminal / comercio | `merchant_id` | Campos 41 / 42 |
| Moneda | `currency` | Campo 49 (USD = 840, VES = 928) |
| Datos originales (reverso) | `original_reference` | Campo 90 |

> Verificar cada campo contra una fuente primaria (estándar ISO 8583:1987) antes de entregar y citarla.

---

## 5. Checklist de entregables de la Sesión 2 (rúbrica: 10 pts técnico + 4 presentación + 6 individual)

| # | Entregable | Pts | Estado |
|---|---|---|---|
| 1 | Diagramas de secuencia: autorización, captura, reverso, conciliación (con el rol del suiche y cada actor) + mapeo ISO 8583 | 2,5 | ✅ diagramas / ⬜ tabla ISO final |
| 2 | API OpenAPI 3 + backend simulado (FastAPI + pasarela/suiche mock) en Git | 2,5 | ✅ código en `invierteya.zip` / ✅ probado en Swagger con un aporte real y un cierre que concilia / ⬜ subir a Git |
| 3 | Front-end navegable (registro → cuestionario → perfil + lección del tutor → aporte → portafolio) | 1,5 | ⬜ |
| 4 | Plan de certificación (fase 1 con pasarela / fase 2 independencia; actores; casos de prueba) | 1,5 | ⬜ |
| 5 | Tablero de KPIs medidos en el prototipo: tasa de aprobación, latencia p95, TPS, tasa de reversos | 1 | ✅ `docs/kpis_tablero.png` |
| 6 | Baseline de IA: dataset sintético (~5.000 usuarios) documentado + modelo + métricas | 1 | ✅ `ia/`, `docs/ia/`, `S2_EquipoD_BaselineIA.pdf` |
| 7 | Bitácora de uso de IA (ver `BITACORA_IA_S2.md`) | (incl. en 6) | 🟡 filas del baseline listas; faltan nombres del 7-nov, SAST/SCA y las tareas que sigan |
| 8 | Láminas: 12 a 15, en PDF | 4 (presentación) | ⬜ |
| 9 | Guion del speech (quién habla, en qué lámina, mensaje clave). **Hablan todos y el rol rota respecto a la Sesión 1** | — | ⬜ |

### 5.1 Plan de certificación (idea base)
- **Fase 1 (con pasarela):** certificación de la integración con la pasarela (casos de prueba en su sandbox); PCI-DSS 4.0 con SAQ A/A-EP; autorización SUDEBAN (normativa fintech) y alianza SUNAVAL con la casa de bolsa; contrato de fideicomiso con el banco fiduciario.
- **Fase 2 (independencia):** conexión directa con el adquirente, homologación con el suiche, PCI de nivel superior y bóveda de tokens propia.
  - **Disparador sugerido:** cuando las comisiones de la pasarela superen el costo anual de certificarse.
- **Casos de prueba mínimos:** aprobada, rechazada (05, 51), timeout → reverso automático, reverso duplicado (idempotencia), captura sin autorización (debe fallar), conciliación con descuadre.

### 5.2 KPIs
El mock de la pasarela debe simular latencias y una proporción de rechazos y timeouts. Se corre un script de carga (ej.: 1.000 transacciones) y se calculan:
- tasa de aprobación;
- latencia p95;
- TPS;
- tasa de reversos.

Se presentan en una página o lámina tipo dashboard.

### 5.3 Baseline de IA
- **Las 10 variables de la ficha de la Sesión 1:** edad, rango de ingreso, % invertible, horizonte, objetivo, reacción a una caída del 20%, experiencia, fondo de emergencia, dependientes, conocimiento.
- La etiqueta se asigna con un puntaje de reglas + ruido.
- **Métricas objetivo:**
  - exactitud ≥ 85%;
  - F1 por clase ≥ 0,80;
  - **0 casos de Conservador clasificado como Agresivo**.
- **Reglas de seguridad:**
  - sin fondo de emergencia, nunca Agresivo;
  - probabilidad < 60% → revisión humana.
- **Tutor predefinido:** tabla de lecciones (`id`, `paso_del_flujo`, `perfil`, `nivel`, `texto`) + regla de selección.

---

## 6. Correcciones pendientes de la Sesión 1 (cuentan para la nota de la Sesión 4)
- Inconsistencia del SOM: la tabla dice **12.870 usuarios**, pero el ejemplo del speech usa 20.000. Unificar (con 12.870 × \$20 × 12 ≈ **\$3,09 millones/año**).
- Las comisiones siguen marcadas como "[validar]": compararlas con tarifarios de casas de bolsa locales y agregar la comisión de la pasarela a la estructura de costos.
- Actualizar el mapa de stakeholders y el diagrama C4: **+ pasarela aliada, + banco fiduciario/fideicomiso**; quitar la bóveda propia en la fase 1.
- Actualizar la propuesta de valor con la IA didáctica.

---

## 7. Estructura sugerida del speech (12 min) — recorrer UNA transacción de María
1. **Apertura (1 min):** María tiene \$30 y no sabe invertir; recordar los cambios tras el feedback (fideicomiso, pasarela, IA didáctica).
2. **Recorrido del usuario (2 min):** demo del front-end, cuestionario y tutor.
3. **Cuerpo técnico (6–7 min):** autorización → captura → asignación de unidades → orden por lotes → reverso (caso de timeout) → conciliación en tres niveles; API e ISO 8583.
4. **Certificación y KPIs (1–2 min).**
5. **IA (1 min):** baseline y métricas.
6. **Cierre (1 min):** riesgos abiertos y siguiente paso (MVP de la Sesión 3).

---

## 8. Reglas del profesor que no hay que olvidar
- El uso de IA es obligatorio y debe declararse en la bitácora. **Si no se declara, se penaliza con el 50% del entregable técnico.**
- Todo dato o cifra obtenido con IA se valida contra una fuente primaria y se cita.
- Solo se usan datos sintéticos; nunca tarjetas reales ni datos personales en herramientas de IA.
- El código generado con IA se pasa por SAST/SCA antes de integrarlo.
- Cada integrante debe poder explicar todo lo que se entrega.
- Las funciones simuladas se indican como "simulado" en las láminas.

---

## 9. Estado actual (actualizar al final de cada sesión de trabajo)
- **Sábado 7-nov, 22:50.** Se discutió el feedback y se tomaron las decisiones de la sección 2:
  - tutor **predefinido**;
  - el equipo hará el trabajo él mismo.
- **Sábado 7-nov, 23:15. Diagramas 1 y 2 listos** (fuente Mermaid en `diagramas/*.mmd`, PNG para las láminas y copia editable en Lucidchart):
  - Diagrama 1, Autorización (v2): https://lucid.app/lucidchart/d5584416-555a-4f63-a30f-2d5be0b29c92/edit
  - Diagrama 2 (v2), Captura + asignación de unidades + orden por lotes: https://lucid.app/lucidchart/d0c03ba5-e02a-4ec5-bcee-20dff6e1e66a/edit
  - Diagrama 3, Reverso (duplicado por idempotencia; timeout o falla → 0400/0410; sin respuesta → 3 reintentos 0421 y cola de excepciones): https://lucid.app/lucidchart/95e4de31-5803-4a18-8229-d7001e1f02d3/edit
  - Diagrama 4, Conciliación en tres niveles (T+1, 6:00 am; excepciones resueltas por un analista: devolución /refunds, reclamo a la pasarela o ajuste con doble aprobación): https://lucid.app/lucidchart/4de3b48d-be8a-4b4a-b981-7ac12f9a4a7c/edit
  - Quedaron obsoletas en Lucid: la v1 del diagrama 1 (fd30d269…) y la v1 del diagrama 2 (9be0a5f1…).
- **Modelo con el banco fiduciario (decidido el 7-nov, 23:20):**
  - **InvierteYa va al banco** y negocia UNA vez (modelo B2B2C): convenio de alianza + contrato marco del fideicomiso (política de inversión, portafolios, límites, reparto de comisiones). El banco gana clientes, comisiones y canal digital.
  - **Operación diaria automática:** en el registro, después del KYC, el usuario firma digitalmente un **contrato de adhesión** al fideicomiso. El banco también lo acepta como cliente (sigue siendo responsable de la prevención de LC/FT; se le envía el resultado del KYC). Cada día InvierteYa envía por API o archivo las nuevas adhesiones, los aportes y la propuesta de órdenes por lote.
  - **InvierteYa propone y el fiduciario aprueba** (separación de funciones / "cuatro ojos"). La aprobación puede ser automática por reglas, con revisión humana solo de las excepciones. Si se rechaza una propuesta, el dinero queda en efectivo en el fideicomiso y la orden se corrige al día siguiente.
  - **Fase 1: un banco y UN fideicomiso con tres portafolios** (Conservador, Moderado, Agresivo), cada uno con su propio valor de unidad. El cambio de perfil se resuelve con un **traspaso** entre portafolios dentro del fideicomiso. **Fase 2:** sumar un segundo banco fiduciario para reducir la dependencia.
  - ⚠️ Validar con el profesor: viabilidad del fideicomiso colectivo con adhesión digital y procedimiento de sustitución del fiduciario.
  - El front-end debe mostrar el paso "firma del contrato de adhesión" en el registro.
- **Decisiones tomadas en esta sesión:**
  - Timeout de autorización: **30 s** → reverso automático.
  - **El tutor NO aparece cuando se rechaza un pago** (no sabemos la causa real). En su lugar va un mensaje según el código de respuesta; los rechazos por sospecha de fraude muestran un mensaje genérico.
  - El tutor aparece en momentos didácticos: fin del cuestionario, antes del primer aporte, **al asignar las unidades** (diagrama 2), en el portafolio y antes de un rescate.
  - Las unidades se calculan como monto / valor de la unidad del portafolio (ej.: \$20 / \$1,25 = 16) y se asignan al confirmarse la captura.
  - El adquirente liquida en T+1 a la cuenta del fideicomiso; la conciliación de nivel 2 verifica ese abono.
  - El batch diario lo **aprueba el fiduciario** antes de instruir a la casa de bolsa (InvierteYa solo propone).
- **Sábado 7-nov, 23:45. Backend simulado listo** (`invierteya.zip`; el detalle está en su README):
  - Python puro + FastAPI. **15 pruebas pasan** (se agregó CP-15: el cierre de un día corre una sola vez) (CP-01 a CP-14: aprobada, rechazos 51/59, PAN nunca llega, timeout→reverso, falla de captura, reverso sin respuesta→excepción, idempotencia, captura sin autorización, monto mínimo, sin adhesión, regla "sin fondo de emergencia nunca Agresivo", conciliación que cuadra y que detecta descuadre). **Estos casos son la base del plan de certificación.**
  - `docs/openapi.yaml` (15 rutas) generado desde los mismos esquemas Pydantic; con FastAPI instalado, Swagger en `/docs` (token `demo-token`).
  - **KPIs (1.000 aportes simulados, 20 workers):** aprobación 88,0% · latencia p95 1.259 ms (p50 699 ms) · 13,8 TPS · reversos 2,2%. Gráfico en `docs/kpis_tablero.png`.
  - `scripts/demo_maria.py`: demo en consola de punta a punta (respaldo si falla la demo en vivo).
  - El perfil hoy se asigna **por reglas** (`app/core/perfil.py`); esa misma regla + ruido etiqueta el dataset del baseline de IA. Cuando exista el modelo, se conecta en `evaluar_perfil`.
  - ✅ Confirmado en Windows (Python 3.13, 7-nov 23:56): las pruebas pasan y `uvicorn` levanta sin errores. **Usar Python 3.13**: con 3.15 fallan las dependencias. En PowerShell hay que habilitar scripts una vez: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- **Decisión de negocio derivada:** la pasarela liquida neto de su comisión (supuesto 3%) e **InvierteYa cubre esa comisión** para que al fideicomiso llegue el 100% del aporte.
  - ⚠️ **Riesgo de viabilidad:** la comisión por operación de InvierteYa (1%, Sesión 1) es menor que la de la pasarela, así que cada aporte con tarjeta deja pérdida. Hay que revisarlo (subir comisión, cobrar un cargo fijo o promover medios más baratos).
- **Domingo 8-nov, 00:30. Cierre de la sesión de trabajo del sábado.** Todo el código y los diagramas están en el **repositorio de GitHub** (carpeta `docs/diagramas`). Probado en Swagger: un aporte real quedó ASIGNADO y el cierre concilió en los 3 niveles.

- **Domingo 8-nov, 21:10. Baseline de IA listo** (Daniel + Claude):
  - Dataset sintético: 5.000 usuarios (`data/dataset_sintetico.csv`), etiquetado con `perfil.py` + ruido (desv. 0,75) + regla del fondo de emergencia. Distribución: 28% Conservador · 62% Moderado · 10% Agresivo. Ficha en `docs/ia/DATASET.md`.
  - Modelo elegido: **regresión logística** (frente al árbol de decisión, que no llegó a F1 de 0,80 en Agresivo). En prueba: **exactitud 89,7% · F1 0,87/0,92/0,83 · 0 Conservador→Agresivo · AUC 0,978**. Estable con 5 semillas (media de 90,8%). Sin sesgo grueso por edad ni ingreso.
  - Conectado en `evaluar_perfil`: probabilidad < 60% → revisión de un asesor con perfil provisional más conservador; si no hay modelo, se usan las reglas. La API devuelve `probabilidad`, `probabilidades`, `revision_humana` y `perfil_reglas`.
  - **21 pruebas pasan** (CP-16 a CP-21 nuevas en `tests/test_ia.py`). Para las láminas: `docs/ia/matriz_confusion.png` e `importancia_variables.png`.
  - Cómo subirlo: `docs/GUIA_SUBIDA_GITHUB.md`.

### Cómo retomar
1. Clonar el repositorio y seguir el README (Python **3.13**, entorno virtual, `pip install -r requirements.txt`, `python -m pytest`).
2. En una conversación nueva con Claude, subir: **este archivo**, el documento de la Sesión 1 y el PDF de instrucciones del profesor. Pedir: *"Lee el contexto y continuemos la Sesión 2 desde 'Lo que falta'"*.
3. Al terminar cada tarea: actualizar esta sección y agregar una fila a la bitácora.

### Lo que falta (carga: domingo 8-nov, 23:59)
| # | Tarea | Pts | Insumos ya disponibles |
|---|---|---|---|
| A | ✅ **Baseline de IA — HECHO (8-nov, 21:10).** Ver `docs/ia/MODELO.md` | 1 | — |
| B | **Front-end navegable:** registro → KYC → cuestionario → perfil + lección → firma de adhesión → aporte → portafolio. Puede ser maqueta HTML/React que llame a la API o con datos fijos | 1,5 | Endpoints en `/docs`; textos del tutor en `app/core/tutor.py` |
| C | **Plan de certificación:** fase 1 (pasarela, SAQ A, SUDEBAN, SUNAVAL, contrato con el fiduciario) y fase 2 (independencia); actores; **casos de prueba = CP-01 a CP-15** de `tests/test_flujo.py` | 1,5 | Sección 5.1 |
| D | **Tabla ISO 8583 para las láminas**, validada contra una fuente primaria y citada | (diagramas) | Sección 4 y `app/core/iso8583.py` |
| E | **Capturas de Swagger** (`/docs`, respuesta de `POST /v1/aportes`, cierre) | — | Correr `python -m uvicorn app.main:app` **sin** `--reload` |
| F | **Láminas (12 a 15, PDF)** + **guion** (hablan los 4; rotar roles respecto a la Sesión 1). Incluir el mapa de stakeholders y el C4 actualizados con la pasarela y el banco fiduciario. Marcar como "simulado" lo que lo sea | 4 (pres.) | Diagramas PNG, `docs/kpis_tablero.png`, `scripts/demo_maria.py`, sección 7 |
| G | **Bitácora:** poner nombres, completar validaciones y exportar a PDF | — | `BITACORA_IA_S2.md` |

### Avisos para la demo del martes
- Los datos viven **en memoria**: si se reinicia el servidor, se pierden (incluidos los tokens). Hacer el recorrido completo de una vez.
- El cierre de un día corre **una sola vez** (`"ya_cerrado": true` al repetir).
- Tener `python scripts/demo_maria.py` como respaldo si falla la conexión.
