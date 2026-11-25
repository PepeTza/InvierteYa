# Bitácora de uso de IA y Análisis Ético — Sesión 3 · Equipo D (InvierteYa)

> **Regla de la cátedra:** declarar toda herramienta de IA utilizada, validar datos/cifras contra fuentes
> primarias o ejecución real de código, trabajar solo con datos sintéticos y pasar el código generado por
> SAST/SCA antes de integrarlo. El uso de IA no declarado penaliza el 50% del entregable técnico.

## Declaración de uso de IA

El Equipo D utilizó asistentes de IA (Antigravity / Gemini y Claude) durante la Sesión 3 para planificación,
definición del contrato de API, generación de código de modelos predictivos, backend, front-end, pipeline
DevSecOps y redacción de documentación técnica. Todas las métricas de los modelos de IA (precisión, recall,
F1, AUC, MAPE, MAE y sesgos por grupo) fueron **calculadas ejecutando código con scikit-learn** sobre datos
**100% sintéticos**; ninguna persona ni tarjeta real fue ingresada en herramientas de IA.

---

## 1. Registro de usos de IA (Sesión 3)

| Fecha | Integrante | Herramienta | Propósito | Prompt resumido | Qué usaron del resultado | Cómo lo validaron |
|---|---|---|---|---|---|---|
| 25-nov-2026 | Daniel Haro | Antigravity (Gemini) | Dividir la Sesión 3 en 4 tracks y congelar el contrato de API | "Tengo el plan de la Sesión 3 y las instrucciones del curso; divide el trabajo para 4 personas sin conflictos de Git y congela el contrato de API" | `docs/equipo/PLAN_TRABAJO_S3.md` y `docs/equipo/CONTRATO_API_S3.md` con propiedad de archivos, ramas y payloads JSON | Contraste directo con la rúbrica de la Sesión 3, el plan de respuesta a la S2 y la estructura real del repositorio |
| 25-nov-2026 | Daniel Haro | Antigravity (Gemini) | Dataset sintético de comportamiento y flujos diarios (IA predictiva) | "Genera un dataset sintético de 5.000 usuarios por 12 meses de eventos (aportes, rechazos 51/05, sesiones, lecciones, rescates) y una serie diaria de flujos por fideicomiso" | `ia/generar_dataset_comportamiento.py`, `data/dataset_comportamiento.csv`, `data/dataset_flujos_diarios.csv` y `docs/ia/DATASET_COMPORTAMIENTO.md` | Ejecución reproducible con semilla fija 42; pruebas automáticas (`test_ia_s3.py`) verificando 0 columnas PII y separación temporal estricta |
| 25-nov-2026 | Daniel Haro | Antigravity (Gemini) | Entrenar y medir el modelo predictivo de abandono y el pronóstico de flujos | "Compara regresión logística vs gradient boosting con split temporal (meses 1–9 vs 10–12) para predecir abandono a 60 días y construye un pronóstico simple de flujos (media móvil vs regresión)" | `ia/entrenar_abandono.py`, `ia/predictor_abandono.py`, `ia/pronostico_flujos.py`, gráficos ROC/confusión/importancia/flujos y JSON de métricas | Métricas calculadas con `scikit-learn`; validación de AUC ≥ 0,80, recall ≥ 0,70, análisis de sesgo por edad/ahorro y pruebas unitarias en verde |
| 25-nov-2026 | Daniel Haro | Antigravity (Gemini) | Reentrenar el modelo de perfil para el cuestionario conversacional en 2 tandas | "Actualiza el modelo de perfil para aceptar rangos de ahorro, imprevisto de $200, 'Prefiero no decirlo' como faltante prudente y 2 tandas, manteniendo 0 Conservador→Agresivo" | Actualización de `app/core/perfil.py`, `ia/comun.py`, `ia/generar_dataset.py`, `ia/entrenar.py`, `ia/predictor.py` y `docs/ia/MODEL_CARD.md` | Ejecución de `ia/entrenar.py`, pruebas `CP-16` a `CP-21` y nuevas pruebas S3 (`CP-22` a `CP-30`) + verificación de compatibilidad con `test_flujo.py` |
| *(pendiente)* | Jesús Sayago | *(completar)* | Catálogo de fideicomisos, aportes repartidos y módulo AES-256/KMS | *(completar)* | *(completar)* | Pruebas `pytest` + SAST (Bandit) + SCA (`pip-audit`) |
| *(pendiente)* | David Crespo | *(completar)* | Front-end MVP S3 (Explorar fideicomisos, cuestionario 2 tandas, aporte repartido, portafolio) | *(completar)* | *(completar)* | `npm run typecheck && npm run build` + `npm audit` + demo E2E |
| *(pendiente)* | Ronald Gómez | *(completar)* | Pipeline DevSecOps (GitHub Actions), STRIDE/OWASP, cifrado y verificación legal | *(completar)* | *(completar)* | Corrida en verde de Bandit, `pip-audit`, `npm audit`, Gitleaks y OWASP ZAP + contraste de citas legales contra Gaceta Oficial |

---

## 2. Análisis ético consolidado (Sesión 3)

### 2.1 Confianza y transparencia en la IA (Comentario 4)
- **Redacción no invasiva:** el cuestionario elimina preguntas sensibles directas (*"¿cuánto ganas?"*) y las reemplaza por situaciones cotidianas (*"¿cuánto podrías apartar al mes sin apretarte?"*, *"si mañana tuvieras un gasto imprevisto de \$200..."*), con la salida cómoda **"Prefiero no decirlo"** tratada de forma prudente y un enlace **"¿Por qué te preguntamos esto?"** en cada paso.
- **No ocultamos la automatización:** la pantalla de perfil declara explícitamente *"Esta sugerencia la hace un modelo automático; tú decides y un asesor puede revisarla"*.
- **Contestabilidad:** se muestra qué factores suben o moderan el perfil, qué respuesta lo cambiaría y un botón **"No estoy de acuerdo con mi perfil"** que abre revisión humana.

### 2.2 Límites éticos de la IA predictiva (Comentario 2)
- **Ningún modelo mueve dinero ni cambia el perfil por sí solo:** tanto el clasificador de perfil como el modelo de abandono solo sugieren.
- **El abandono nunca penaliza al usuario:** la predicción de riesgo de abandono se usa exclusivamente para enviar avisos suaves de apoyo al hábito de ahorro (*"¿Quieres programar tu aporte de \$10 cada quincena?"*), nunca para cobrar comisiones mayores, restringir el servicio ni ejercer presión indebida.
- **Sin promesas de rendimiento:** ningún modelo predice precios de mercado ni promete ganancias; todo rendimiento histórico simulado lleva el aviso *"no garantiza resultados futuros"*.

### 2.3 Equidad y control de sesgos
- Tanto el modelo de **perfil de riesgo** como el modelo de **abandono** se evalúan de forma desagregada por **grupo de edad** (18–24, 25–40, 41+) y **rango de ahorro/ingreso** (ver `docs/ia/MODEL_CARD.md`).
- Las variables sensibles como edad e ingreso tienen peso acotado y están sujetas a pruebas automatizadas para detectar disparidades de exactitud o tasas desproporcionadas de falsos positivos.

### 2.4 Ética en el uso y monetización de datos (Comentario 6)
- **No se venden datos individuales:** la Res. SUDEBAN 001.21 (confidencialidad de operaciones) y el secreto bancario impiden comercializar perfiles individuales, además de destruir la confianza del usuario.
- **Privacidad por diseño (3 capas):** los datos entran cifrados con AES-256 (Bronce), se seudonimizan para entrenar modelos sin nombre ni cédula (Plata) y solo salen como **informes agregados con $k \ge 10$ personas por celda** (Oro), suprimiendo cualquier celda más pequeña.
- **Consentimiento granular y habeas data:** el consentimiento para informes agregados es opcional, está separado de los términos del servicio y puede retirarse desde la app, respetando los derechos de acceso, rectificación y supresión (Constitución, art. 28).
