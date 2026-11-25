# Ficha del dataset sintético · Perfil de riesgo (Actualizado Sesión 3)

**InvierteYa · Equipo D · Sesión 3** — Archivo: `data/dataset_sintetico.csv` · Generador: `ia/generar_dataset.py`

> **100% sintético.** Ninguna fila corresponde a una persona real. No hay nombres, cédulas,
> correos, teléfonos ni datos de tarjetas. Cumple la regla de la cátedra: solo datos sintéticos.

## 1. Qué cambió en la Sesión 3 (respuesta al comentario #4)

Para reducir la fricción y aumentar la confianza del usuario, el cuestionario directo de 10 preguntas de la
Sesión 2 se rediseñó como un **cuestionario conversacional por situaciones en 2 tandas**:

- **Edad:** ya no se pregunta; proviene del KYC simulado.
- **Ingreso y % invertible:** se reemplazan por *"¿Cuánto podrías apartar al mes sin apretarte?"*
  (`ahorro_mensual_rango`: 1 = \$5–\$20, 2 = \$20–\$50, 3 = \$50–\$100, 4 = más de \$100) con opción
  **"Prefiero no decirlo"** (`ahorro_omitido = True`, simulado en **11,3%** de los usuarios).
- **Fondo de emergencia:** pasa a situación concreta *"Si mañana tuvieras un gasto imprevisto de \$200,
  ¿cómo lo cubrirías?"* (`emergencia_200`: `ahorros` / `prestado` / `no_podria` / faltante en **5,9%**).
  La regla de seguridad **"nunca Agresivo"** se mantiene cuando la respuesta es `no_podria` o faltante.
- **Experiencia previa:** pasa a productos cotidianos (`experiencia_tipo`: `ninguna`, `ahorro_dolares`,
  `caja_ahorro`, `acciones`).
- **Dos tandas:** Tanda 1 (6 preguntas antes del primer aporte) y Tanda 2 (*"Afinemos tu perfil"*: hogar +
  2 preguntas de quiz amistoso). En el dataset, **21,3%** de los usuarios operan inicialmente solo con
  Tanda 1 (dependientes y conocimiento como faltantes tratados de forma prudente).

## 2. Resumen del dataset generado (semilla 42)

| Dato | Valor |
|---|---|
| Filas | 5.000 usuarios sintéticos (`syn_00001` a `syn_05000`) |
| Distribución de perfiles | Conservador **1.739 (34,8%)** · Moderado **2.788 (55,8%)** · Agresivo **473 (9,5%)** |
| Uso de *"Prefiero no decirlo"* | Ahorro mensual: **11,3%** · Imprevisto \$200: **5,9%** |
| Solo Tanda 1 completada | **21,3%** (1.066 usuarios) |
| División | 80% entrenamiento (4.000) / 20% prueba (1.000), estratificada |

## 3. Regla de etiquetado y trazabilidad

Se conserva la metodología transparente de la Sesión 2 (`app/core/perfil.py`): puntaje de idoneidad
(máximo 19 puntos, tratando los campos omitidos con puntaje prudente 0) + ruido gaussiano ($\sigma = 0,70$)
+ cortes (`< 7` Conservador, `< 13` Moderado, `>= 13` Agresivo) + regla dura sin fondo de emergencia nunca
Agresivo. Las columnas de trazabilidad `puntaje_reglas`, `ruido` y `puntaje_con_ruido` se guardan para
auditoría pero **no** entran al modelo.

## 4. Cómo regenerarlo

```bash
python ia/generar_dataset.py            # 5.000 filas, semilla 42
python ia/generar_dataset.py --n 10000  # otro tamaño
```
