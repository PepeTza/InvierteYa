"""Entrena y evalúa el modelo de perfil de riesgo v2 (Sesión 3 · cuestionario en 2 tandas).

    python ia/entrenar.py

Pasos:
  1. Lee data/dataset_sintetico.csv (si no existe o no tiene columnas S3, lo regenera).
  2. Divide 80% entrenamiento / 20% prueba (estratificado, semilla 42).
  3. Compara árbol de decisión y regresión logística multinomial con validación cruzada 5-fold.
  4. Evalúa ambos en el 20% de prueba, con y sin reglas de seguridad, incluyendo subgrupos de
     edad, rango de ahorro, usuarios que usaron "Prefiero no decirlo" y solo Tanda 1.
  5. Guarda ia/modelo_perfil.joblib, docs/ia/metricas.json, matriz_confusion.png e
     importancia_variables.png.
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
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from ia.comun import (CLASES, COLUMNAS_MODELO, DIR_DOCS, RUTA_DATASET, RUTA_MODELO,  # noqa: E402
                      UMBRAL_REVISION, VARIABLES, preparar_x)

SEMILLA = 42
META_EXACTITUD, META_F1 = 0.85, 0.80


def cargar_dataset() -> pd.DataFrame:
    regenerar = not RUTA_DATASET.exists()
    if not regenerar:
        df = pd.read_csv(RUTA_DATASET)
        if not set(VARIABLES).issubset(df.columns):
            regenerar = True
        else:
            return df
    from ia.generar_dataset import generar
    RUTA_DATASET.parent.mkdir(parents=True, exist_ok=True)
    df = generar()
    df.to_csv(RUTA_DATASET, index=False)
    return df


def candidatos() -> dict[str, GridSearchCV]:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA)
    arbol = GridSearchCV(
        DecisionTreeClassifier(random_state=SEMILLA),
        {"max_depth": [4, 6, 8, 10, 12], "min_samples_leaf": [5, 10, 20],
         "class_weight": [None, "balanced"]},
        scoring="f1_macro", cv=cv)
    logistica = GridSearchCV(
        Pipeline([("escala", StandardScaler()),
                  ("modelo", LogisticRegression(max_iter=5000))]),
        {"modelo__C": [0.1, 1.0, 10.0], "modelo__class_weight": [None, "balanced"]},
        scoring="f1_macro", cv=cv)
    return {"arbol_decision": arbol, "regresion_logistica": logistica}


def aplicar_reglas(pred: np.ndarray, df: pd.DataFrame) -> np.ndarray:
    """Regla de seguridad (no negociable): sin fondo de emergencia ('no_podria' o faltante) nunca Agresivo."""
    pred = pred.copy()
    sin_fondo = ~df["fondo_emergencia"].astype(bool).to_numpy()
    pred[(pred == "AGRESIVO") & sin_fondo] = "MODERADO"
    return pred


def metricas(y: np.ndarray, pred: np.ndarray, proba: np.ndarray | None = None) -> dict:
    cm = confusion_matrix(y, pred, labels=CLASES)
    m = {
        "exactitud": round(accuracy_score(y, pred), 4),
        "f1_macro": round(f1_score(y, pred, average="macro"), 4),
        "f1_por_clase": dict(zip(CLASES, np.round(f1_score(y, pred, labels=CLASES, average=None), 4).tolist())),
        "precision_por_clase": dict(zip(CLASES, np.round(precision_score(y, pred, labels=CLASES, average=None, zero_division=0), 4).tolist())),
        "recall_por_clase": dict(zip(CLASES, np.round(recall_score(y, pred, labels=CLASES, average=None, zero_division=0), 4).tolist())),
        "matriz_confusion": {"filas_real_columnas_predicho": CLASES, "valores": cm.tolist()},
        "conservador_como_agresivo": int(cm[0, 2]),
        "agresivo_como_conservador": int(cm[2, 0]),
    }
    if proba is not None:
        orden = sorted(CLASES)
        p = proba[:, [CLASES.index(c) for c in orden]]
        m["auc_ovr_macro"] = round(roc_auc_score(y, p, multi_class="ovr", labels=orden), 4)
        m["pct_revision_humana"] = round(float((proba.max(axis=1) < UMBRAL_REVISION).mean()), 4)
    return m


def cumple(m: dict) -> dict:
    return {"exactitud_>=_85%": m["exactitud"] >= META_EXACTITUD,
            "f1_por_clase_>=_0.80": all(v >= META_F1 for v in m["f1_por_clase"].values()),
            "cero_conservador_como_agresivo": m["conservador_como_agresivo"] == 0}


def proba_ordenada(modelo, x: pd.DataFrame) -> np.ndarray:
    orden = [list(modelo.classes_).index(c) for c in CLASES]
    return modelo.predict_proba(x)[:, orden]


def metricas_por_grupo(df: pd.DataFrame, y, pred) -> dict:
    """Mitigación de sesgo: revisar métricas por edad, ahorro mensual y uso de 'Prefiero no decirlo'."""
    ahorro_cat = pd.Series("prefiero no decir", index=df.index, dtype="object")
    mask_bajo = df["ahorro_mensual_rango"].isin([1, 2])
    mask_alto = df["ahorro_mensual_rango"].isin([3, 4])
    ahorro_cat.loc[mask_bajo] = "bajo ($5-$50)"
    ahorro_cat.loc[mask_alto] = "alto ($50+)"

    grupos = {
        "edad": pd.cut(df["edad"], [0, 24, 40, 200], labels=["18-24", "25-40", "41+"]),
        "ahorro_mensual": pd.Categorical(ahorro_cat, categories=["bajo ($5-$50)", "alto ($50+)", "prefiero no decir"]),
        "tanda": pd.Categorical(df["tanda_completada"].map({1: "solo tanda 1", 2: "tanda 1 y 2"}),
                                categories=["solo tanda 1", "tanda 1 y 2"]),
    }
    salida = {}
    for nombre, g in grupos.items():
        filas = []
        categorias = g.cat.categories if hasattr(g, "cat") else g.categories
        for valor in categorias:
            mask = np.asarray(g == valor)
            if mask.sum() == 0:
                continue
            filas.append({
                "grupo": str(valor), "n": int(mask.sum()),
                "exactitud": round(accuracy_score(y[mask], pred[mask]), 4),
                "f1_macro": round(f1_score(y[mask], pred[mask], average="macro", labels=CLASES, zero_division=0), 4),
                "pct_agresivo_real": round(float((y[mask] == "AGRESIVO").mean()), 4),
                "pct_agresivo_predicho": round(float((pred[mask] == "AGRESIVO").mean()), 4),
            })
        salida[nombre] = filas
    return salida


VARS_IMPORTANCIA = [
    "edad", "ahorro_mensual_rango", "horizonte_anios", "objetivo",
    "reaccion_caida_20", "experiencia_tipo", "emergencia_200",
    "dependientes", "conocimiento",
]


def importancia_por_variable(modelo, df: pd.DataFrame, y, repeticiones: int = 10) -> dict:
    """Importancia por permutación agrupada por pregunta del cuestionario S3."""
    rng = np.random.default_rng(SEMILLA)
    base = f1_score(y, modelo.predict(preparar_x(df)), average="macro")
    resultado = {}
    for var in VARS_IMPORTANCIA:
        caidas = []
        for _ in range(repeticiones):
            mezclado = df.copy()
            perm = rng.permutation(len(df))
            if var == "ahorro_mensual_rango":
                for c in ["ahorro_mensual_rango", "ingreso_rango", "pct_invertible", "ahorro_omitido"]:
                    mezclado[c] = mezclado[c].to_numpy()[perm]
            elif var == "emergencia_200":
                for c in ["emergencia_200", "fondo_emergencia", "emergencia_omitida"]:
                    mezclado[c] = mezclado[c].to_numpy()[perm]
            else:
                mezclado[var] = mezclado[var].to_numpy()[perm]
            caidas.append(base - f1_score(y, modelo.predict(preparar_x(mezclado)), average="macro"))
        resultado[var] = round(float(np.mean(caidas)), 4)
    return dict(sorted(resultado.items(), key=lambda kv: kv[1], reverse=True))


# ------------------------------------------------------------------ gráficos
SUPERFICIE, TINTA, TINTA_2 = "#fcfcfb", "#0b0b0b", "#52514e"
AZUL = "#2a78d6"
RAMPA_AZUL = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
NOMBRES = {"CONSERVADOR": "Conservador", "MODERADO": "Moderado", "AGRESIVO": "Agresivo"}
ETIQUETAS_VAR = {
    "edad": "Edad (desde KYC)",
    "ahorro_mensual_rango": "Monto mensual apartable",
    "horizonte_anios": "Horizonte (¿para qué es?)",
    "objetivo": "Objetivo (3 frases)",
    "reaccion_caida_20": "Reacción si $100 bajan a $80",
    "experiencia_tipo": "Experiencia previa",
    "emergencia_200": "Imprevisto de $200",
    "dependientes": "Hogar (Tanda 2)",
    "conocimiento": "Quiz amistoso (Tanda 2)",
}


def _estilo(plt):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": "#d8d7d2",
                         "axes.labelcolor": TINTA_2, "xtick.color": TINTA_2, "ytick.color": TINTA_2,
                         "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE})


def grafico_matriz(cm: np.ndarray, titulo: str, ruta: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    _estilo(plt)
    cmap = LinearSegmentedColormap.from_list("azul", RAMPA_AZUL)
    fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=200)
    porc = cm / cm.sum(axis=1, keepdims=True)
    ax.imshow(porc, cmap=cmap, vmin=0, vmax=1)
    for i in range(3):
        for j in range(3):
            oscuro = porc[i, j] > 0.55
            ax.text(j, i, f"{cm[i, j]}\n{porc[i, j]:.0%}", ha="center", va="center", fontsize=12,
                    color="#ffffff" if oscuro else TINTA, fontweight="bold" if i == j else "normal")
    nombres = [NOMBRES[c] for c in CLASES]
    ax.set_xticks(range(3), nombres)
    ax.set_yticks(range(3), nombres)
    ax.set_xlabel("Perfil predicho por el modelo")
    ax.set_ylabel("Perfil real (etiqueta)")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, 3), minor=True)
    ax.set_yticks(np.arange(-0.5, 3), minor=True)
    ax.grid(which="minor", color=SUPERFICIE, linewidth=3)
    ax.tick_params(which="minor", length=0)
    ax.set_title(titulo, color=TINTA, fontsize=12, loc="left", pad=12)
    fig.text(0.01, 0.01, "Datos sintéticos S3 (2 tandas + faltantes) · 20% prueba (1.000 usuarios)",
             color=TINTA_2, fontsize=8)
    fig.tight_layout()
    fig.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(fig)


def grafico_importancia(imp: dict, ruta: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _estilo(plt)
    items = list(imp.items())[::-1]
    fig, ax = plt.subplots(figsize=(7.4, 4.6), dpi=200)
    valores = [max(v, 0) for _, v in items]
    ax.barh([ETIQUETAS_VAR[k] for k, _ in items], valores, color=AZUL, height=0.6)
    max_v = max(valores) if valores and max(valores) > 0 else 1.0
    for i, v in enumerate(valores):
        ax.text(v + max_v * 0.01, i, f"{v:.3f}", va="center", fontsize=9, color=TINTA_2)
    ax.set_xlabel("Pérdida de F1 macro al desordenar esa pregunta")
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.xaxis.grid(True, color="#ecebe7", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title("¿Qué respuestas pesan más en el perfil? (Cuestionario S3)", color=TINTA, fontsize=12, loc="left")
    fig.tight_layout()
    fig.savefig(ruta, facecolor=SUPERFICIE)
    plt.close(fig)


# ------------------------------------------------------------------ principal
def entrenar(df: pd.DataFrame | None = None, guardar: bool = True,
             con_estabilidad: bool = True) -> dict:
    df = cargar_dataset() if df is None else df
    y = df["perfil"].to_numpy()
    df_ent, df_pru, y_ent, y_pru = train_test_split(df, y, test_size=0.2, stratify=y,
                                                    random_state=SEMILLA)
    x_ent, x_pru = preparar_x(df_ent), preparar_x(df_pru)

    comparacion, ajustados = {}, {}
    for nombre, busqueda in candidatos().items():
        busqueda.fit(x_ent, y_ent)
        modelo = busqueda.best_estimator_
        proba = proba_ordenada(modelo, x_pru)
        crudo = modelo.predict(x_pru)
        final = aplicar_reglas(crudo, df_pru)
        m_final = metricas(y_pru, final, proba)
        comparacion[nombre] = {
            "mejores_hiperparametros": busqueda.best_params_,
            "f1_macro_validacion_cruzada": round(busqueda.best_score_, 4),
            "prueba_sin_reglas": metricas(y_pru, crudo, proba),
            "prueba_con_reglas_de_seguridad": m_final,
            "cumple_metas": cumple(m_final),
        }
        ajustados[nombre] = (modelo, final)

    def puntaje(n):
        c = comparacion[n]
        return (all(c["cumple_metas"].values()), c["prueba_con_reglas_de_seguridad"]["f1_macro"])
    elegido = max(comparacion, key=puntaje)
    modelo, pred_final = ajustados[elegido]

    resultado = {
        "version_modelo": "perfil_v2_s3_2tandas",
        "fecha_entrenamiento": datetime.now().isoformat(timespec="seconds"),
        "version_scikit_learn": sklearn.__version__,
        "dataset": {
            "ruta": "data/dataset_sintetico.csv",
            "filas": len(df),
            "distribucion_perfiles": df["perfil"].value_counts().to_dict(),
            "entrenamiento": len(df_ent),
            "prueba": len(df_pru),
            "semilla": SEMILLA,
            "pct_prefiero_no_decir_ahorro": round(float(df["ahorro_omitido"].mean()), 4),
            "pct_prefiero_no_decir_emergencia": round(float(df["emergencia_omitida"].mean()), 4),
            "pct_solo_tanda_1": round(float((df["tanda_completada"] == 1).mean()), 4),
        },
        "metas": {"exactitud": META_EXACTITUD, "f1_por_clase": META_F1, "conservador_como_agresivo": 0,
                  "umbral_revision_humana": UMBRAL_REVISION},
        "modelo_elegido": elegido,
        "comparacion": comparacion,
        "metricas_por_grupo": metricas_por_grupo(df_pru, y_pru, pred_final),
        "importancia_por_variable": importancia_por_variable(modelo, df_pru, y_pru),
    }
    if con_estabilidad:
        resultado["estabilidad_otras_semillas"] = estabilidad(elegido)

    if guardar:
        DIR_DOCS.mkdir(parents=True, exist_ok=True)
        joblib.dump({"modelo": modelo, "nombre": elegido, "columnas": COLUMNAS_MODELO,
                     "clases": CLASES, "version_scikit_learn": sklearn.__version__,
                     "version_modelo": "perfil_v2_s3_2tandas",
                     "fecha": resultado["fecha_entrenamiento"]}, RUTA_MODELO)
        (DIR_DOCS / "metricas.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False),
                                                encoding="utf-8")
        cm = np.array(comparacion[elegido]["prueba_con_reglas_de_seguridad"]["matriz_confusion"]["valores"])
        nombre_bonito = {"arbol_decision": "Árbol de decisión",
                         "regresion_logistica": "Regresión logística"}[elegido]
        grafico_matriz(cm, f"Matriz de confusión · {nombre_bonito} (S3)", DIR_DOCS / "matriz_confusion.png")
        grafico_importancia(resultado["importancia_por_variable"], DIR_DOCS / "importancia_variables.png")
        if elegido == "arbol_decision":
            (DIR_DOCS / "reglas_arbol.txt").write_text(
                export_text(modelo, feature_names=COLUMNAS_MODELO, max_depth=4), encoding="utf-8")
    return resultado


def estabilidad(nombre_modelo: str, semillas=(1, 7, 99, 123, 2024)) -> dict:
    """Repite TODO (dataset + entrenamiento) con otras semillas para verificar estabilidad."""
    global SEMILLA
    from ia.generar_dataset import generar
    original, filas = SEMILLA, []
    try:
        for s in semillas:
            SEMILLA = s
            r = entrenar(generar(semilla=s), guardar=False, con_estabilidad=False)
            m = r["comparacion"][nombre_modelo]["prueba_con_reglas_de_seguridad"]
            filas.append({"semilla": s, "exactitud": m["exactitud"],
                          "f1_minimo_por_clase": min(m["f1_por_clase"].values()),
                          "conservador_como_agresivo": m["conservador_como_agresivo"]})
    finally:
        SEMILLA = original
    ex = [f["exactitud"] for f in filas]
    f1 = [f["f1_minimo_por_clase"] for f in filas]
    return {"modelo": nombre_modelo, "corridas": filas,
            "exactitud_promedio": round(float(np.mean(ex)), 4), "exactitud_min": min(ex),
            "f1_minimo_promedio": round(float(np.mean(f1)), 4), "f1_minimo_peor_caso": min(f1),
            "conservador_como_agresivo_total": sum(f["conservador_como_agresivo"] for f in filas)}


def main():
    r = entrenar()
    print(f"Modelo elegido (perfil S3): {r['modelo_elegido']}\n")
    for nombre, c in r["comparacion"].items():
        m = c["prueba_con_reglas_de_seguridad"]
        print(f"{nombre:22s} exactitud={m['exactitud']:.3f}  F1={m['f1_por_clase']}  "
              f"C->A={m['conservador_como_agresivo']}  AUC={m['auc_ovr_macro']}  "
              f"revisión humana={m['pct_revision_humana']:.1%}  cumple={all(c['cumple_metas'].values())}")
    e = r["estabilidad_otras_semillas"]
    print(f"\nEstabilidad ({len(e['corridas'])} semillas): exactitud media {e['exactitud_promedio']:.3f}, "
          f"peor F1 por clase {e['f1_minimo_peor_caso']:.3f}, C->A total {e['conservador_como_agresivo_total']}")


if __name__ == "__main__":
    main()
