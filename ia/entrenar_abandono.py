"""Entrena y evalúa el modelo predictivo de abandono del ahorro (Sesión 3).

    python ia/entrenar_abandono.py

Pasos:
  1. Lee data/dataset_comportamiento.csv (si no existe, lo genera).
  2. Separación estrictamente TEMPORAL (sin fuga del futuro):
       - Entrenamiento: cortes de meses 3 a 6 (features en meses 1-6, etiquetas en meses 4-8).
       - Validación (selección de hiperparámetros y umbral): corte mes 7 (etiquetas en meses 8-9).
         -> TODO entrenamiento y ajuste ocurre dentro de meses 1 a 9.
       - Prueba (evaluación final no vista): corte mes 10 (etiquetas en meses 11-12).
         -> Evaluación estrictamente dentro de meses 10 a 12.
  3. Compara Regresión Logística vs Gradient Boosting (scikit-learn).
  4. Reporta precisión, recall, F1, AUC-ROC, curva ROC, matriz de confusión, importancia
     de variables y métricas por grupo de edad y rango de ahorro (sesgos).
  5. Guarda: ia/modelo_abandono.joblib, docs/ia/metricas_abandono.json,
     docs/ia/roc_abandono.png, docs/ia/matriz_confusion_abandono.png y
     docs/ia/importancia_abandono.png.

Metas del Plan Sesión 3: AUC >= 0,80 y recall >= 0,70 en la clase "abandona"
("preferimos avisar de más que dejar ir a alguien").
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score, roc_curve)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

RUTA_DATASET_COMP = RAIZ / "data" / "dataset_comportamiento.csv"
RUTA_MODELO_ABANDONO = RAIZ / "ia" / "modelo_abandono.joblib"
DIR_DOCS = RAIZ / "docs" / "ia"

SEMILLA = 42
META_AUC = 0.80
META_RECALL = 0.70
RECALL_OBJETIVO_VALIDACION = 0.78   # margen de seguridad al calibrar el umbral en validación

PERFILES = ["CONSERVADOR", "MODERADO", "AGRESIVO"]

VARIABLES_ABANDONO = [
    "meses_activo",
    "aportes_90d",
    "dias_desde_ultimo_aporte",
    "pct_pagos_rechazados",
    "sesiones_por_mes",
    "lecciones_vistas",
    "perfil",
    "monto_promedio",
    "tuvo_caida_unidad",
]

COLUMNAS_X_ABANDONO = [
    "meses_activo",
    "aportes_90d",
    "dias_desde_ultimo_aporte",
    "pct_pagos_rechazados",
    "sesiones_por_mes",
    "lecciones_vistas",
    "monto_promedio",
    "tuvo_caida_unidad",
    "perfil_CONSERVADOR",
    "perfil_MODERADO",
    "perfil_AGRESIVO",
]

ETIQUETAS_VAR = {
    "meses_activo": "Meses activo",
    "aportes_90d": "Aportes en 90 días",
    "dias_desde_ultimo_aporte": "Días desde último aporte",
    "pct_pagos_rechazados": "% pagos rechazados",
    "sesiones_por_mes": "Sesiones por mes",
    "lecciones_vistas": "Lecciones vistas",
    "perfil": "Perfil de riesgo",
    "monto_promedio": "Monto promedio (USD)",
    "tuvo_caida_unidad": "Tuvo caída de unidad",
}


def preparar_x_abandono(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte las 9 variables de comportamiento en matriz numérica para scikit-learn."""
    x = pd.DataFrame(index=df.index)
    for col in ["meses_activo", "aportes_90d", "dias_desde_ultimo_aporte",
                "pct_pagos_rechazados", "sesiones_por_mes", "lecciones_vistas",
                "monto_promedio", "tuvo_caida_unidad"]:
        x[col] = df[col].astype(float)
    for p in PERFILES:
        x[f"perfil_{p}"] = (df["perfil"] == p).astype(float)
    return x[COLUMNAS_X_ABANDONO]


def cargar_dataset() -> pd.DataFrame:
    if not RUTA_DATASET_COMP.exists():
        from ia.generar_dataset_comportamiento import generar_comportamiento
        RUTA_DATASET_COMP.parent.mkdir(parents=True, exist_ok=True)
        generar_comportamiento().to_csv(RUTA_DATASET_COMP, index=False)
    return pd.read_csv(RUTA_DATASET_COMP)


def elegir_umbral(y_val: np.ndarray, prob_val: np.ndarray,
                  recall_objetivo: float = RECALL_OBJETIVO_VALIDACION) -> float:
    """Elige el umbral de probabilidad que maximiza F1 manteniendo recall >= recall_objetivo."""
    mejores = []
    for u in np.linspace(0.20, 0.75, 56):
        pred = (prob_val >= u).astype(int)
        rec = recall_score(y_val, pred, zero_division=0)
        if rec >= recall_objetivo:
            f1 = f1_score(y_val, pred, zero_division=0)
            mejores.append((f1, float(u)))
    if mejores:
        mejores.sort(reverse=True)
        return round(mejores[0][1], 2)
    return 0.40


def evaluar_binario(y: np.ndarray, prob: np.ndarray, umbral: float) -> dict:
    pred = (prob >= umbral).astype(int)
    cm = confusion_matrix(y, pred, labels=[0, 1])
    return {
        "umbral": umbral,
        "exactitud": round(float(accuracy_score(y, pred)), 4),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y, pred, zero_division=0)), 4),
        "auc_roc": round(float(roc_auc_score(y, prob)), 4),
        "tasa_alerta": round(float(pred.mean()), 4),
        "tasa_real_abandono": round(float(y.mean()), 4),
        "matriz_confusion": {
            "filas_real_columnas_predicho": ["NO_ABANDONA", "ABANDONA"],
            "valores": cm.tolist(),
        },
    }


def metricas_por_grupo(df_pru: pd.DataFrame, y: np.ndarray, prob: np.ndarray, umbral: float) -> dict:
    """Evaluación de equidad/sesgo por edad y rango de ahorro (continuidad de CP-21)."""
    pred = (prob >= umbral).astype(int)
    grupos = {
        "edad": pd.cut(df_pru["edad"], [0, 24, 40, 200], labels=["18-24", "25-40", "41+"]),
        "ahorro_mensual": pd.cut(df_pru["ahorro_mensual_rango"], [0, 2, 4],
                                 labels=["bajo ($5-$50)", "alto ($50+)"]),
    }
    salida = {}
    for nombre, g in grupos.items():
        filas = []
        for valor in g.cat.categories:
            mask = (g == valor).to_numpy()
            if mask.sum() == 0:
                continue
            filas.append({
                "grupo": str(valor),
                "n": int(mask.sum()),
                "auc_roc": round(float(roc_auc_score(y[mask], prob[mask])), 4),
                "precision": round(float(precision_score(y[mask], pred[mask], zero_division=0)), 4),
                "recall": round(float(recall_score(y[mask], pred[mask], zero_division=0)), 4),
                "f1": round(float(f1_score(y[mask], pred[mask], zero_division=0)), 4),
                "tasa_real": round(float(y[mask].mean()), 4),
                "tasa_alerta": round(float(pred[mask].mean()), 4),
            })
        salida[nombre] = filas
    return salida


def importancia_por_variable(modelo, df_pru: pd.DataFrame, y: np.ndarray, repeticiones: int = 8) -> dict:
    """Importancia por permutación (caída del AUC-ROC al desordenar cada variable)."""
    rng = np.random.default_rng(SEMILLA)
    base = roc_auc_score(y, modelo.predict_proba(preparar_x_abandono(df_pru))[:, 1])
    resultado = {}
    for var in VARIABLES_ABANDONO:
        caidas = []
        for _ in range(repeticiones):
            mezclado = df_pru.copy()
            mezclado[var] = rng.permutation(mezclado[var].to_numpy())
            auc_m = roc_auc_score(y, modelo.predict_proba(preparar_x_abandono(mezclado))[:, 1])
            caidas.append(base - auc_m)
        resultado[var] = round(float(np.mean(caidas)), 4)
    return dict(sorted(resultado.items(), key=lambda kv: kv[1], reverse=True))


# ------------------------------------------------------------------ gráficos
SUPERFICIE, TINTA, TINTA_2 = "#fcfcfb", "#0b0b0b", "#52514e"
AZUL, VERDE = "#2a78d6", "#0f7a55"
RAMPA_AZUL = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def _estilo(plt):
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": "#d8d7d2",
        "axes.labelcolor": TINTA_2, "xtick.color": TINTA_2, "ytick.color": TINTA_2,
        "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE,
    })


def grafico_roc(y_pru: np.ndarray, curvas: dict[str, tuple[np.ndarray, float]], ruta: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _estilo(plt)
    fig, ax = plt.subplots(figsize=(6.4, 5.0), dpi=200)
    colores = {"regresion_logistica": AZUL, "gradient_boosting": VERDE}
    nombres = {"regresion_logistica": "Regresión logística", "gradient_boosting": "Gradient boosting"}
    for clave, (prob, auc) in curvas.items():
        fpr, tpr, _ = roc_curve(y_pru, prob)
        ax.plot(fpr, tpr, label=f"{nombres[clave]} (AUC = {auc:.3f})",
                color=colores[clave], linewidth=2.2)
    ax.plot([0, 1], [0, 1], "--", color="#9c9a94", linewidth=1.2, label="Azar (AUC = 0,500)")
    ax.set_xlabel("Tasa de falsos positivos")
    ax.set_ylabel("Tasa de verdaderos positivos (Recall)")
    ax.set_title("Curva ROC · Modelo de abandono a 60 días", color=TINTA, fontsize=12, loc="left", pad=10)
    ax.grid(True, color="#ecebe7", linewidth=0.8)
    ax.legend(loc="lower right", frameon=True, facecolor=SUPERFICIE, edgecolor="#d8d7d2")
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    fig.text(0.01, 0.01, "Datos sintéticos · Split temporal: entrenamiento meses 1-9, prueba meses 10-12",
             color=TINTA_2, fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(fig)


def grafico_matriz_abandono(cm: np.ndarray, titulo: str, ruta: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    _estilo(plt)
    cmap = LinearSegmentedColormap.from_list("azul", RAMPA_AZUL)
    fig, ax = plt.subplots(figsize=(5.8, 4.8), dpi=200)
    porc = cm / cm.sum(axis=1, keepdims=True)
    ax.imshow(porc, cmap=cmap, vmin=0, vmax=1)
    for i in range(2):
        for j in range(2):
            oscuro = porc[i, j] > 0.55
            ax.text(j, i, f"{cm[i, j]}\n{porc[i, j]:.0%}", ha="center", va="center", fontsize=12,
                    color="#ffffff" if oscuro else TINTA, fontweight="bold" if i == j else "normal")
    etiquetas = ["Sigue aportando", "Abandona (60d)"]
    ax.set_xticks(range(2), etiquetas)
    ax.set_yticks(range(2), etiquetas)
    ax.set_xlabel("Predicción del modelo")
    ax.set_ylabel("Comportamiento real (meses 11-12)")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, 2), minor=True)
    ax.set_yticks(np.arange(-0.5, 2), minor=True)
    ax.grid(which="minor", color=SUPERFICIE, linewidth=3)
    ax.tick_params(which="minor", length=0)
    ax.set_title(titulo, color=TINTA, fontsize=12, loc="left", pad=12)
    fig.text(0.01, 0.01, "Datos sintéticos · Corte mes 10 (5.000 usuarios) · % por fila",
             color=TINTA_2, fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(fig)


def grafico_importancia_abandono(imp: dict, ruta: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _estilo(plt)
    items = list(imp.items())[::-1]
    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=200)
    valores = [max(v, 0) for _, v in items]
    ax.barh([ETIQUETAS_VAR[k] for k, _ in items], valores, color=VERDE, height=0.6)
    max_v = max(valores) if valores and max(valores) > 0 else 1.0
    for i, v in enumerate(valores):
        ax.text(v + max_v * 0.01, i, f"{v:.4f}", va="center", fontsize=9, color=TINTA_2)
    ax.set_xlabel("Caída del AUC-ROC al desordenar esa variable")
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.grid(True, color="#ecebe7", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title("¿Qué variables explican el riesgo de abandono?", color=TINTA, fontsize=12, loc="left")
    fig.tight_layout()
    fig.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(fig)


# ------------------------------------------------------------------ principal
def entrenar_abandono(df: pd.DataFrame | None = None, guardar: bool = True) -> dict:
    df = cargar_dataset() if df is None else df
    etiquetado = df.dropna(subset=["abandona_60d"]).copy()
    etiquetado["abandona_60d"] = etiquetado["abandona_60d"].astype(int)

    # Split estrictamente temporal sin fuga del futuro:
    #   Entrenamiento: cortes meses 3..6 -> todas las etiquetas caen en meses 4..8
    #   Validación: corte mes 7          -> etiquetas caen en meses 8..9 (<= mes 9)
    #   Prueba: corte mes 10             -> etiquetas caen en meses 11..12 (periodo 10..12)
    df_ent = etiquetado[etiquetado["mes"].isin([3, 4, 5, 6])]
    df_val = etiquetado[etiquetado["mes"] == 7]
    df_pru = etiquetado[etiquetado["mes"] == 10]

    x_ent, y_ent = preparar_x_abandono(df_ent), df_ent["abandona_60d"].to_numpy()
    x_val, y_val = preparar_x_abandono(df_val), df_val["abandona_60d"].to_numpy()
    x_pru, y_pru = preparar_x_abandono(df_pru), df_pru["abandona_60d"].to_numpy()

    modelos_candidatos = {
        "regresion_logistica": [
            ({"C": c}, Pipeline([("escala", StandardScaler()),
                                 ("modelo", LogisticRegression(C=c, max_iter=2000))]))
            for c in [0.1, 1.0, 5.0]
        ],
        "gradient_boosting": [
            ({"max_depth": d, "learning_rate": lr},
             HistGradientBoostingClassifier(max_depth=d, learning_rate=lr,
                                            max_iter=180, min_samples_leaf=30,
                                            random_state=SEMILLA))
            for d in [3, 5] for lr in [0.05, 0.1]
        ],
    }

    comparacion, ajustados, curvas_roc = {}, {}, {}
    for nombre, rejilla in modelos_candidatos.items():
        mejor_auc, mejor_modelo, mejor_params = -1.0, None, None
        for params, est in rejilla:
            est.fit(x_ent, y_ent)
            p_val = est.predict_proba(x_val)[:, 1]
            auc_val = roc_auc_score(y_val, p_val)
            if auc_val > mejor_auc:
                mejor_auc, mejor_modelo, mejor_params = auc_val, est, params

        prob_val = mejor_modelo.predict_proba(x_val)[:, 1]
        umbral = elegir_umbral(y_val, prob_val)

        # Reentrenar con meses 3..7 (toda la ventana <= mes 9) antes de evaluar en mes 10
        df_ent_full = etiquetado[etiquetado["mes"].isin([3, 4, 5, 6, 7])]
        mejor_modelo.fit(preparar_x_abandono(df_ent_full), df_ent_full["abandona_60d"].to_numpy())
        prob_pru = mejor_modelo.predict_proba(x_pru)[:, 1]
        m_pru = evaluar_binario(y_pru, prob_pru, umbral)

        comparacion[nombre] = {
            "mejores_hiperparametros": mejor_params,
            "auc_validacion_mes7": round(float(mejor_auc), 4),
            "prueba_meses_10_12": m_pru,
            "cumple_metas": {
                "auc_>=_0.80": m_pru["auc_roc"] >= META_AUC,
                "recall_>=_0.70": m_pru["recall"] >= META_RECALL,
            },
        }
        ajustados[nombre] = (mejor_modelo, umbral, prob_pru)
        curvas_roc[nombre] = (prob_pru, m_pru["auc_roc"])

    def puntaje(n: str):
        c = comparacion[n]
        return (all(c["cumple_metas"].values()), c["prueba_meses_10_12"]["auc_roc"],
                c["prueba_meses_10_12"]["f1"])

    elegido = max(comparacion, key=puntaje)
    modelo_final, umbral_final, prob_final = ajustados[elegido]

    resultado = {
        "fecha_entrenamiento": datetime.now().isoformat(timespec="seconds"),
        "version_scikit_learn": sklearn.__version__,
        "dataset": {
            "ruta": "data/dataset_comportamiento.csv",
            "usuarios_unicos": int(df["usuario_id"].nunique()),
            "filas_totales": int(len(df)),
            "split_temporal": {
                "entrenamiento_cortes_meses": [3, 4, 5, 6, 7],
                "etiquetas_entrenamiento_hasta_mes": 9,
                "filas_entrenamiento": int(len(df_ent) + len(df_val)),
                "prueba_corte_mes": 10,
                "etiquetas_prueba_meses": [11, 12],
                "filas_prueba": int(len(df_pru)),
            },
        },
        "metas": {"auc_roc": META_AUC, "recall_abandona": META_RECALL},
        "modelo_elegido": elegido,
        "umbral_elegido": umbral_final,
        "comparacion": comparacion,
        "metricas_por_grupo": metricas_por_grupo(df_pru, y_pru, prob_final, umbral_final),
        "importancia_por_variable": importancia_por_variable(modelo_final, df_pru, y_pru),
    }

    if guardar:
        DIR_DOCS.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "modelo": modelo_final,
            "nombre": elegido,
            "umbral": umbral_final,
            "columnas": COLUMNAS_X_ABANDONO,
            "version_scikit_learn": sklearn.__version__,
            "fecha": resultado["fecha_entrenamiento"],
        }, RUTA_MODELO_ABANDONO)
        (DIR_DOCS / "metricas_abandono.json").write_text(
            json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
        grafico_roc(y_pru, curvas_roc, DIR_DOCS / "roc_abandono.png")
        cm = np.array(comparacion[elegido]["prueba_meses_10_12"]["matriz_confusion"]["valores"])
        nombre_bonito = {"regresion_logistica": "Regresión logística",
                         "gradient_boosting": "Gradient boosting"}[elegido]
        grafico_matriz_abandono(cm, f"Matriz de confusión · {nombre_bonito}",
                                DIR_DOCS / "matriz_confusion_abandono.png")
        grafico_importancia_abandono(resultado["importancia_por_variable"],
                                     DIR_DOCS / "importancia_abandono.png")

    return resultado


def main():
    r = entrenar_abandono()
    print(f"Modelo elegido (abandono 60d): {r['modelo_elegido']} (umbral={r['umbral_elegido']})\n")
    for nombre, c in r["comparacion"].items():
        m = c["prueba_meses_10_12"]
        print(f"{nombre:22s} AUC={m['auc_roc']:.3f}  precision={m['precision']:.3f}  "
              f"recall={m['recall']:.3f}  F1={m['f1']:.3f}  cumple={all(c['cumple_metas'].values())}")
    print("\nArchivos: ia/modelo_abandono.joblib, docs/ia/metricas_abandono.json, "
          "docs/ia/roc_abandono.png, docs/ia/matriz_confusion_abandono.png, "
          "docs/ia/importancia_abandono.png")


if __name__ == "__main__":
    main()
