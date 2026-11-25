# Plan de Trabajo · Sesión 3 (MVP Seguro con IA Integrada)

**InvierteYa · Equipo D** (Daniel Haro, Jesús Sayago, David Crespo, Ronald Gómez)  
**Carga en aula virtual:** domingo 29-nov-2026, 23:59 (retraso: −2 pts/día)  
**Presentación:** martes 1-dic-2026 (15 min con demo + 5 min preguntas · peso **30%**)

> **Objetivo de este documento:** dividir la Sesión 3 en **4 tracks paralelos con archivos separados**
> para que cada integrante aporte commits verificables en su propia rama Git (coevaluación) sin
> conflictos de merge. Todos trabajan contra el contrato congelado en `docs/equipo/CONTRATO_API_S3.md`.

---

## 1. Mapa de rúbrica y respuesta a los 6 comentarios de la Sesión 2

| Criterio de evaluación | Pts | Comentarios S2 que atiende | Responsable principal |
|---|---|---|---|
| MVP construido/simulado con demo del flujo principal | 2,5 | #1 (catálogo fideicomisos), #4 (cuestionario en 2 tandas) | **Jesús** (backend) + **David** (front-end) |
| IA integrada, evaluada con métricas y Model Card | 3,0 | #2 (IA predictiva: abandono + flujos), #4 (confianza) | **Daniel** |
| DevSecOps y codificación segura | 2,0 | #5 (seguridad y registro Res. SUDEBAN 001.21) | **Ronald** |
| Cifrado y protección de datos sensibles (+ arquitectura de datos) | 1,5 | #6 (3 capas Bronce/Plata/Oro, no vender datos individuales) | **Ronald** (docs/arquitectura) + **Jesús** (código AES-256/KMS) |
| Bitácora de IA y análisis ético | 1,0 | #4 (confianza/sesgos), #6 (uso de datos) | **Todos** (bitácora) + **Daniel** (ética IA) + **Ronald** (ética datos) |
| Presentación (máx. 15 láminas PDF) y guion | 4,0 (grupal) | #3 (ingresos vs. gastos), #5 (encaje SUDEBAN) | **Todos** (rotar roles respecto a S2) |
| Speech y defensa | 6,0 (individual) | Defensa técnica de cada capa | **Todos** (cada integrante defiende su capa) |

---

## 2. División por integrante, rama Git y propiedad de archivos

### Regla de oro para evitar conflictos de merge
Cada integrante crea su rama desde `main` y solo modifica los archivos de su columna. Si necesita un cambio en un archivo de otro track, lo coordina primero contra `CONTRATO_API_S3.md`.

---

### Track 1 — Daniel Haro (`feat/s3-ia-predictiva`)
**Responsabilidad:** IA predictiva (abandono + pronóstico de flujos), reentrenamiento del modelo de perfil para el cuestionario nuevo, pruebas IA y Model Card.

- **Archivos propios:**
  - `ia/generar_dataset_comportamiento.py` *(nuevo)*
  - `ia/entrenar_abandono.py` *(nuevo)*
  - `ia/predictor_abandono.py` *(nuevo)*
  - `ia/pronostico_flujos.py` *(nuevo)*
  - `ia/comun.py`, `ia/generar_dataset.py`, `ia/entrenar.py`, `ia/predictor.py` *(actualizados para S3)*
  - `app/core/perfil.py` *(soporte cuestionario S3 2 tandas + faltantes + retrocompatible con S2)*
  - `data/dataset_comportamiento.csv`, `data/dataset_flujos_diarios.csv`, `data/dataset_sintetico.csv`
  - `docs/ia/DATASET_COMPORTAMIENTO.md`, `docs/ia/MODEL_CARD.md`, `docs/ia/DATASET.md` y gráficos PNG/JSON
  - `tests/test_ia.py` y `tests/test_ia_s3.py`
- **Definición de hecho (DoD):**
  - [ ] Dataset de comportamiento: 5.000 usuarios × 12 meses de eventos sintéticos, reproducible (semilla 42), sin PII.
  - [ ] Modelo de abandono: compara Regresión Logística vs Gradient Boosting con **split temporal** (entrenamiento meses 1–9, prueba meses 10–12). Cumple **AUC ≥ 0,80** y **recall ≥ 0,70** en clase `"abandona"`.
  - [ ] Curva ROC, matriz de confusión, importancia de variables y métricas por grupo de edad y rango de ahorro (sesgos).
  - [ ] `ia/predictor_abandono.py` listo para ser invocado por el endpoint de Jesús (`GET /v1/usuarios/{id}/riesgo-abandono`).
  - [ ] Pronóstico de flujos simple (media móvil vs regresión por fideicomiso) con MAPE y MAE + función `obtener_pronostico_fiduciario()`.
  - [ ] Modelo de perfil reentrenado con las codificaciones del cuestionario nuevo (rango de ahorro mensual, imprevisto de \$200, *"Prefiero no decirlo"* como faltante prudente, soporte Tanda 1 sola y Tanda 1+2). Mantiene exactitud ≥ 85%, F1 por clase ≥ 0,80, **0 Conservador→Agresivo** y regla dura *"sin fondo / no podría / no dice → nunca Agresivo"*.
  - [ ] `docs/ia/MODEL_CARD.md` completo (perfil + abandono + pronóstico + diseño rescate/cambio de perfil + límites + ética/confianza) listo para exportar a `S3_EquipoD_ModelCard.pdf`.
  - [ ] Todas las pruebas (`test_flujo.py`, `test_ia.py`, `test_ia_s3.py`) en verde.

---

### Track 2 — Jesús Sayago (`feat/s3-backend-catalogo`)
**Responsabilidad:** Catálogo de fideicomisos, aportes repartidos, adhesión por fideicomiso, conexión de endpoints IA/cuestionario y módulo de cifrado/datos en Python.

- **Archivos propios:**
  - `app/core/catalogo.py` *(nuevo)*
  - `app/core/fideicomiso.py` *(migrar de 3 portafolios fijos a 5 fideicomisos del catálogo)*
  - `app/core/conciliacion.py` *(nivel 2 y 3 por fideicomiso)*
  - `app/core/servicio.py` *(orquestación catálogo, adhesión por fideicomiso, distribución 100%, comisión/recargo, cuestionario 2 tandas, revisión humana, riesgo abandono, consentimiento)*
  - `app/core/seguridad_datos.py` *(nuevo: AES-256-GCM en reposo, KMS/rotación simulada, seudonimización Plata, agregación Oro con $k \ge 10$)*
  - `app/api/esquemas.py`, `app/main.py`
  - `tests/test_flujo.py`, `tests/test_catalogo_s3.py` *(nuevo)*
  - `docs/openapi.yaml` (regenerar con `python scripts/generar_openapi.py`)
- **Definición de hecho (DoD):**
  - [ ] `GET /fiduciario/v1/fideicomisos` (catálogo simulado del banco con los 5 fideicomisos) y caché diario en `app/core/catalogo.py`.
  - [ ] `GET /v1/fideicomisos?usuario_id=` aplica regla de idoneidad (`CONSERVADOR→2`, `MODERADO→3`, `AGRESIVO→5`), etiqueta cada fideicomiso (`RECOMENDADO`, `COMPATIBLE`, `POR_ENCIMA_DEL_PERFIL`) y ordena la lista.
  - [ ] `POST /v1/usuarios/{id}/adhesion` acepta `fideicomiso_id` y `confirmacion_riesgo_extra` (obligatoria si el fideicomiso supera el perfil); guarda sello de tiempo y hash SHA-256 (Ley de Mensajes de Datos y Firmas Electrónicas).
  - [ ] `POST /v1/aportes` soporta `distribucion` (lista de `{fideicomiso_id, porcentaje}` que suma 100%, exige adhesión a cada fideicomiso y valida aporte mínimo por fideicomiso) y `medio_pago` (`TARJETA` cobra 1% + 2% recargo; `PAGO_MOVIL`/`TRANSFERENCIA` cobra 1% + 0% recargo).
  - [ ] `GET /v1/usuarios/{id}/portafolio` devuelve el consolidado total y el desglose por fideicomiso.
  - [ ] Conciliación nivel 2 y 3 y propuesta de órdenes por lote funcionan por fideicomiso.
  - [ ] Endpoints nuevos conectados a Daniel: `POST /v1/usuarios/{id}/perfil` (Tanda 1 con edad desde KYC), `PATCH /v1/usuarios/{id}/perfil/tanda2`, `POST /v1/usuarios/{id}/perfil/revision` (*"No estoy de acuerdo"*), `GET /v1/usuarios/{id}/riesgo-abandono` (llama `ia.predictor_abandono.predecir_abandono`), `GET /v1/fiduciario/pronostico-flujos` (llama `ia.pronostico_flujos.obtener_pronostico_fiduciario`).
  - [ ] Endpoints de privacidad/habeas data (art. 28): `PUT /v1/usuarios/{id}/consentimiento`, `GET /v1/usuarios/{id}/datos-personales`.
  - [ ] Módulo `app/core/seguridad_datos.py` con cifrado AES-256-GCM real (o `cryptography`), rotación simulada de llaves KMS, token seudónimo (Plata) y supresión de celdas con $< 10$ personas (Oro).
  - [ ] Pruebas nuevas en verde: sin adhesión a ese fideicomiso no aporta; por encima del perfil exige confirmación expresa; distribución debe sumar 100%; cifrado/descifrado y rotación KMS; supresión $k < 10$.

---

### Track 3 — David Crespo (`feat/s3-frontend-mvp`)
**Responsabilidad:** Front-end React completo de la Sesión 3, integración con la API nueva, compilación `frontend/dist` y video de respaldo de la demo.

- **Archivos propios:**
  - `frontend/src/lib/api.ts`, `frontend/src/lib/datos.ts`, `frontend/src/estado.tsx`
  - `frontend/src/screens/ExplorarFideicomisos.tsx` *(nueva)*
  - `frontend/src/screens/Cuestionario.tsx` *(2 tandas, situacional, "¿Por qué te preguntamos esto?", "Prefiero no decirlo", mini gráfico \$100→\$80)*
  - `frontend/src/screens/Perfil.tsx` *(aviso modelo automático, qué cambiaría el perfil, botón "No estoy de acuerdo con mi perfil", acceso a Tanda 2 "Afinemos tu perfil")*
  - `frontend/src/screens/Adhesion.tsx`, `frontend/src/screens/Aporte.tsx` *(reparto % sumando 100% + medio de pago Tarjeta vs Pago Móvil con transparencia de comisiones)*
  - `frontend/src/screens/Portafolio.tsx` *(suma de fideicomisos + aviso suave de abandono + controles de consentimiento y habeas data)*
  - `frontend/src/components/PanelDemo.tsx` *(controles para simular riesgo de abandono en la demo)*
  - `frontend/dist/` *(compilado con `npm run build`)*
- **Definición de hecho (DoD):**
  - [ ] Pantalla **Explorar fideicomisos**: tarjetas con los 5 fideicomisos, etiqueta de idoneidad visible, filtro por nivel de riesgo (1–5), comparador lado a lado de 2 fideicomisos y nota *"El rendimiento histórico simulado no garantiza resultados futuros"*.
  - [ ] Modal de **confirmación expresa** cuando el usuario elige un fideicomiso *"Por encima de tu perfil"* (explica el riesgo en lenguaje simple, no bloquea, registra confirmación).
  - [ ] **Cuestionario nuevo**: Tanda 1 (6 preguntas, sin edad porque sale del KYC, enlace *"¿Por qué te preguntamos esto?"* de 1 línea en cada pregunta, botón *"Prefiero no decirlo"* en las de dinero/emergencia, mini gráfico en la caída \$100→\$80) + pantalla opcional Tanda 2 *"Afinemos tu perfil"* (hogar + 2 preguntas de quiz amistoso).
  - [ ] **Perfil**: texto claro *"Esta sugerencia la hace un modelo automático; tú decides y un asesor puede revisarla"*, sección *"¿Qué respuesta cambiaría tu perfil?"* y botón *"No estoy de acuerdo con mi perfil"* que dispara revisión humana.
  - [ ] **Aporte repartido**: permite elegir 1 o varios fideicomisos (ej. 70% Renta Fija USD + 30% Mixto Balanceado), valida que sume 100%, muestra transparencia de comisión (1% aporte + 2% recargo solo si elige tarjeta; 0% recargo en Pago Móvil).
  - [ ] **Portafolio consolidado**: suma total + detalle por fideicomiso + **aviso suave de abandono** (ej. *"¿Quieres programar tu aporte de \$10 cada quincena?"*) + toggle de consentimiento separado para informes agregados y botón de derechos habeas data.
  - [ ] `npm run typecheck && npm run build` sin errores y **video de respaldo** (3–4 min) grabado mostrando todo el flujo.

---

### Track 4 — Ronald Gómez (`feat/s3-devsecops-seguridad`)
**Responsabilidad:** Pipeline DevSecOps en GitHub Actions, hardening y auditoría inmutable en FastAPI, documentos STRIDE/OWASP y Cifrado/Arquitectura de datos, y verificación de citas legales.

- **Archivos propios:**
  - `.github/workflows/devsecops.yml` *(nuevo)*
  - `app/core/auditoria.py` *(nuevo: registro inmutable encadenado por hash SHA-256 con origen, destino, fecha/hora, IP y usuario — Res. SUDEBAN 001.21; middleware de cabeceras de seguridad)*
  - `docs/seguridad/STRIDE_OWASP_DEVSECOPS.md` *(nuevo)*
  - `docs/seguridad/CIFRADO_Y_DATOS.md` *(nuevo)*
  - `docs/seguridad/arquitectura_datos.mmd` y `.png` *(diagrama Bronce/Plata/Oro)*
  - `docs/seguridad/evidencias/` *(reportes/capturas de Bandit, pip-audit, npm audit, Gitleaks y OWASP ZAP)*
- **Definición de hecho (DoD):**
  - [ ] Pipeline `.github/workflows/devsecops.yml` corriendo en verde en GitHub Actions con 5 jobs:
    1. Pruebas unitarias (`pytest`) y compilación front-end (`npm run typecheck && npm run build`).
    2. **SAST:** `bandit -r app ia scripts -ll`.
    3. **SCA:** `pip-audit -r requirements.txt` y `npm audit --prefix frontend --audit-level=high`.
    4. **Escaneo de secretos:** `gitleaks`.
    5. **DAST básico:** levantar `uvicorn app.main:app` en el runner y correr **OWASP ZAP Baseline** contra `http://127.0.0.1:8000`.
  - [ ] Hardening en FastAPI: middleware de cabeceras HTTP seguras (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`, `Strict-Transport-Security`), CORS restrictivo y registro inmutable `app/core/auditoria.py` (conectado en `app/main.py` tras coordinar con Jesús).
  - [ ] Hallazgos críticos/altos de Bandit, SCA y ZAP resueltos y documentados.
  - [ ] `STRIDE_OWASP_DEVSECOPS.md`: análisis STRIDE del flujo completo (registro/KYC, catálogo/adhesión, aporte repartido, pasarela/ISO 8583, cierre/conciliación, endpoints IA) + mapeo de controles **OWASP Top 10** y **OWASP API Security Top 10**.
  - [ ] `CIFRADO_Y_DATOS.md`: esquema de protección de datos (TLS 1.3, AES-256 en reposo, tokenización PAN/SAQ A, KMS y rotación de llaves), arquitectura de datos **Bronce / Plata / Oro** ($k \ge 10$), tabla de qué se comparte vs. no se comparte, controles de consentimiento/habeas data/retención y justificación explícita de **por qué no se usa blockchain**.
  - [ ] Verificar contra el texto oficial de la Gaceta las 3 citas legales pendientes del plan antes de ponerlas en láminas:
    1. Res. SUDEBAN 001.21 (reimpresa G.O. 42.162): artículo exacto de 5 accionistas y registro cronológico con IP (verificar corrimiento del art. 24).
    2. Res. SUDEBAN 010.25 (G.O. 43.098): si menciona expresamente *"Conozca al cliente de su cliente"* (KYCC).
    3. Números de Gaceta de Res. 083.12 y Res. 063.15 en el compendio oficial de SUDEBAN.

---

## 3. Calendario de integración (Mié 25-nov → Dom 29-nov)

| Día | Hito de coordinación | Daniel (IA) | Jesús (Back) | David (Front) | Ronald (Sec/DevSecOps) |
|---|---|---|---|---|---|
| **Mié 25-nov** | Congelar `CONTRATO_API_S3.md` y acordar ramas | Dataset comportamiento + modelo abandono + pronóstico flujos | Iniciar `catalogo.py` y `fideicomiso.py` multi-fideicomiso | Maquetar *Explorar fideicomisos* y cuestionario 2 tandas usando el contrato | Crear `.github/workflows/devsecops.yml` y correrlo en PR de prueba |
| **Jue 26-nov** | **Checkpoint 1 (20:00):** PR de Daniel (`ia/`) y PR base de Ronald (`ci`) listos | Reentrenar modelo de perfil S3 + `MODEL_CARD.md` + pruebas `test_ia_s3.py` | Terminar endpoints catálogo, adhesión, aporte repartido y conectar IA | Terminar pantallas *Explorar*, *Cuestionario 2 tandas* y *Perfil* | Middleware seguridad + `auditoria.py` + borrador STRIDE/OWASP |
| **Vie 27-nov** | **Checkpoint 2 (20:00):** Merge a `main` de Daniel → Jesús → David → Ronald | Pulir Model Card + sección análisis ético IA + láminas de IA | `seguridad_datos.py` (AES-256/KMS/Oro) + pruebas backend + `openapi.yaml` | Conectar front-end a la API real de Jesús + *Aporte repartido* + *Portafolio* | Correr pipeline completo sobre `main` (SAST/SCA/DAST), resolver hallazgos + `CIFRADO_Y_DATOS.md` + verificación Gaceta |
| **Sáb 28-nov** | **Congelamiento de código (18:00)** | Revisión cruzada de pruebas + láminas + guion | Pruebas E2E + capturas Swagger + láminas backend/negocio | `npm run build`, pruebas E2E en Web/Móvil + grabar **video respaldo** | Capturas evidencia CI/CD + láminas seguridad/legal |
| **Dom 29-nov** | **Carga aula virtual antes de las 23:59** | Ensayo general + exportar PDFs `S3_EquipoD_*.pdf` + completar bitácora | Ensayo general + verificar filas bitácora | Ensayo general + verificar video y bitácora | Ensayo general + revisión final PDFs y bitácora |

---

## 4. Entregables PDF a cargar (domingo 29-nov, 23:59)

Convención obligatoria: `S3_EquipoD_<Entregable>.pdf` (todo el código vive en Git).

1. `S3_EquipoD_ModelCard.pdf` — desde `docs/ia/MODEL_CARD.md` (+ `DATASET_COMPORTAMIENTO.md` como anexo).
2. `S3_EquipoD_DevSecOps_STRIDE.pdf` — desde `docs/seguridad/STRIDE_OWASP_DEVSECOPS.md` (con capturas del pipeline en GitHub Actions).
3. `S3_EquipoD_Cifrado_Datos.pdf` — desde `docs/seguridad/CIFRADO_Y_DATOS.md` (esquema de protección de datos + arquitectura Bronce/Plata/Oro).
4. `S3_EquipoD_Bitacora_Etica.pdf` — desde `docs/equipo/BITACORA_IA_S3.md` (bitácora de uso de IA + análisis ético consolidado).
5. `S3_EquipoD_Presentacion.pdf` — máximo **15 láminas** (incluir: 1 lámina de respuesta a los 6 comentarios S2, 1 de modelo de ingresos/gastos, 1 legal SUDEBAN; marcar explícitamente todo lo simulado).
6. `S3_EquipoD_Guion.pdf` — guion de 15 min (quién habla, qué lámina, mensaje clave, **sin leer durante la exposición**).
7. **Video de respaldo** de la demo del MVP (enlace o archivo según permita el aula virtual).

---

## 5. Estructura sugerida del Speech (15 min + 5 preguntas) y rotación

> **Regla del profesor:** hablan los 4 integrantes y **nadie repite el mismo rol de la Sesión 2**. Cada integrante defiende una capa (producto/negocio, demo MVP, IA, seguridad/datos).

1. **Apertura y respuesta al feedback S2 (2 min):** los 6 cambios integrados, modelo de ingresos con 5 fuentes (punto de equilibrio año 2) y encaje legal SUDEBAN Fase 1.
2. **Demo del MVP en vivo (5 min):** cuestionario en 2 tandas → perfil explicable → explorar y comparar fideicomisos → adhesión + aporte repartido (Tarjeta vs Pago Móvil) → portafolio con aviso de abandono + cierre/conciliación.
3. **IA predictiva y Model Card (3,5 min):** modelo de abandono (split temporal, AUC, recall, sesgos), pronóstico de flujos para el fiduciario, reentrenamiento de perfil y límites éticos.
4. **DevSecOps, cifrado y arquitectura de datos (3,5 min):** pipeline CI/CD (SAST/SCA/secretos/DAST), STRIDE/OWASP, AES-256/KMS/SAQ A y arquitectura Bronce/Plata/Oro ($k \ge 10$, no venta de datos individuales).
5. **Cierre (1 min):** logros, riesgos abiertos para Sesión 4 (RegTech AML, matriz PCI/SUDEBAN, sandbox ITFB).

### Preguntas para validar con el profesor antes del martes
- ¿El fideicomiso colectivo con unidades se acepta como fideicomiso bancario o lo ve como entidad de inversión colectiva (SUNAVAL)?
- ¿La fase 1 como proveedor tecnológico en alianza con el banco (Res. 001.21) es suficiente para el encaje SUDEBAN, o quiere ver la ruta ITFB desde ya?
