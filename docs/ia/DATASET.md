# Ficha del dataset sintético · Perfil de riesgo

**InvierteYa · Equipo D · Sesión 2** — Archivo: `data/dataset_sintetico.csv` · Generador: `ia/generar_dataset.py`

> **100% sintético.** Ninguna fila corresponde a una persona real. No hay nombres, cédulas,
> correos, teléfonos ni datos de tarjetas. Cumple la regla de la cátedra: solo datos sintéticos.

## 1. Para qué sirve

Entrenar y evaluar el **modelo baseline** que clasifica a un usuario como **Conservador, Moderado o
Agresivo** a partir de las 10 respuestas del cuestionario definido en la ficha del componente de IA
(Sesión 1). Como InvierteYa todavía no tiene usuarios, no existen datos reales: se simulan.

## 2. Resumen

| Dato | Valor |
|---|---|
| Filas | 5.000 usuarios ficticios (`syn_00001` a `syn_05000`) |
| Columnas | `id` + 10 variables del cuestionario + 3 columnas de trazabilidad + `perfil` (etiqueta) |
| Semilla | 42 (el archivo se regenera idéntico con `python ia/generar_dataset.py`) |
| Etiquetas | Conservador 1.382 (27,6%) · Moderado 3.109 (62,2%) · Agresivo 509 (10,2%) |
| División | 80% entrenamiento (4.000) / 20% prueba (1.000), estratificada |

## 3. Variables

| # | Variable | Tipo | Valores | Distribución simulada |
|---|---|---|---|---|
| 1 | `edad` | entero | 18 a 65 | 70% entre 20 y 40 años (segmento principal de la Sesión 1); media 33 |
| 2 | `ingreso_rango` | ordinal | 1 (más bajo) a 5 | 25% · 30% · 24% · 13% · 8% |
| 3 | `pct_invertible` | entero | 1% a 50% del ingreso | mediana 13%; sube con el ingreso |
| 4 | `horizonte_anios` | numérico | 0,5 · 1 · 2 · 3 · 5 · 7 · 10 | más largo en menores de 35 |
| 5 | `objetivo` | categórica | proteger · crecer · ganar_rapido | 33% · 46% · 21% |
| 6 | `reaccion_caida_20` | categórica | vender_todo · esperar · comprar_mas | 32% · 40% · 28% |
| 7 | `experiencia_previa` | sí/no | | 21% sí |
| 8 | `fondo_emergencia` | sí/no | | 55% sí; más probable con mayor ingreso |
| 9 | `dependientes` | entero | 0 a 5 | 51% sin dependientes; más con la edad |
| 10 | `conocimiento` | ordinal | 1 a 5 (autoevaluado) | 68% en niveles 1-2 (público que nunca invirtió) |

**Coherencia entre respuestas.** Se usa un rasgo latente de *tolerancia al riesgo* (normal estándar,
**no se guarda en el CSV**) que influye en el objetivo, la reacción ante caídas, el horizonte, la
experiencia y el % invertible. Así, quien quiere "ganar rápido" tiende a no vender ante una caída,
como pasa en un cuestionario real. Sin este rasgo, casi todos los usuarios quedaban como Moderados
(solo 5% Agresivos) y el modelo no tenía ejemplos suficientes de esa clase.

**Columnas de trazabilidad** (no las ve el modelo): `puntaje_reglas` (0 a 19), `ruido` y
`puntaje_con_ruido`. Permiten auditar por qué cada fila tiene su etiqueta.

## 4. Cómo se asigna la etiqueta

1. **Puntaje de idoneidad** con la misma regla del prototipo (`app/core/perfil.py`, máximo 19 puntos):
   horizonte (0-3), objetivo (0-3), reacción ante una caída del 20% (0-3), % invertible (0-2),
   edad (0-2), experiencia (0-1), conocimiento (0-2), sin dependientes (0-1) e ingreso (0-2).
2. **Ruido gaussiano** (desviación de 0,75 puntos). Representa que dos asesores no siempre coinciden
   con un cliente que está cerca del límite entre dos perfiles. Por el ruido, el **7,2%** de las
   etiquetas cambia respecto de la regla pura. Por eso **ningún modelo puede llegar al 100%**: el techo
   práctico ronda el 93%.
3. **Cortes:** menos de 7 puntos → Conservador; de 7 a menos de 13 → Moderado; 13 o más → Agresivo.
4. **Regla de seguridad:** sin fondo de emergencia nunca Agresivo (pasa a Moderado). Afecta al 7,2%
   de las filas.

## 5. Supuestos y limitaciones

- Las distribuciones, los puntajes y los cortes son **supuestos del equipo**: no salen de una encuesta
  ni de un estudio. Deben recalibrarse con datos reales (con consentimiento) antes de producción.
- El modelo aprende a imitar una regla definida por el equipo. Una exactitud alta mide **qué tan bien
  reproduce el criterio de idoneidad**, no si la recomendación es buena para el usuario.
- La clase Agresivo es minoritaria (10%), así que su F1 es la métrica más frágil.
- `edad` e `ingreso` son variables de idoneidad habituales, pero pueden introducir sesgo. Por eso se
  miden métricas por grupo (ver la ficha del modelo).

## 6. Cómo regenerarlo

```bash
python ia/generar_dataset.py            # 5.000 filas, semilla 42
python ia/generar_dataset.py --n 10000  # otro tamaño
```
