# Especificación de API y mapeo de mensajería ISO 8583

**InvierteYa · Equipo D · Sesión 2** — Especificación completa: `docs/openapi.yaml` (OpenAPI 3) ·
Código: `app/main.py`, `app/core/iso8583.py`, `app/core/pasarela_simulada.py`

> **Simulado:** la pasarela aliada, el adquirente, el suiche y el emisor son servicios simulados del
> prototipo. InvierteYa **no** arma mensajes ISO 8583 en producción: eso lo hace la pasarela
> certificada. El prototipo los genera para mostrar qué pasa en ese tramo de la cadena.

## 1. Dos tramos de mensajería

```
Tramo 1 (REST/JSON, OpenAPI 3):
  Usuario → App InvierteYa → Backend InvierteYa → Pasarela aliada

Tramo 2 (ISO 8583, versión 1987):
  Pasarela aliada → Banco adquirente → Suiche → Banco emisor
```

| Tramo | Protocolo | Quién lo implementa | Dónde está especificado |
|---|---|---|---|
| InvierteYa ↔ Pasarela aliada | API REST/JSON sobre TLS, autenticación con token, encabezado `Idempotency-Key` | InvierteYa (cliente) | `docs/openapi.yaml` |
| Pasarela ↔ Adquirente ↔ Suiche ↔ Emisor | ISO 8583:1987 | Pasarela certificada (fase 1) | Tablas 3 a 5 de este documento |

## 2. API de InvierteYa (OpenAPI 3) — 15 rutas

| Método y ruta | Qué hace | Grupo |
|---|---|---|
| `POST /v1/usuarios` | Registrar usuario (datos sintéticos) | Usuarios |
| `POST /v1/usuarios/{id}/kyc` | KYC simulado; el resultado se comparte con el banco fiduciario | Usuarios |
| `POST /v1/usuarios/{id}/adhesion` | Firmar el contrato de adhesión al fideicomiso | Usuarios |
| `POST /v1/usuarios/{id}/perfil` | Cuestionario → perfil (modelo de IA) + probabilidad + explicación + lección | Perfil y tutor |
| `GET /v1/lecciones` | Tutor predefinido: lección según paso, perfil y nivel | Perfil y tutor |
| `POST /v1/aportes` | Aporte: autorización → captura → asignación de unidades (reverso si falla) | Aportes |
| `GET /v1/aportes/{id}` | Consultar un aporte y su traza ISO 8583 | Aportes |
| `GET /v1/usuarios/{id}/portafolio` | Unidades, valor de la unidad y saldo | Aportes |
| `POST /v1/operaciones/cierre` | Cierre T+1: liquidación, conciliación en 3 niveles y propuesta de órdenes por lote | Operaciones |
| `POST /pasarela/v1/tokens` | Tokenizar tarjeta de PRUEBA (el PAN no llega a InvierteYa) | Pasarela simulada |
| `POST /pasarela/v1/authorizations` | Autorización | Pasarela simulada |
| `POST /pasarela/v1/captures` | Captura | Pasarela simulada |
| `POST /pasarela/v1/reversals` | Reverso | Pasarela simulada |
| `POST /pasarela/v1/refunds` | Devolución de un cobro ya capturado | Pasarela simulada |
| `GET /pasarela/v1/settlements/{fecha}` | Archivo de liquidación diario | Pasarela simulada |

## 3. Operaciones: API ↔ mensajes ISO 8583

| Operación | Llamada a la pasarela | MTI ISO 8583 | Significado del MTI |
|---|---|---|---|
| Autorización | `POST /authorizations` | **0100** / **0110** | Solicitud de autorización / respuesta |
| Captura | `POST /captures` | **0220** / **0230** | Aviso financiero del adquirente (completa una transacción autorizada antes) / respuesta al aviso |
| Reverso | `POST /reversals` | **0400** / **0410** | Solicitud de reverso del adquirente / respuesta |
| Reverso sin respuesta | (lo hace la pasarela) | **0420** → **0421** ×3 → espera **0430** | Aviso de reverso; repeticiones del aviso; respuesta al aviso |
| Cierre y conciliación | `GET /settlements/{fecha}` | **0500** / **0510** | Conciliación del adquirente / respuesta |

**Cómo se lee un MTI** (4 dígitos): versión (0 = 1987) · clase (1 autorización, 2 financiero,
4 reverso, 5 conciliación) · función (0 solicitud, 1 respuesta, 2 aviso, 3 respuesta al aviso) ·
origen (0 adquirente, 1 repetición del adquirente). Por eso **0421** = aviso de reverso (`42`)
repetido por el adquirente (`1`).

## 4. Campos: API ↔ ISO 8583

| Dato | Campo de la API (pasarela) | Campo ISO 8583 | Formato | Mensajes donde va |
|---|---|---|---|---|
| Número de tarjeta (PAN) | **Nunca llega a InvierteYa:** se envía `token` | **2** — PAN | n..19 | 0100 (la pasarela lo resuelve desde el token) |
| Tipo de operación | implícito en la ruta (`/authorizations`) | **3** — código de proceso | n6 | 0100 (`000000` = compra) |
| Monto | `amount` (en centavos) | **4** — monto de la transacción | n12 | 0100, 0220, 0400/0420/0421 |
| Fecha y hora de envío | (lo pone la pasarela) | **7** — fecha/hora de transmisión | n10 (MMDDhhmmss) | Todos |
| Número de traza | (lo pone la pasarela) | **11** — STAN | n6 | Todos |
| Referencia de recuperación | `rrn` (respuesta) | **37** — RRN | an12 | 0110, 0220 |
| Código de autorización | `auth_code` (respuesta) | **38** — identificación de la autorización | an6 | 0110 (si se aprueba), 0220 |
| Resultado | `response_code` y `status` (respuesta) | **39** — código de respuesta | an2 | 0110, 0230, 0410 |
| Terminal | (configurado en la pasarela: `INVYA001`) | **41** — terminal del comercio | ans8 | 0100 |
| Comercio | (configurado en la pasarela: `INVIERTEYA00001`) | **42** — identificación del comercio | ans15 | 0100 |
| Moneda | `currency` (`USD`) | **49** — moneda de la transacción | n3 (ISO 4217) | 0100 |
| Número de aportes del día | `cantidad` (liquidación) | **76** — número de débitos | n10 | 0500 |
| Total de aportes del día | `monto_bruto` (liquidación) | **88** — monto total de débitos | n16 | 0500 |
| Transacción original | `original_reference` | **90** — datos originales: MTI (4) + STAN (6) + fecha/hora (10) + id. adquirente (11) + id. reenviador (11) | n42 | 0400, 0420, 0421 |

`reference` (referencia propia del aporte) y `Idempotency-Key` viajan solo en la API: no tienen
campo ISO equivalente y sirven para evitar cobros dobles.

## 5. Códigos de respuesta (campo 39) y qué hace InvierteYa

| Código | Significado | Qué ve el usuario / qué hace el sistema |
|---|---|---|
| `00` | Aprobada | Se captura y se asignan las unidades (aparece el tutor) |
| `05` | No honrar (rechazo del emisor) | Mensaje genérico: comunícate con tu banco o usa otra tarjeta |
| `12` | Transacción inválida | Lo usa la pasarela simulada para una devolución no permitida |
| `14` | Número de tarjeta inválido | Token inválido: pedir de nuevo los datos de la tarjeta |
| `25` | No se encuentra el registro | Reverso de una autorización que no existe |
| `51` | Fondos insuficientes | "Tu banco no aprobó el pago, posiblemente por saldo insuficiente" |
| `59` | Sospecha de fraude | **Mensaje genérico** (no se revela el motivo) |
| `91` | Emisor o suiche no disponible | Mensaje genérico; como no hubo aprobación, no hay nada que reversar y el usuario puede reintentar |
| `96` | Falla del sistema | Falla de captura: reverso automático (0400) |
| (sin respuesta en 30 s) | Timeout | Reverso automático (0400) |

El tutor **no** aparece cuando se rechaza un pago: InvierteYa no conoce la causa real.

## 6. Monedas (campo 49, ISO 4217)

| Código | Número | Moneda | Uso en InvierteYa |
|---|---|---|---|
| USD | **840** | Dólar estadounidense | Moneda de los aportes en el prototipo |
| VES | **928** | Bolívar soberano (desde el 20-ago-2018) | Activo en ISO 4217 |
| VED | **926** | Bolívar digital (desde el 1-oct-2021) | Activo en ISO 4217 |

**Decisión de diseño:** el prototipo opera en USD (840). Como ISO 4217 mantiene hoy **dos** códigos
activos para Venezuela, si en la fase 2 se aceptan aportes en bolívares se usará el que exija la
especificación de la pasarela aliada.

## 7. Verificación del mapeo (8-nov-2026)

| Elemento | Qué establece el estándar | Cómo se implementó en el prototipo |
|---|---|---|
| Reverso sin respuesta | 0421 es la **repetición de un aviso 0420** (función 2 = aviso, origen 1 = repetición) | 0400 → (sin 0410) → **aviso 0420** → 3 repeticiones **0421** → espera **0430** (prueba CP-07 y diagrama 3) |
| Totales de la conciliación 0500 | 74/86 = créditos; 76/88 = débitos | Los aportes son **débitos** a la tarjeta: se usan el campo **76** (número) y el **88** (monto) |
| Moneda (campo 49) | ISO 4217: USD 840; para Venezuela están activos VES 928 y VED 926 | USD 840 en el prototipo; para bolívares, el código que exija la pasarela (fase 2) |

Los demás elementos (MTI 0100/0110, 0220/0230, 0400/0410, 0500/0510 y los campos 2, 3, 4, 7, 11,
37, 38, 39, 41, 42, 49 y 90) **coinciden** con las fuentes.

## 8. Fuentes

- ISO 8583-1:1987 / ISO 8583-1:2003. *Financial transaction card originated messages — Interchange
  message specifications*. ISO, Ginebra. Norma de referencia (de acceso pago); la verificación se realizó con
  las fuentes públicas siguientes.
- Wikipedia. *ISO 8583* (estructura del MTI: clase, función y origen; MTI 0100, 0110, 0220, 0230, 0400,
  0420, 0430, 0510; tabla de campos con tipo y longitud). https://en.wikipedia.org/wiki/ISO_8583
  (consultado el 8-nov-2026).
- NIBSS. *POS Interface Specifications — ISO 8583 (1987 version)*: definición de DE90 (n42 y sus 5
  subcampos) y de DE39, DE41 y DE42.
  https://testdocs.nibss-plc.com.ng/pos/pos-interface-specifications-iso-8583-1987-version/data-element-definition-de90-de123
  y …/data-element-definition-de39-de48 (consultado el 8-nov-2026).
- 2C2P. *Response Code – Card (ISO 8583)*: significado de los códigos 00, 05, 12, 14, 25, 51, 59, 91 y 96.
  https://developer.2c2p.com/docs/response-code-card-iso-8583 (consultado el 8-nov-2026).
- Worldpay (FIS). *ISO 8583 Reference Guide V2.46* (índice: 0220/0230 aviso financiero, 0420/0430
  reverso, 0500/0510 conciliación del adquirente).
  https://developerengine.fisglobal.com/assets/pdf/Worldpay_ISO_8583_Reference_Guide_V2.46.pdf
- SIX Group (agencia de mantenimiento de ISO 4217). *ISO 4217 Amendment 168*: alta de VES 928 el
  20-ago-2018.
  https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/amendments/dl_currency_iso_amendment_168.pdf
- Wikipedia. *ISO 4217*, tabla de códigos activos (USD 840, VES 928, VED 926).
  https://en.wikipedia.org/wiki/ISO_4217 (consultado el 8-nov-2026).
