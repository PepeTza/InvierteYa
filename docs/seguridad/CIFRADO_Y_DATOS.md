# Cifrado, Protección de Datos Sensibles y Arquitectura Bronce / Plata / Oro — Sesión 3

**Proyecto:** InvierteYa (MVP Seguro con IA Integrada) · **Equipo D**  
**Responsable de documentación y arquitectura (Track 4):** Ronald Gómez  
**Responsable de implementación en código (Track 2):** Jesús Sayago (`app/core/seguridad_datos.py`)  
**Atiende:** Comentarios #5 y #6 de la Sesión 2 (protección de datos, arquitectura en 3 capas y no comercialización de datos individuales)

> **Nota de transparencia:** en el MVP el KMS y la rotación de llaves son **simulados en memoria**, y se trabaja exclusivamente con **datos sintéticos** (sin PAN, cédulas ni cuentas bancarias reales). El modelo de cifrado **AES-256-GCM**, la seudonimización y la supresión $k \ge 10$ están diseñados para operar de forma idéntica en producción sobre un KMS administrado (AWS KMS / HashiCorp Vault).

---

## 1. Esquema integral de cifrado y protección de datos

| Superficie / Dato | Estado | Control criptográfico y de acceso | Alcance / Estándar |
|---|---|---|---|
| **Tránsito Cliente ↔ API ↔ Pasarela ↔ Fiduciario** | En tránsito | **TLS 1.3** obligatorio (con `Strict-Transport-Security: max-age=31536000; includeSubDomains` desde `MiddlewareSeguridadHTTP` en producción HTTPS). | OWASP ASVS / SUDEBAN |
| **Datos personales e identidad (KYC, correo, edad)** | En reposo (Capa Bronce) | **AES-256-GCM** (cifrado autenticado con *nonce* único de 96 bits por registro y etiqueta de autenticidad contra manipulación). | NIST SP 800-38D |
| **Datos de tarjeta (PAN, CVV, expiración)** | Captura y pago | **Tokenización delegada en la pasarela (`tok_...`)**: el formulario/SDK de la pasarela captura los datos de tarjeta y nunca llegan al servidor de InvierteYa. | **PCI DSS SAQ A** (alcance mínimo) |
| **Firmas de adhesión y eventos críticos** | Integridad / No repudio | **SHA-256**: `hash_adhesion` en contrato de adhesión + cadena inmutable `hash_previo → hash_actual` en `app/core/auditoria.py`. | Ley de Mensajes de Datos y Firmas Electrónicas / Res. SUDEBAN 001.21 |
| **Gestión de llaves (KMS y rotación)** | Ciclo de vida | **Cifrado por envoltorio (*envelope encryption*)**: llave maestra (KEK en KMS) protege llaves de datos (DEK) versionadas (`key_id`). La rotación genera nueva DEK sin perder lectura de registros históricos y permite re-cifrado progresivo. | NIST SP 800-57 |

---

## 2. Arquitectura de datos en 3 capas: Bronce / Plata / Oro

Responde directamente al **Comentario #6 de la Sesión 2** (*"¿cómo garantizan que los datos sensibles no queden expuestos al entrenar IA o generar informes, y cómo evitan la venta de datos individuales?"*). Diagrama fuente en `docs/seguridad/arquitectura_datos.mmd`.

| Capa | Qué datos contiene | Nivel de identificación | Quién accede | Controles aplicados |
|---|---|---|---|---|
| **Bronce (Operacional / Cruda)** | Registro de usuario, resultado KYC, contratos de adhesión firmados, bitácora de auditoría con IP, aportes y tokens de pasarela. | **Identificada (PII directa)** | Solo servicios core del backend de InvierteYa y conciliación con el banco fiduciario (bajo secreto bancario). | Cifrado **AES-256-GCM** en reposo, acceso por mínimo privilegio, sin PAN/CVV (SAQ A) y trazabilidad SHA-256. |
| **Plata (Analítica / Entrenamiento IA)** | Variables de comportamiento y perfilamiento: rango de ahorro, horizonte, reacción ante caídas, frecuencia de aportes, tasas de rechazo y lecciones vistas. | **Seudonimizada** (identificador opaco HMAC/token irreversible sin acceso a llave de mapeo; sin nombre, correo ni IP). | Equipo/pipelines de IA (`ia/entrenar.py`, `ia/entrenar_abandono.py`, `ia/pronostico_flujos.py`). | Eliminación de PII directa, validación automatizada de **0 columnas PII** en `test_ia_s3.py`, consentimiento separado para analítica. |
| **Oro (Inteligencia Agregada)** | Métricas de negocio y tendencias agregadas por cohorte (ej. distribución de riesgo por rango de edad, flujo neto proyectado por fideicomiso). | **Anónima y agregada** ($k$-anonimato) | Banco fiduciario (para planificar lotes) y reportes internos / aliados autorizados con consentimiento. | **Regla dura $k \ge 10$:** cualquier celda o segmento con menos de 10 personas se **suprime automáticamente** para impedir re-identificación por cruce de atributos. |

---

## 3. Política de uso de datos: qué se comparte y qué NUNCA se comparte

| Destinatario | Qué SÍ recibe | Qué NUNCA recibe | Base legal / técnica |
|---|---|---|---|
| **Banco Fiduciario aliado** | Identidad KYC del fideicomitente, contrato de adhesión firmado (`hash_adhesion`), instrucciones de aporte/rescate, conciliación por lote y pronóstico agregado de flujos (`GET /v1/fiduciario/pronostico-flujos`). | Datos completos de tarjeta (PAN/CVV) ni historial de navegación o lecciones del tutor. | Relación fiduciaria + Res. SUDEBAN 001.21 (servicio tecnológico al banco). |
| **Pasarela de pagos certificada** | Monto, moneda, token (`tok_...`) o referencia de Pago Móvil/transferencia, clave de idempotencia y referencia de transacción. | Perfil de riesgo, saldo total del portafolio, respuestas del cuestionario ni datos de otros fideicomisos. | Principio de minimización de datos + PCI DSS SAQ A. |
| **Motor de IA (entrenamiento e inferencia)** | Atributos seudonimizados de Capa Plata (rangos, respuestas codificadas, eventos de uso). | Nombre, cédula/documento, correo, teléfono, dirección IP o número de tarjeta. | Privacidad por diseño (Capa Plata). |
| **Terceros / Aliados comerciales / Informes de mercado** | **Únicamente** estadísticas agregadas de Capa Oro con **$k \ge 10$** personas por celda y **solo** de usuarios con consentimiento explícito activo. | **Nunca** se venden, alquilan ni ceden perfiles individuales, hábitos personales ni listas de contactos. | Secreto bancario, Res. SUDEBAN 001.21 y ética de datos del Equipo D. |

---

## 4. Consentimiento granular, Habeas Data y retención

Para cumplir el **artículo 28 de la Constitución** (derecho de acceso, actualización y supresión de datos) y evitar el consentimiento atado:

1. **Consentimiento separado (`PUT /v1/usuarios/{id}/consentimiento`):**
   - `informes_agregados` y `alertas_ahorro` son interruptores independientes de los términos obligatorios del servicio. El usuario puede activarlos o revocarlos en cualquier momento desde el front-end (`Portafolio.tsx`).
2. **Derecho de acceso (`GET /v1/usuarios/{id}/datos-personales`):**
   - Devuelve en lenguaje claro qué datos personales conserva InvierteYa, su perfil asignado y el estado vigente de sus consentimientos.
3. **Derecho de supresión / anonimización (`DELETE /v1/usuarios/{id}/datos-personales`):**
   - Elimina/anonimiza datos de uso y perfilamiento en Capa Bronce y Plata, conservando **únicamente** los registros contables y de auditoría exigidos al banco por normativa de prevención de legitimación de capitales (**LC/FT**) durante el plazo legal de retención.

---

## 5. Justificación técnica: por qué NO se usa blockchain

Aunque el MVP incluye trazabilidad inmutable encadenada por hash SHA-256, **no utilizamos blockchain** (pública ni permisionada) por cuatro razones de ingeniería, privacidad y regulación:

1. **Conflicto con Habeas Data (derecho al olvido / supresión):**
   - La Constitución (art. 28) obliga a poder suprimir o rectificar datos personales cuando el usuario lo solicite (`DELETE /datos-personales`). Una blockchain distribuida hace técnicamente inviable borrar registros históricos sin romper el consenso, mientras que nuestra arquitectura permite separar la PII cifrada (suprimible/anonimizable en Bronce) de la bitácora operativa seudonimizada.
2. **Privacidad bancaria y Res. SUDEBAN 001.21:**
   - Las operaciones financieras de clientes están sujetas a confidencialidad bancaria; replicar trazas financieras en nodos distribuidos amplía innecesariamente la superficie de exposición frente a un esquema centralizado auditado bajo control del banco fiduciario.
3. **Costo operacional, latencia y simplicidad en Fase 1:**
   - InvierteYa opera aportes pequeños (desde \$5) en alianza con un único banco fiduciario que ya actúa como tercero de confianza regulado. Mantener nodos, consenso y sincronización añade latencia y costos incompatibles con micro-aportes, sin aportar seguridad adicional frente al modelo cliente-fiduciario.
4. **Integridad verificable sin blockchain:**
   - La clase `BitacoraAuditoria` (`app/core/auditoria.py`) logra detección determinística de manipulaciones mediante **encadenamiento criptográfico SHA-256 (`hash_previo → hash_actual`)** y sello de tiempo, con costo computacional prácticamente nulo ($O(1)$ por evento) y respaldo directo ante auditorías de SUDEBAN.
