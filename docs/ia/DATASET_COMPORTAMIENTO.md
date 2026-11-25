# Ficha del dataset sintético · Comportamiento y flujos diarios (Sesión 3)

**InvierteYa · Equipo D · Sesión 3**  
Archivos: `data/dataset_comportamiento.csv` y `data/dataset_flujos_diarios.csv`  
Generador: `ia/generar_dataset_comportamiento.py`

> **100% sintético.** Ninguna fila corresponde a una persona real ni a operaciones reales. No contiene
> nombres, cédulas, correos, teléfonos ni números de tarjeta (PAN). Semilla fija (`42`) para
> reproducibilidad total.

---

## 1. Propósito

Soportar los dos modelos predictivos nuevos de la Sesión 3 (respuesta al comentario #2 del docente):

1. **Modelo de abandono del ahorro (60 días):** predecir la probabilidad de que un usuario deje de
   aportar en los próximos dos meses (`data/dataset_comportamiento.csv`).
2. **Pronóstico de flujos para el banco fiduciario:** estimar los aportes netos diarios y semanales
   por fideicomiso para dimensionar las órdenes por lote (`data/dataset_flujos_diarios.csv`).

---

## 2. Dataset de comportamiento (`data/dataset_comportamiento.csv`)

| Dato | Valor |
|---|---|
| Universo | 5.000 usuarios sintéticos (`syn_00001` a `syn_05000`) × 12 meses |
| Filas activas | **58.004** registros usuario-mes (ingreso escalonado en meses 1 a 3) |
| Tasa global de abandono 60d (meses 1–10) | **35,4%** |
| Tasa de abandono en el corte de prueba (mes 10 → meses 11–12) | **48,5%** (5.000 usuarios evaluados) |
| División temporal sin fuga del futuro | Entrenamiento: cortes meses **3–7** (25.000 filas; etiquetas en meses 4–9) · Prueba: corte mes **10** (5.000 filas; etiquetas en meses **11–12**) |
| Semilla | `42` |

### Variables al corte $t$ (calculadas estrictamente con historial $\le t$)

| # | Variable | Tipo | Descripción |
|---|---|---|---|
| 1 | `meses_activo` | entero | Meses transcurridos desde el alta del usuario |
| 2 | `aportes_90d` | entero | Número de aportes aprobados en los últimos 90 días (meses $t-2$ a $t$) |
| 3 | `dias_desde_ultimo_aporte` | entero | Días desde el último aporte aprobado (1 a 360) |
| 4 | `pct_pagos_rechazados` | decimal [0,1] | Proporción de intentos rechazados (códigos ISO `51` fondos insuficientes y `05` no honrar) en 90 días |
| 5 | `sesiones_por_mes` | decimal | Promedio de sesiones en la app por mes en la ventana de 90 días |
| 6 | `lecciones_vistas` | entero | Lecciones del tutor didáctico vistas de forma acumulada |
| 7 | `perfil` | categórica | `CONSERVADOR` (28%), `MODERADO` (60%), `AGRESIVO` (12%) |
| 8 | `monto_promedio` | decimal (USD) | Monto promedio histórico de los aportes aprobados del usuario |
| 9 | `tuvo_caida_unidad` | binaria (0/1) | Si el fideicomiso del usuario sufrió una caída temporal del valor de la unidad en 90 días |

Además se conservan `edad` y `ahorro_mensual_rango` (1 a 4) exclusivamente para **auditar sesgos por
grupo** (no entran como predictores del abandono), y `abandona_60d` (1 si realiza 0 aportes en $t+1$ y
$t+2$, `NaN` en meses 11 y 12 porque el horizonte de 60 días no ha cerrado).

### Dinámica simulada (reglas + ruido)

Un estado latente de compromiso (*no exportado al CSV*) evoluciona cada mes:
- **Refuerzan el hábito:** aportes exitosos y consumo de microlecciones del tutor.
- **Erosionan el hábito:** meses sin aportar, pagos rechazados (`51`/`05`), rescates y caídas del valor
  de la unidad (con mayor impacto en usuarios Conservadores y Moderados).
- **Ruido gaussiano mensual** ($\sigma = 0,48$) para evitar separaciones artificialmente perfectas.

---

## 3. Serie diaria de flujos (`data/dataset_flujos_diarios.csv`)

| Dato | Valor |
|---|---|
| Horizonte | **365 días** (`2025-11-26` a `2026-11-25`) × **5 fideicomisos** = **1.825 filas** |
| Fideicomisos | `liq_usd` (Liquidez USD), `rf_usd` (Renta Fija USD), `mix_bal` (Mixto Balanceado), `acc_bvc` (Acciones BVC), `crec_ves` (Crecimiento Bolívares) |
| Variables | `fecha`, `dia_idx`, `dia_semana`, `es_quincena`, `fideicomiso_id`, `aportes_brutos_usd`, `rescates_usd`, `flujo_neto_usd` |
| Estacionalidad simulada | Picos de quincena (días 14–16 y 29–1), menor actividad los fines de semana y tendencia gradual hacia el SOM de la Sesión 1 |
| División temporal | Entrenamiento: primeros **305 días** · Prueba: últimos **60 días** |

---

## 4. Supuestos y limitaciones

- Las tasas de rechazo, rescates, sensibilidad a caídas y estacionalidad de quincena son **supuestos del
  equipo** para el MVP. Antes de producción deben recalibrarse con historial real seudonimizado (capa
  Plata) y consentimiento del usuario.
- Al ser datos sintéticos, el desempeño medido demuestra que el pipeline temporal funciona sin fuga del
  futuro y captura señales de comportamiento realistas, no que el comportamiento de clientes reales sea
  idéntico.

## 5. Reproducibilidad

```bash
python ia/generar_dataset_comportamiento.py
```
