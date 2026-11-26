# Seguridad Aplicativa, Modelado de Amenazas (STRIDE / OWASP) y DevSecOps — Sesión 3

**Proyecto:** InvierteYa (MVP Seguro con IA Integrada) · **Equipo D**  
**Responsable Track 4 (DevSecOps y Seguridad):** Ronald Gómez  
**Rama de trabajo:** `feat/s3-devsecops-seguridad`  
**Contrato base:** `docs/equipo/CONTRATO_API_S3.md` (`v0.3.0-s3`)

> **Alcance y transparencia (simulado vs. implementado):** En el MVP, la pasarela de pago, el adquirente/suiche/emisor (ISO 8583), el banco fiduciario y el KMS son **simulados en memoria** con datos **100% sintéticos**. Los controles de **pipeline DevSecOps** (`.github/workflows/devsecops.yml`), **bitácora inmutable encadenada por SHA-256** y **cabeceras HTTP + CORS restrictivo** (`app/core/auditoria.py`) sí están implementados y probados en el código fuente.

---

## 1. Arquitectura de confianza y fronteras del MVP

InvierteYa opera como **plataforma de acceso e intermediación tecnológica** aliada a un **banco fiduciario** (Fase 1) y a una **pasarela de pagos certificada**. Ningún número real de tarjeta (PAN) ni CVV toca nuestros servidores (**alcance PCI DSS: SAQ A**).

```
[Usuario (Web/Móvil React)]
        │  HTTPS / TLS 1.3
        ├──────────────────────────────────────► [Pasarela Aliada (Tokenización SAQ A)]
        │                                                │ token_tarjeta (tok_...)
        ▼                                                ▼
[API FastAPI InvierteYa (/v1)] ◄──── Token + Idempotency-Key
  ├─ MiddlewareSeguridadHTTP (CSP, X-Frame-Options, HSTS, CORS)
  ├─ MiddlewareAuditoria (SHA-256 chain · Res. SUDEBAN 001.21)
  ├─ Motor IA (perfil 2 tandas, abandono, pronóstico flujos)
  └─ Cifrado AES-256-GCM + Seudonimización (Plata) + Agregación k>=10 (Oro)
        │
        ▼  Propuesta de órdenes por lote + Conciliación 3 niveles
[Banco Fiduciario (Simulado)]
```

**Fronteras de confianza clave:**
1. **Frontera 1 (Cliente → API InvierteYa):** tráfico externo no confiable; exige autenticación (`Authorization: Bearer`, simulada en demo con `demo-token`), validación estricta de esquemas Pydantic, CORS restrictivo y cabeceras de endurecimiento HTTP.
2. **Frontera 2 (Cliente → Pasarela):** los datos de tarjeta viajan directamente al formulario/SDK de la pasarela; InvierteYa solo recibe un token opaco (`tok_...`).
3. **Frontera 3 (API → Motor de IA):** las salidas de IA (perfil de riesgo y riesgo de abandono) pasan por reglas duras de seguridad y nunca ejecutan movimientos de dinero ni penalizan al usuario.
4. **Frontera 4 (InvierteYa → Banco Fiduciario):** separación de funciones: InvierteYa **propone** órdenes por lote y el **fiduciario aprueba** tras conciliación en 3 niveles.

---

## 2. Análisis de amenazas STRIDE sobre el flujo completo (Sesión 3)

Metodología: **S**poofing (Suplantación), **T**ampering (Manipulación), **R**epudiation (Repudio), **I**nformation Disclosure (Divulgación), **D**enial of Service (Denegación de servicio) y **E**levation of Privilege (Elevación de privilegios).

| Flujo / Componente S3 | Amenaza STRIDE | Escenario concreto de ataque | Control implementado / mitigación en InvierteYa | Estado en MVP |
|---|---|---|---|---|
| **1. Registro y KYC** (`POST /v1/usuarios`, `/kyc`) | **S / I** | Suplantación de identidad o filtración de nombre, correo o edad KYC. | Auth Bearer obligatoria en `/v1/*`; datos personales cifrados con AES-256-GCM en capa Bronce (`seguridad_datos.py`); edad tomada del KYC validado sin exponer PII en logs ni datasets de IA. | Implementado (KYC y auth simulados; cifrado en Track 2). |
| **2. Catálogo y Adhesión por fideicomiso** (`GET /v1/fideicomisos`, `POST /adhesion`) | **R / E** | Usuario invierte en un fideicomiso `POR_ENCIMA_DEL_PERFIL` y luego niega haber aceptado el riesgo o alega adhesión no autorizada. | Regla de idoneidad (`CONSERVADOR→2`, `MODERADO→3`, `AGRESIVO→5`); bloqueo HTTP `422` (`CONFIRMACION_RIESGO_REQUERIDA`) si falta `confirmacion_riesgo_extra`; sello de tiempo ISO 8601 + `hash_adhesion` SHA-256 + registro en `BitacoraAuditoria` con IP. | Contrato congelado (Track 2) + auditoría implementada en `auditoria.py`. |
| **3. Aporte repartido y medios de pago** (`POST /v1/aportes`) | **T / D** | Manipulación de porcentajes (no suman 100%, montos negativos), reintento de red que cobra dos veces, o evasión del mínimo por fideicomiso. | Validación Pydantic + negocio HTTP `422` (`DISTRIBUCION_INVALIDA`, `ADHESION_PENDIENTE`, `MONTO_MINIMO_FIDEICOMISO`); header obligatorio `Idempotency-Key`; desglose explícito de `comision_aporte_pct` (1%) y `recargo_medio_pago_pct` (2% tarjeta / 0% Pago Móvil). | Contrato S3 (Track 2) + idempotencia S2 activa. |
| **4. Pasarela y mensajería ISO 8583** (`/pasarela/v1/*`, `0100/0220/0400/0420`) | **I / T / R** | Exposición de PAN/CVV en el backend, cobros huérfanos por timeout de red o alteración de mensajes de liquidación. | Tokenización previa (`SAQ A`): el PAN nunca entra a `/v1/*`; ante timeout/falla de captura se dispara reverso automático (`0400/0410` y reintentos `0420/0421`); detección de huérfanos y devolución (`/refunds`). | Implementado en `pasarela_simulada.py` y `iso8583.py`. |
| **5. Cierre del día y conciliación** (`POST /v1/operaciones/cierre`) | **T / E** | Descuadre entre pasarela, banco fiduciario y libro interno, o ejecución directa de compra de títulos sin autorización fiduciaria. | Conciliación en 3 niveles por fideicomiso; principio de menor privilegio: InvierteYa solo **propone** órdenes por lote, el **banco fiduciario aprueba**; alerta inmediata ante omisiones en liquidación. | Implementado en `conciliacion.py` y `fideicomiso.py`. |
| **6. Endpoints de IA y Privacidad** (`/perfil`, `/tanda2`, `/riesgo-abandono`, `/pronostico-flujos`, `/datos-personales`) | **E / I / T** | Inyección de valores extremos para forzar perfil `AGRESIVO` sin respaldo; extracción de datos individuales desde informes; manipulación de registros de auditoría. | Regla dura: sin fondo de emergencia (`"no_podria"` o `null`) nunca `AGRESIVO`; probabilidad < 60% o desacuerdo activa revisión humana; `riesgo-abandono` solo emite recordatorio suave; capa Oro suprime celdas con $k < 10$; `BitacoraAuditoria` encadena cada evento con `hash_previo → hash_actual` SHA-256. | Reglas y bitácora implementadas; endpoints S3 en integración. |

---

## 3. Mapeo OWASP Top 10 (2021) y OWASP API Security Top 10 (2023)

### 3.1 OWASP API Security Top 10 (2023)

| Código | Riesgo OWASP API | Aplicación en InvierteYa | Control concreto |
|---|---|---|---|
| **API1:2023** | Broken Object Level Authorization (BOLA) | Acceso al portafolio, datos personales o adhesiones de otro `usuario_id`. | En MVP: autenticación en `/v1/*` y validación de existencia (`404`). En producción (Fase 1 bancaria): el `sub` del JWT OAuth2 se valida contra `{usuario_id}` en cada ruta; en `auditoria.py` queda trazado `usuario_id` e IP. |
| **API2:2023** | Broken Authentication | Uso indebido de credenciales o tokens débiles. | Separación de entorno para `INVIERTEYA_TOKEN_DEMO` (nunca hardcodeado en producción); validación en dependencia global `autenticado()` del router `v1`. En producción: OAuth2/OIDC + MFA. |
| **API3:2023** | Broken Object Property Level Authorization | Envío de campos no permitidos (ej. alterar `perfil` o `saldo` directamente en el payload). | Modelos Pydantic estrictos en `esquemas.py` que solo exponen los campos de entrada permitidos; decisiones calculadas únicamente en el backend. |
| **API4:2023** | Unrestricted Resource Consumption | Abuso de `/aportes`, `/perfil` o endpoints de IA (DoS / fuerza bruta). | `Idempotency-Key` obligatoria en `/v1/aportes`; timeouts definidos en pasarela; en despliegue productivo se agrega *rate limiting* por IP/usuario en API Gateway. |
| **API5:2023** | Broken Function Level Authorization | Un usuario regular ejecutando `/v1/operaciones/cierre` o `/v1/fiduciario/pronostico-flujos`. | Separación de routers (`/v1`, `/pasarela/v1`, endpoints demo aislados) y segregación de roles usuario vs. operador/fiduciario para producción. |
| **API6:2023** | Unrestricted Access to Sensitive Business Flows | Automatización abusiva de aportes o creación masiva de cuentas. | Límites de monto ($5–$1.000), mínimo por fideicomiso, validaciones de KYC/adhesión previa e idempotencia obligatoria. |
| **API8:2023** | Security Misconfiguration | CORS abierto (`*`), ausencia de cabeceras defensivas, Swagger expuesto sin control. | `MiddlewareSeguridadHTTP` (`X-Content-Type-Options`, `X-Frame-Options`, `CSP`, `HSTS`, `Referrer-Policy`, `Permissions-Policy`) y `CORSMiddleware` restrictivo vía `INVIERTEYA_CORS_ORIGINS` (`app/core/auditoria.py`). |
| **API9:2023** | Improper Inventory Management | Endpoints obsoletos o sin documentar. | Especificación OpenAPI 3 generada automáticamente desde el código (`docs/openapi.yaml` via `scripts/generar_openapi.py`) y escaneada en CI con OWASP ZAP. |
| **API10:2023** | Unsafe Consumption of APIs | Confiar ciegamente en respuestas de la pasarela o del fiduciario. | Validación de respuestas ISO 8583 (`0110/0230/0410`), manejo explícito de timeouts y conciliación diaria en 3 niveles. |

### 3.2 OWASP Top 10 (2021) — Controles complementarios

- **A01 Broken Access Control:** CORS restrictivo sin comodín (`*`), validación de adhesión previa antes de aportar.
- **A02 Cryptographic Failures:** TLS 1.3 en tránsito, AES-256-GCM en reposo, SHA-256 para integridad de adhesiones y bitácora (sin algoritmos débiles como MD5/SHA-1).
- **A03 Injection:** React escapa el DOM por defecto; ausencia de SQL concatenado o `eval()`/`exec()`; verificado automáticamente por **Bandit** en CI.
- **A04 Insecure Design:** arquitectura SAQ A (sin PAN en backend), principio de no bloqueo en perfil con confirmación expresa de riesgo y separación InvierteYa (propone) / Fiduciario (aprueba).
- **A05 Security Misconfiguration:** cabeceras HTTP seguras en todas las respuestas y permisos mínimos (`contents: read`) en GitHub Actions.
- **A06 Vulnerable and Outdated Components:** análisis SCA automático con `pip-audit` y `npm audit --audit-level=high` en cada PR.
- **A08 Software and Data Integrity Failures:** dependencias fijadas/auditadas, `hash_adhesion` y cadena SHA-256 en `BitacoraAuditoria`.
- **A09 Security Logging and Monitoring Failures:** `MiddlewareAuditoria` registra timestamp UTC, `usuario_id`, IP (`X-Forwarded-For` / cliente), operación, origen, destino y hashes enlazados (cumpliendo la trazabilidad exigida por la **Res. SUDEBAN 001.21**).

---

## 4. Pipeline DevSecOps en GitHub Actions (`.github/workflows/devsecops.yml`)

El pipeline se ejecuta automáticamente en cada `push` (`main`, `feat/**`), `pull_request` hacia `main` y de forma manual (`workflow_dispatch`), con principio de **menor privilegio** (`permissions: contents: read`).

| # | Job | Herramienta | Qué verifica | Artefacto / Evidencia |
|---|---|---|---|---|
| 1 | `tests-and-build` | `pytest`, `tsc -b`, `vite build` | Que las pruebas unitarias/integración pasen y que el front-end React/TS compile sin errores de tipos. | Log de CI en verde |
| 2 | `sast-bandit` | `bandit -r app ia scripts -ll` | Análisis estático del código Python buscando vulnerabilidades de severidad media/alta (inyecciones, cifrado débil, deserialización insegura). | `bandit-report.txt` |
| 3 | `sca-dependencies` | `pip-audit` + `npm audit --audit-level=high` | Vulnerabilidades conocidas (CVE) en dependencias Python (`requirements.txt`) y Node (`frontend/`). | `pip-audit-report.txt`, `npm-audit-report.txt` |
| 4 | `secret-scan-gitleaks` | `zricethezav/gitleaks` (`fetch-depth: 0`) | Escaneo completo del historial Git para detectar API keys, contraseñas o tokens expuestos accidentalmente. | `gitleaks-report.json` |
| 5 | `dast-owasp-zap` | `uvicorn` + `owasp/zap-baseline.py` | Levanta la API real en el runner y ejecuta escaneo dinámico pasivo contra `http://127.0.0.1:8000` (cabeceras, cookies, exposición de información). | `zap-report.html`, `zap-report.md` |

---

## 5. Hardening en FastAPI y Bitácora Inmutable (`app/core/auditoria.py`)

Para atender el comentario #5 de la Sesión 2 sin generar conflictos con el Track 2, el módulo expone `configurar_seguridad(app)` con tres capas:

1. **CORS restrictivo:** lista blanca configurable mediante `INVIERTEYA_CORS_ORIGINS` (por defecto solo orígenes locales `127.0.0.1:8000`, `localhost:8000`, `localhost:5173`), métodos explícitos y `allow_credentials=False` (autenticación por cabecera `Authorization`, no por cookies).
2. **Cabeceras de endurecimiento HTTP (`MiddlewareSeguridadHTTP`):**
   - `X-Content-Type-Options: nosniff` (evita MIME sniffing).
   - `X-Frame-Options: DENY` + `frame-ancestors 'none'` en CSP (bloquea *clickjacking*).
   - `Content-Security-Policy` restrictiva (`default-src 'self'`), con excepción acotada únicamente a `/docs` y `/redoc` para permitir los recursos de Swagger UI.
   - `Strict-Transport-Security`, `Referrer-Policy` y `Permissions-Policy`.
3. **Bitácora encadenada por hash SHA-256 (`BitacoraAuditoria` + `MiddlewareAuditoria`):**
   - Cada evento en ruta sensible guarda `timestamp`, `usuario_id`, `ip`, `operacion`, `origen`, `destino`, `hash_previo` y `hash_actual = SHA256(json_canonico_con_hash_previo)`.
   - `verificar_integridad()` recalcula toda la cadena desde el bloque génesis (`0 * 64`) y detecta cualquier alteración retroactiva.
   - Probado en `tests/test_auditoria_s3.py` (integridad, detección de manipulación, persistencia JSONL, cabeceras HTTP, CORS y captura automática de IP).

---

## 6. Registro de hallazgos y evidencias (`docs/seguridad/evidencias/`)

*(Se completa tras ejecutar el pipeline sobre el PR y luego sobre `main` en el Checkpoint 2).*

| Control | Fecha corrida | Estado | Hallazgos críticos/altos | Acción / Remediación | Evidencia |
|---|---|---|---|---|---|
| `tests-and-build` | *(pendiente PR)* | — | — | — | `docs/seguridad/evidencias/` |
| `sast-bandit` | *(pendiente PR)* | — | — | — | `docs/seguridad/evidencias/bandit-report.txt` |
| `sca-dependencies` | *(pendiente PR)* | — | — | — | `docs/seguridad/evidencias/pip-audit-report.txt` |
| `secret-scan-gitleaks` | *(pendiente PR)* | — | — | — | `docs/seguridad/evidencias/gitleaks-report.json` |
| `dast-owasp-zap` | *(pendiente PR)* | — | — | — | `docs/seguridad/evidencias/zap-report.md` |
