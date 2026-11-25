# Contrato de API e Interfaces Internas · Sesión 3 (Congelado)

**InvierteYa · Equipo D** · Versión `0.3.0-s3` · Fecha: 25-nov-2026

Este contrato sincroniza los 4 tracks paralelos (**Daniel / IA**, **Jesús / Backend**, **David / Front-end** y **Ronald / DevSecOps**).  
**Compatibilidad:** los endpoints de la Sesión 2 siguen funcionando (campos nuevos con valores por defecto cuando aplica) para no romper las pruebas `CP-01` a `CP-21`.

---

## 1. Catálogo de fideicomisos del banco (simulado)

### 1.1 Endpoint del banco fiduciario simulado
`GET /fiduciario/v1/fideicomisos` *(sin auth de usuario; consumido y cacheado diariamente por `app/core/catalogo.py`)*

Catálogo fijo de 5 fideicomisos simulados para el MVP:

| `id` | `nombre` | `riesgo` (1–5) | `horizonte` | `minimo_usd` | `comision_anual_pct` | `rescate_dias` | `valor_unidad` | `rendimiento_anual_simulado_pct` | `composicion` |
|---|---|---:|---|---:|---:|---|---:|---:|---|
| `liq_usd` | Liquidez USD | 1 | `< 1 año` | 5 | 1.0 | `T+1` | 1.05 | 4.2 | `{"renta_fija": 100, "fondos": 0, "acciones": 0}` |
| `rf_usd` | Renta Fija USD | 2 | `1 a 3 años` | 5 | 1.5 | `T+2` | 1.25 | 6.8 | `{"renta_fija": 80, "fondos": 20, "acciones": 0}` |
| `mix_bal` | Mixto Balanceado | 3 | `3 a 5 años` | 10 | 2.0 | `T+3` | 1.32 | 9.4 | `{"renta_fija": 40, "fondos": 30, "acciones": 30}` |
| `acc_bvc` | Acciones BVC | 4 | `> 5 años` | 10 | 2.5 | `T+3` | 1.40 | 13.5 | `{"renta_fija": 15, "fondos": 25, "acciones": 60}` |
| `crec_ves` | Crecimiento Bolívares | 5 | `> 5 años` | 20 | 2.5 | `T+5` | 1.18 | 16.0 | `{"renta_fija": 0, "fondos": 0, "acciones": 100}` |

### 1.2 Regla de idoneidad y etiquetas (`app/core/catalogo.py`)
- Riesgo máximo por perfil: `CONSERVADOR -> 2`, `MODERADO -> 3`, `AGRESIVO -> 5`.
- Etiqueta asignada a cada fideicomiso respecto al perfil del usuario:
  - `RECOMENDADO` (*"Recomendado para ti"*): `riesgo == riesgo_max` (o `riesgo in (4, 5)` para Agresivo, `riesgo in (1, 2)` con `2` principal para Conservador).
  - `COMPATIBLE` (*"Compatible"*): `riesgo < riesgo_max` (y no marcado principal).
  - `POR_ENCIMA_DEL_PERFIL` (*"Por encima de tu perfil"*): `riesgo > riesgo_max`.
- Orden de salida: primero `RECOMENDADO`, luego `COMPATIBLE`, al final `POR_ENCIMA_DEL_PERFIL`.

### 1.3 Endpoint InvierteYa para el front-end
`GET /v1/fideicomisos?usuario_id={id}&riesgo_max={1..5}`

```json
{
  "usuario_id": "usr_a1b2c3d4",
  "perfil_usuario": "MODERADO",
  "riesgo_maximo_perfil": 3,
  "nota_rendimiento": "Rendimientos históricos simulados; no garantizan resultados futuros.",
  "actualizado_en": "2026-11-25T08:00:00",
  "fideicomisos": [
    {
      "id": "mix_bal",
      "nombre": "Mixto Balanceado",
      "riesgo": 3,
      "horizonte": "3 a 5 años",
      "minimo_usd": 10.0,
      "comision_anual_pct": 2.0,
      "rescate_dias": "T+3",
      "valor_unidad": "1.32",
      "rendimiento_anual_simulado_pct": 9.4,
      "composicion": {"renta_fija": 40, "fondos": 30, "acciones": 30},
      "etiqueta": "RECOMENDADO",
      "etiqueta_texto": "Recomendado para ti",
      "requiere_confirmacion_riesgo": false,
      "adhesion_firmada": false
    }
  ]
}
```

---

## 2. KYC con edad + Cuestionario conversacional en 2 tandas

### 2.1 KYC simulado (provee la edad)
`POST /v1/usuarios/{usuario_id}/kyc`  
Body opcional: `{"edad": 24}` (default `24` si se omite). El usuario guarda `edad_kyc` y ya no se pregunta en el cuestionario.

### 2.2 Tanda 1 (6 preguntas antes del primer aporte)
`POST /v1/usuarios/{usuario_id}/perfil`

Acepta **formato S3** (preferido) o **formato S2** (retrocompatible). En S3:

```json
{
  "tanda": 1,
  "edad": 24,
  "ahorro_mensual_rango": 2,
  "horizonte_anios": 2.0,
  "objetivo": "crecer",
  "reaccion_caida_20": "esperar",
  "emergencia_200": "ahorros",
  "experiencia_tipo": "ahorro_dolares",
  "dependientes": null,
  "quiz_aciertos": null
}
```

Codificación exacta acordada entre **Daniel (IA)**, **Jesús (Backend)** y **David (Front-end)**:
- `edad`: entero `18..100` (viene del KYC si no se envía).
- `ahorro_mensual_rango`: `1` (\$5–\$20), `2` (\$20–\$50), `3` (\$50–\$100), `4` (más de \$100), o `null` (*"Prefiero no decirlo"*).
- `horizonte_anios`: `0.5` (*un imprevisto*), `2.0` (*una meta en 1–3 años*), `4.0` (*algo grande en 5 años*), `7.0` (*mi futuro*).
- `objetivo`: `"proteger"` | `"crecer"` | `"ganar_rapido"`.
- `reaccion_caida_20`: `"vender_todo"` | `"esperar"` | `"comprar_mas"`.
- `emergencia_200`: `"ahorros"` (*con mis ahorros*) | `"prestado"` (*pidiendo prestado*) | `"no_podria"` (*no podría*) | `null` (*"Prefiero no decirlo"*).
  - **Regla de seguridad dura:** si `emergencia_200` es `"no_podria"` o `null`, el perfil **nunca** puede ser `AGRESIVO`.
- `experiencia_tipo`: `"ninguna"` | `"ahorro_dolares"` | `"caja_ahorro"` | `"acciones"`.
- `dependientes` *(Tanda 2)*: `0..5` o `null`.
- `quiz_aciertos` *(Tanda 2)*: `0`, `1`, `2` (2 preguntas de quiz amistoso) o `null`.

### 2.3 Tanda 2 (*"Afinemos tu perfil"*, 3 preguntas después del primer aporte)
`PATCH /v1/usuarios/{usuario_id}/perfil/tanda2`
```json
{
  "dependientes": 0,
  "quiz_aciertos": 2
}
```
Recalcula el perfil combinando la Tanda 1 guardada + Tanda 2 y devuelve el mismo `PerfilOut`.

### 2.4 Respuesta `PerfilOut` (extensiones S3)
Además de todos los campos de S2 (`perfil`, `puntaje`, `puntaje_maximo`, `explicacion`, `factores_suben`, `factores_moderan`, `avisos`, `leccion`, `motor`, `perfil_reglas`, `probabilidad`, `probabilidades`, `revision_humana`), incluye:

```json
{
  "tanda_completada": 1,
  "campos_omitidos": ["ahorro_mensual_rango"],
  "que_cambiaria": [
    "Si tuvieras un horizonte de más de 5 años, tu perfil podría subir a Agresivo.",
    "Si ante una caída de $100 a $80 eligieras vender todo, bajaría a Conservador."
  ],
  "aviso_transparencia": "Esta sugerencia la hace un modelo automático; tú decides y un asesor puede revisarla.",
  "nota_rendimiento": "El rendimiento histórico no garantiza resultados futuros."
}
```

### 2.5 Desacuerdo con el perfil → revisión humana
`POST /v1/usuarios/{usuario_id}/perfil/revision`
```json
{
  "motivo": "Creo que mi tolerancia es más conservadora"
}
```
Respuesta `201`: `{"revision_id": "rev_...", "estado": "PENDIENTE_ASESOR", "mensaje": "Un asesor humano revisará tu perfil."}`

---

## 3. Adhesión por fideicomiso y Aporte repartido

### 3.1 Adhesión por fideicomiso (firma electrónica con hash)
`POST /v1/usuarios/{usuario_id}/adhesion`
```json
{
  "acepta": true,
  "fideicomiso_id": "acc_bvc",
  "confirmacion_riesgo_extra": true
}
```
- Si `fideicomiso_id` está `POR_ENCIMA_DEL_PERFIL` y `confirmacion_riesgo_extra` es `false` → HTTP `422`, `codigo: "CONFIRMACION_RIESGO_REQUERIDA"`.
- Si se omite `fideicomiso_id` (compatibilidad S2), adhiere al fideicomiso recomendado por defecto del perfil.
- Respuesta incluye: `fideicomiso_id`, `sello_tiempo` (ISO 8601), `hash_adhesion` (SHA-256), `confirmacion_riesgo_extra`.

### 3.2 Aporte con distribución y medio de pago
`POST /v1/aportes` (Header obligatorio: `Idempotency-Key`)
```json
{
  "usuario_id": "usr_a1b2c3d4",
  "monto": 100.0,
  "token_tarjeta": "tok_abc123",
  "medio_pago": "TARJETA",
  "distribucion": [
    {"fideicomiso_id": "rf_usd", "porcentaje": 70},
    {"fideicomiso_id": "mix_bal", "porcentaje": 30}
  ]
}
```
- Validaciones obligatorias (HTTP `422`):
  - La suma de `porcentaje` debe ser exactamente `100` (`DISTRIBUCION_INVALIDA`).
  - Cada `fideicomiso_id` debe tener adhesión firmada (`ADHESION_PENDIENTE`).
  - El monto asignado a cada fideicomiso debe cumplir su `minimo_usd` (`MONTO_MINIMO_FIDEICOMISO`).
- Transparencia de comisiones (Res. SUDEBAN 063.15):
  - `comision_aporte_pct`: `1.0` siempre.
  - `recargo_medio_pago_pct`: `2.0` si `medio_pago == "TARJETA"`; `0.0` si `medio_pago in ("PAGO_MOVIL", "TRANSFERENCIA")`.
- La respuesta `AporteOut` agrega `medio_pago`, `comision_total_usd`, `asignaciones: [{fideicomiso_id, nombre, porcentaje, monto, unidades, valor_unidad}]`.

### 3.3 Portafolio consolidado
`GET /v1/usuarios/{usuario_id}/portafolio`
- Mantiene campos consolidados (`saldo`, `unidades`, `aportes`, `leccion`) y agrega:
  - `fideicomisos`: lista con `{fideicomiso_id, nombre, riesgo, unidades, valor_unidad, saldo, composicion, comision_anual_pct}`.

---

## 4. Endpoints de IA Predictiva (contrato `ia/` ↔ `app/`)

### 4.1 Riesgo de abandono del ahorro
`GET /v1/usuarios/{usuario_id}/riesgo-abandono`  
*(Opcional query param de demo: `?simular_inactivo=true` para mostrar el aviso suave en la presentación).*

**Contrato Python que implementa Daniel (`ia/predictor_abandono.py`) y llama Jesús:**
```python
from ia.predictor_abandono import predecir_abandono

resultado = predecir_abandono({
    "meses_activo": 4,
    "aportes_90d": 1,
    "dias_desde_ultimo_aporte": 48,
    "pct_pagos_rechazados": 0.25,
    "sesiones_por_mes": 1.5,
    "lecciones_vistas": 2,
    "perfil": "MODERADO",
    "monto_promedio": 20.0,
    "tuvo_caida_unidad": True,
})
```
**Respuesta JSON del endpoint:**
```json
{
  "usuario_id": "usr_a1b2c3d4",
  "probabilidad_abandono": 0.78,
  "en_riesgo": true,
  "nivel_riesgo": "ALTO",
  "umbral_alerta": 0.45,
  "factores": [
    "Llevas 48 días sin realizar un aporte",
    "Tienes 25% de intentos de pago rechazados"
  ],
  "sugerencia_suave": "¿Quieres programar tu aporte de $10 cada quincena?",
  "accion_permitida": "SOLO_SUGERIR_RECORDATORIO",
  "aviso_etico": "Este aviso solo busca ayudarte a mantener tu meta; nunca genera cobros ni restricciones.",
  "motor": "modelo abandono: gradient boosting (entrenado con datos sintéticos)"
}
```

### 4.2 Pronóstico de flujos para el banco fiduciario
`GET /v1/fiduciario/pronostico-flujos`

**Contrato Python que implementa Daniel (`ia/pronostico_flujos.py`) y llama Jesús:**
```python
from ia.pronostico_flujos import obtener_pronostico_fiduciario
resultado = obtener_pronostico_fiduciario()
```
**Respuesta JSON del endpoint:**
```json
{
  "modelo_elegido": "regresion_lineal_rezagos",
  "fecha_corte": "2026-11-25",
  "por_fideicomiso": [
    {
      "fideicomiso_id": "rf_usd",
      "nombre": "Renta Fija USD",
      "flujo_neto_manana_usd": 1420.5,
      "flujo_neto_7d_usd": 9850.0,
      "mae_usd": 115.2,
      "mape_pct": 8.4
    }
  ],
  "total_manana_usd": 4850.0,
  "total_7d_usd": 33900.0,
  "nota": "Pronóstico basado en serie diaria sintética para planificación de lotes del fiduciario."
}
```

---

## 5. Privacidad, Consentimiento y Auditoría (Jesús + Ronald)

- `PUT /v1/usuarios/{usuario_id}/consentimiento`  
  Body: `{"informes_agregados": true, "alertas_ahorro": true}`  
  Permite otorgar o retirar el consentimiento separado de los términos en cualquier momento.
- `GET /v1/usuarios/{usuario_id}/datos-personales`  
  Derecho de acceso (habeas data, Constitución art. 28): devuelve resumen de datos guardados y estado de consentimientos.
- `DELETE /v1/usuarios/{usuario_id}/datos-personales`  
  Derecho de supresión/anonimización de datos de uso (conservando solo el registro contable exigido por normativa LC/FT al banco).
- **Auditoría inmutable (`app/core/auditoria.py`, Ronald):** cada operación sensible (`POST /v1/aportes`, `POST /v1/usuarios/{id}/adhesion`, `POST /v1/usuarios/{id}/perfil`) registra `{timestamp, usuario_id, ip, operacion, origen, destino, hash_previo, hash_actual}`.
