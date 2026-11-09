# Guía paso a paso · Subir el baseline de IA a GitHub

Para cualquier integrante del Equipo D. Comandos para **Windows (PowerShell)**; en macOS o Linux son
iguales, salvo la activación del entorno virtual (`source .venv/bin/activate`).

**Tiempo estimado:** 10 a 15 minutos.

---

## Paso 0 · Lo que necesitas

- **Git** instalado. Compruébalo con `git --version`. Si no aparece una versión, instálalo desde
  https://git-scm.com/download/win (opciones por defecto).
- **Python 3.13**. Compruébalo con `py -3.13 --version`. Con 3.15 fallan las dependencias.
- Permiso de escritura en el repositorio de GitHub del equipo.
- El archivo **`cambios_baseline_ia.zip`**. Trae solo los archivos nuevos o modificados, con la misma
  estructura de carpetas del repositorio.

## Paso 1 · Abrir la carpeta del repositorio

Si ya tienes el repositorio en tu PC:

```powershell
cd C:\ruta\a\InvierteYa
git pull                      # trae lo último que subió el equipo
```

Si no lo tienes, clónalo primero (copia la URL desde el botón verde **Code** en GitHub):

```powershell
git clone https://github.com/USUARIO/InvierteYa.git
cd InvierteYa
```

## Paso 2 · (Opcional) Crear una rama

Si el equipo trabaja con ramas y pull requests:

```powershell
git checkout -b baseline-ia
```

Si todos suben directo a `main`, salta este paso.

## Paso 3 · Copiar los archivos nuevos encima del repositorio

Descomprime el zip **en la raíz del repositorio** (la carpeta que contiene `README.md`) y acepta
reemplazar los archivos:

```powershell
Expand-Archive -Path "$HOME\Downloads\cambios_baseline_ia.zip" -DestinationPath . -Force
```

También sirve hacerlo con el Explorador: clic derecho en el zip → **Extraer todo** → elegir la carpeta
del repositorio → reemplazar.

Lo que trae el zip:

| Tipo | Archivos |
|---|---|
| **Nuevos** | `ia/__init__.py`, `ia/comun.py`, `ia/generar_dataset.py`, `ia/entrenar.py`, `ia/predictor.py`, `ia/modelo_perfil.joblib`, `data/dataset_sintetico.csv`, `docs/ia/` (DATASET.md, MODELO.md, metricas.json, 2 gráficos), `tests/test_ia.py`, `docs/GUIA_SUBIDA_GITHUB.md`, `.gitignore`, `docs/entregables/` (PDFs) |
| **Modificados** | `app/core/perfil.py`, `app/core/servicio.py`, `app/api/esquemas.py`, `scripts/demo_maria.py`, `requirements.txt`, `README.md`, `docs/openapi.yaml`, `docs/demo_maria_salida.txt`, `docs/equipo/BITACORA_IA_S2.md`, `docs/equipo/CONTEXTO_INVIERTEYA_S2.md` |

> ⚠️ Si alguien del equipo modificó hoy alguno de los archivos **modificados**, revisa con
> `git diff <archivo>` que no se pierdan sus cambios antes de hacer el commit.

## Paso 4 · Instalar dependencias y probar

```powershell
py -3.13 -m venv .venv                 # solo si todavía no tienes el entorno
.venv\Scripts\activate                  # si falla: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt         # ahora incluye scikit-learn, pandas, numpy y joblib
python -m pytest -v
```

Resultado esperado: **`21 passed`** (CP-01 a CP-21).

- Si **CP-17 sale como `SKIPPED`**, o la demo dice `motor: reglas (modelo no disponible...)`, tu versión
  de scikit-learn no pudo abrir el modelo guardado. Regenéralo con `python ia/entrenar.py` (unos 20 s)
  y vuelve a correr las pruebas.
- Prueba rápida de punta a punta: `python scripts/demo_maria.py`. Debe mostrar
  `Motor: modelo baseline: regresión logística ... probabilidad 92%`.

## Paso 5 · Escaneo de seguridad (SAST/SCA) — lo pide el profesor

El código generado con IA debe pasar por SAST/SCA antes de integrarse:

```powershell
pip install bandit pip-audit
bandit -r app ia scripts -ll           # SAST: busca patrones inseguros en el código
pip-audit -r requirements.txt          # SCA: busca vulnerabilidades conocidas en dependencias
```

Copia el resumen de ambos (cantidad de hallazgos y su severidad) en la columna "Cómo lo validaron" de
la bitácora. Si `bandit` marca el uso de `joblib.load`, la explicación es que carga solo el archivo del
propio repositorio, nunca uno subido por un usuario.

## Paso 6 · Revisar, confirmar (commit) y subir (push)

```powershell
git status                              # revisa la lista: no debe aparecer .venv ni __pycache__
git add .
git commit -m "Baseline de IA: dataset sintético, modelo de perfil, métricas, pruebas CP-16 a CP-21 y documentación"
git push                                # si creaste rama: git push -u origin baseline-ia
```

Si usaste una rama, entra a GitHub, pulsa **Compare & pull request** → **Create pull request** →
**Merge**.

## Paso 7 · Verificar en GitHub

En la página del repositorio deben verse las carpetas `ia/`, `data/` y `docs/ia/`, y el README con la
sección **"Baseline de IA (resumen)"**. Abre `docs/ia/MODELO.md`: GitHub muestra las tablas y los
gráficos.

## Errores frecuentes

| Mensaje | Solución |
|---|---|
| `rejected ... (fetch first)` | Otro integrante subió algo antes. Ejecuta `git pull --rebase` y luego `git push` |
| `Authentication failed` / pide contraseña | GitHub no acepta la contraseña normal. Usa **GitHub Desktop** o crea un token en GitHub → Settings → Developer settings → Personal access tokens, y úsalo como contraseña |
| `CONFLICT (content)` al hacer pull | Abre el archivo, busca las marcas `<<<<<<<` y `>>>>>>>`, deja la versión correcta, y luego `git add <archivo>` y `git rebase --continue` |
| `warning: LF will be replaced by CRLF` | Es solo un aviso de Windows; se puede ignorar |
| `python` no se reconoce | Usa `py -3.13` en lugar de `python`, o activa el entorno virtual |
| `No module named 'sklearn'` | No instalaste las dependencias nuevas: `pip install -r requirements.txt` con el entorno activo |

## Alternativa sin consola: GitHub Desktop

1. **File → Clone repository** (o abre el que ya tengas) y luego **Fetch origin / Pull**.
2. Extrae el zip encima de la carpeta del repositorio (paso 3).
3. En GitHub Desktop aparecen los cambios. Escribe el mensaje del commit, pulsa **Commit to main** y
   luego **Push origin**.

(Las pruebas del paso 4 igual hay que correrlas en PowerShell.)

---

## Qué se carga en el aula virtual (no va en Git)

Los entregables en PDF están en `docs/entregables/`:

- `S2_EquipoD_BaselineIA.pdf`: dataset documentado, modelo, métricas, sesgos y tutor.
- `S2_EquipoD_Bitacora.pdf`: bitácora de uso de IA. **Antes de cargarla**, completa los nombres
  pendientes y las validaciones marcadas "Pendiente", y vuelve a exportarla.
