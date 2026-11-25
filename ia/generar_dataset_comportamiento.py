"""Genera el dataset SINTÉTICO de comportamiento (5.000 usuarios × 12 meses) y la serie diaria de flujos.

    python ia/generar_dataset_comportamiento.py
        -> data/dataset_comportamiento.csv  (eventos y variables al corte por usuario-mes)
        -> data/dataset_flujos_diarios.csv  (serie diaria de aportes y rescates por fideicomiso)

Cómo se construye (detalle en docs/ia/DATASET_COMPORTAMIENTO.md):
  1. Se simulan 5.000 usuarios sintéticos (syn_00001..syn_05000) durante 12 meses de operación.
  2. Cada mes ocurren eventos: aportes, rechazos de pago (códigos 51 y 05), sesiones en la app,
     lecciones vistas del tutor, rescates y eventuales caídas del valor de la unidad.
  3. El hábito de ahorro de cada usuario evoluciona con reglas + ruido: rechazos de pago,
     caídas del valor de la unidad y baja actividad elevan el riesgo de dejar de aportar;
     sesiones activas y lecciones vistas lo amortiguan.
  4. Para cada corte mensual t se calculan las 9 variables estrictamente con información <= t
     (sin fuga del futuro) y la etiqueta `abandona_60d` = 1 si el usuario no realiza aportes
     en los meses t+1 y t+2.

No contiene datos de personas reales ni tarjetas reales. Semilla fija (42): 100% reproducible.
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
RUTA_COMPORTAMIENTO = RAIZ / "data" / "dataset_comportamiento.csv"
RUTA_FLUJOS = RAIZ / "data" / "dataset_flujos_diarios.csv"

SEMILLA = 42
N_USUARIOS_DEFECTO = 5000
N_MESES = 12

FIDEICOMISOS_CATALOGO = [
    {"id": "liq_usd", "nombre": "Liquidez USD", "riesgo": 1, "volatilidad": 0.02, "peso_base": 0.18},
    {"id": "rf_usd", "nombre": "Renta Fija USD", "riesgo": 2, "volatilidad": 0.05, "peso_base": 0.30},
    {"id": "mix_bal", "nombre": "Mixto Balanceado", "riesgo": 3, "volatilidad": 0.12, "peso_base": 0.28},
    {"id": "acc_bvc", "nombre": "Acciones BVC", "riesgo": 4, "volatilidad": 0.22, "peso_base": 0.16},
    {"id": "crec_ves", "nombre": "Crecimiento Bolívares", "riesgo": 5, "volatilidad": 0.30, "peso_base": 0.08},
]

PERFIL_A_FIDEICOMISO = {
    "CONSERVADOR": (["liq_usd", "rf_usd"], [0.40, 0.60]),
    "MODERADO": (["rf_usd", "mix_bal", "acc_bvc"], [0.25, 0.60, 0.15]),
    "AGRESIVO": (["mix_bal", "acc_bvc", "crec_ves"], [0.15, 0.55, 0.30]),
}

RIESGO_POR_FIDEICOMISO = {f["id"]: f["riesgo"] for f in FIDEICOMISOS_CATALOGO}


def _sigmoide(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -20.0, 20.0)))


def generar_comportamiento(n_usuarios: int = N_USUARIOS_DEFECTO,
                           semilla: int = SEMILLA) -> pd.DataFrame:
    """Simula n_usuarios × 12 meses de comportamiento y calcula variables al corte sin fuga futura."""
    rng = np.random.default_rng(semilla)

    # Atributos base sintéticos (sin PII)
    usuario_ids = np.array([f"syn_{i:05d}" for i in range(1, n_usuarios + 1)])
    grupo_edad = rng.choice(3, size=n_usuarios, p=[0.18, 0.62, 0.20])
    edad = np.where(grupo_edad == 0, rng.integers(18, 25, n_usuarios),
                    np.where(grupo_edad == 1, rng.integers(25, 41, n_usuarios),
                             rng.integers(41, 66, n_usuarios)))

    # Rango de ahorro mensual S3: 1 ($5-$20), 2 ($20-$50), 3 ($50-$100), 4 (>$100)
    ahorro_rango = rng.choice([1, 2, 3, 4], size=n_usuarios, p=[0.32, 0.36, 0.21, 0.11])
    monto_base_mapa = {1: 12.0, 2: 30.0, 3: 68.0, 4: 135.0}
    monto_base = np.array([monto_base_mapa[r] for r in ahorro_rango]) * rng.uniform(0.8, 1.25, n_usuarios)

    perfil = rng.choice(["CONSERVADOR", "MODERADO", "AGRESIVO"], size=n_usuarios, p=[0.28, 0.60, 0.12])
    fideicomiso = np.empty(n_usuarios, dtype=object)
    for p_nombre, (fids, probs) in PERFIL_A_FIDEICOMISO.items():
        mask = perfil == p_nombre
        fideicomiso[mask] = rng.choice(fids, size=int(mask.sum()), p=probs)
    riesgo_fid = np.array([RIESGO_POR_FIDEICOMISO[f] for f in fideicomiso], dtype=float)

    # Todos los usuarios ingresan en el mes 1 o 2 para tener historial completo hasta el mes 12.
    mes_ingreso = rng.choice([1, 2, 3], size=n_usuarios, p=[0.70, 0.20, 0.10])

    # Estado latente de compromiso (NO se exporta al CSV). Evoluciona mes a mes.
    compromiso = rng.normal(0.55, 0.95, n_usuarios) + 0.18 * (ahorro_rango - 2)
    # Sensibilidad individual a fricción de pagos / caídas de mercado
    sensibilidad = rng.uniform(0.6, 1.4, n_usuarios)

    # Matrices (n_usuarios, N_MESES)
    aportes_m = np.zeros((n_usuarios, N_MESES), dtype=int)
    monto_m = np.zeros((n_usuarios, N_MESES), dtype=float)
    rech51_m = np.zeros((n_usuarios, N_MESES), dtype=int)
    rech05_m = np.zeros((n_usuarios, N_MESES), dtype=int)
    sesiones_m = np.zeros((n_usuarios, N_MESES), dtype=int)
    lecciones_m = np.zeros((n_usuarios, N_MESES), dtype=int)
    rescates_m = np.zeros((n_usuarios, N_MESES), dtype=int)
    caida_m = np.zeros((n_usuarios, N_MESES), dtype=int)

    # Meses con correcciones de mercado simuladas (afectan más a fideicomisos de mayor riesgo)
    meses_volatiles = {4: 0.28, 8: 0.35, 10: 0.30, 11: 0.22}

    for m in range(N_MESES):
        mes_num = m + 1
        activo = mes_num >= mes_ingreso

        # Caída del valor de la unidad en este mes
        prob_caida = 0.03 * riesgo_fid + meses_volatiles.get(mes_num, 0.0) * (riesgo_fid / 5.0)
        caida = ((rng.random(n_usuarios) < np.clip(prob_caida, 0.0, 0.85)) & activo).astype(int)
        caida_m[:, m] = caida

        # Sesiones en la app dependen del compromiso actual
        lam_ses = np.clip(np.exp(0.65 + 0.72 * compromiso), 0.1, 14.0)
        sesiones = np.where(activo, rng.poisson(lam_ses), 0)
        sesiones_m[:, m] = sesiones

        # Lecciones vistas (más frecuentes en los primeros meses y con más sesiones)
        prob_lec = _sigmoide(-1.1 + 0.35 * np.minimum(sesiones, 6) - 0.12 * np.maximum(mes_num - mes_ingreso, 0))
        lecciones = np.where(activo, rng.binomial(2, np.clip(prob_lec, 0.01, 0.90)), 0)
        lecciones_m[:, m] = lecciones

        # Probabilidad de intentar aportar este mes
        prob_intento = _sigmoide(0.25 + 1.15 * compromiso + 0.18 * np.minimum(sesiones, 5) - 0.35 * caida)
        intenta = (rng.random(n_usuarios) < prob_intento) & activo
        n_intentos = np.where(intenta, 1 + (rng.random(n_usuarios) < _sigmoide(-1.6 + 0.55 * compromiso)), 0)

        # Rechazos de pago (51 fondos insuficientes, 05 no honrar): más probables si ahorro_rango es bajo
        p_r51 = np.clip(0.06 + 0.05 * (4 - ahorro_rango) / 3.0 + 0.06 * (compromiso < -0.3), 0.02, 0.35)
        p_r05 = np.full(n_usuarios, 0.03)
        r51 = np.where(n_intentos > 0, rng.binomial(n_intentos, p_r51), 0)
        restantes = np.maximum(n_intentos - r51, 0)
        r05 = np.where(restantes > 0, rng.binomial(restantes, p_r05), 0)
        aprobados = np.maximum(n_intentos - r51 - r05, 0)

        rech51_m[:, m] = r51
        rech05_m[:, m] = r05
        aportes_m[:, m] = aprobados
        ruido_monto = rng.uniform(0.75, 1.30, n_usuarios)
        monto_m[:, m] = np.round(aprobados * monto_base * ruido_monto, 2)

        # Rescates parciales/totales (más probables tras una caída de unidad o bajo compromiso)
        p_rescate = _sigmoide(-3.4 + 1.1 * caida - 0.75 * compromiso)
        rescates = np.where(activo & (mes_num > mes_ingreso), (rng.random(n_usuarios) < p_rescate).astype(int), 0)
        rescates_m[:, m] = rescates

        # Dinámica del compromiso para el mes siguiente (memoria + shock por fricción/caída + ruido)
        tuvo_rechazo = (r51 + r05) > 0
        sin_aporte = activo & (aprobados == 0)
        delta = (
            0.14 * (aprobados > 0)
            + 0.12 * (lecciones > 0)
            - 0.36 * sin_aporte
            - 0.45 * tuvo_rechazo * sensibilidad
            - 0.42 * caida * (perfil == "CONSERVADOR") * sensibilidad
            - 0.25 * caida * (perfil == "MODERADO") * sensibilidad
            - 0.65 * rescates
            + rng.normal(0.0, 0.48, n_usuarios)
        )
        # Reversión suave hacia la media para evitar divergencia
        compromiso = np.where(activo, 0.88 * compromiso + delta, compromiso)

    # Construcción de variables al corte t (estrictamente con historial <= t) y etiqueta a 60 días (t+1, t+2)
    registros = []
    ultimo_mes_aporte = np.zeros(n_usuarios, dtype=int)
    monto_acum = np.zeros(n_usuarios, dtype=float)
    aportes_acum = np.zeros(n_usuarios, dtype=int)
    lecciones_acum = np.zeros(n_usuarios, dtype=int)

    for m in range(N_MESES):
        mes_num = m + 1
        activo = mes_num >= mes_ingreso

        # Actualizar acumulados hasta el mes m (inclusive)
        hubo_aporte_m = aportes_m[:, m] > 0
        ultimo_mes_aporte = np.where(hubo_aporte_m, mes_num, ultimo_mes_aporte)
        monto_acum += monto_m[:, m]
        aportes_acum += aportes_m[:, m]
        lecciones_acum += lecciones_m[:, m]

        # Ventana 90 días: [max(0, m-2) .. m]
        ini = max(0, m - 2)
        n_vent = m - ini + 1
        aportes_90d = aportes_m[:, ini:m + 1].sum(axis=1)
        rechazos_90d = (rech51_m[:, ini:m + 1] + rech05_m[:, ini:m + 1]).sum(axis=1)
        intentos_90d = aportes_90d + rechazos_90d
        pct_rechazados = np.divide(rechazos_90d, intentos_90d,
                                   out=np.zeros(n_usuarios, dtype=float), where=intentos_90d > 0)
        sesiones_prom = sesiones_m[:, ini:m + 1].sum(axis=1) / n_vent
        tuvo_caida_90d = (caida_m[:, ini:m + 1].sum(axis=1) > 0).astype(int)

        meses_activo = np.maximum(mes_num - mes_ingreso + 1, 0)
        meses_sin_aporte = np.where(ultimo_mes_aporte > 0, mes_num - ultimo_mes_aporte, meses_activo)
        # Días desde el último aporte (simulado dentro del mes para resolución realista)
        jitter_dias = rng.integers(2, 26, n_usuarios)
        dias_ultimo = np.where(
            hubo_aporte_m,
            rng.integers(1, 22, n_usuarios),
            np.clip(meses_sin_aporte * 30 + jitter_dias, 25, 360),
        )
        monto_prom = np.divide(monto_acum, aportes_acum,
                               out=np.zeros(n_usuarios, dtype=float), where=aportes_acum > 0)

        # Etiqueta abandona_60d: 1 si 0 aportes en meses mes_num+1 y mes_num+2 (solo observable si m <= N_MESES - 3)
        if m <= N_MESES - 3:
            aportes_futuros_60d = aportes_m[:, m + 1] + aportes_m[:, m + 2]
            abandona = (aportes_futuros_60d == 0).astype(float)
        else:
            abandona = np.full(n_usuarios, np.nan)

        idx = np.where(activo)[0]
        registros.append(pd.DataFrame({
            "usuario_id": usuario_ids[idx],
            "mes": mes_num,
            "edad": edad[idx],
            "ahorro_mensual_rango": ahorro_rango[idx],
            "perfil": perfil[idx],
            "fideicomiso_principal": fideicomiso[idx],
            "meses_activo": meses_activo[idx],
            "aportes_90d": aportes_90d[idx],
            "dias_desde_ultimo_aporte": dias_ultimo[idx],
            "pct_pagos_rechazados": np.round(pct_rechazados[idx], 4),
            "sesiones_por_mes": np.round(sesiones_prom[idx], 2),
            "lecciones_vistas": lecciones_acum[idx],
            "monto_promedio": np.round(monto_prom[idx], 2),
            "tuvo_caida_unidad": tuvo_caida_90d[idx],
            "aportes_mes": aportes_m[idx, m],
            "rechazos_51_mes": rech51_m[idx, m],
            "rechazos_05_mes": rech05_m[idx, m],
            "rescates_mes": rescates_m[idx, m],
            "abandona_60d": abandona[idx],
        }))

    return pd.concat(registros, ignore_index=True)


def generar_flujos_diarios(n_dias: int = 365, semilla: int = SEMILLA) -> pd.DataFrame:
    """Genera 365 días de aportes y rescates sintéticos por fideicomiso para el pronóstico de flujos."""
    rng = np.random.default_rng(semilla + 100)
    fecha_inicio = date(2025, 11, 26)
    filas = []

    # Escala diaria coherente con una base en crecimiento hacia el SOM (~$8.500/día en volumen anual $3,09M)
    volumen_diario_base = 6200.0

    for d in range(n_dias):
        f = fecha_inicio + timedelta(days=d)
        dia_semana = f.weekday()  # 0=lun .. 6=dom
        es_quincena = int(f.day in (14, 15, 16, 29, 30, 31, 1))
        factor_tendencia = 1.0 + 0.45 * (d / n_dias)
        factor_semana = 1.12 if dia_semana < 5 else 0.72
        factor_quincena = 1.48 if es_quincena else 0.90

        for fid in FIDEICOMISOS_CATALOGO:
            esperado_aportes = volumen_diario_base * fid["peso_base"] * factor_tendencia * factor_semana * factor_quincena
            aportes = max(50.0, rng.normal(esperado_aportes, esperado_aportes * 0.09))
            # Rescates representan entre 12% y 24% de los aportes brutos (más en liquidez y mayor volatilidad)
            tasa_rescate = 0.22 if fid["riesgo"] == 1 else 0.13 + 0.02 * fid["riesgo"]
            rescates = max(0.0, rng.normal(aportes * tasa_rescate, aportes * 0.04))
            flujo_neto = aportes - rescates
            filas.append({
                "fecha": f.isoformat(),
                "dia_idx": d,
                "dia_semana": dia_semana,
                "es_quincena": es_quincena,
                "fideicomiso_id": fid["id"],
                "nombre_fideicomiso": fid["nombre"],
                "aportes_brutos_usd": round(aportes, 2),
                "rescates_usd": round(rescates, 2),
                "flujo_neto_usd": round(flujo_neto, 2),
            })

    return pd.DataFrame(filas)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--usuarios", type=int, default=N_USUARIOS_DEFECTO)
    args = ap.parse_args()

    df_comp = generar_comportamiento(n_usuarios=args.usuarios)
    RUTA_COMPORTAMIENTO.parent.mkdir(parents=True, exist_ok=True)
    df_comp.to_csv(RUTA_COMPORTAMIENTO, index=False)

    df_flujos = generar_flujos_diarios()
    df_flujos.to_csv(RUTA_FLUJOS, index=False)

    etiquetados = df_comp.dropna(subset=["abandona_60d"])
    tasa = etiquetados["abandona_60d"].mean()
    print(f"Comportamiento: {len(df_comp):,} filas ({df_comp['usuario_id'].nunique():,} usuarios × 12 meses) -> {RUTA_COMPORTAMIENTO}")
    print(f"Tasa global de abandono 60d (meses 1-10): {tasa:.1%}")
    print(f"Flujos diarios: {len(df_flujos):,} filas ({df_flujos['fideicomiso_id'].nunique()} fideicomisos × 365 días) -> {RUTA_FLUJOS}")


if __name__ == "__main__":
    main()
