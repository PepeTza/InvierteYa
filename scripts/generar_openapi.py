"""Genera docs/openapi.yaml (OpenAPI 3.1) a partir de la propia aplicación FastAPI.

Desde la Sesión 3 la especificación sale de `app.main.app.openapi()`, así que el archivo coincide
exactamente con lo que FastAPI publica en /openapi.json (rutas, esquemas Pydantic, ejemplos y
seguridad) y no hay que mantener las rutas a mano.

    python scripts/generar_openapi.py
"""
import sys
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from app.main import app  # noqa: E402

doc = app.openapi()
doc["servers"] = [{"url": "http://127.0.0.1:8000", "description": "Local"}]
esquemas_seguridad = doc.setdefault("components", {}).setdefault("securitySchemes", {})
if "HTTPBearer" in esquemas_seguridad:
    esquemas_seguridad["HTTPBearer"]["description"] = (
        "Simulado: usar `demo-token`. En producción, OAuth2/JWT validado en el API Gateway.")


class _SinAlias(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


salida = RAIZ / "docs" / "openapi.yaml"
salida.write_text(yaml.dump(doc, Dumper=_SinAlias, allow_unicode=True, sort_keys=False), encoding="utf-8")
print(f"Generado {salida} con {len(doc['paths'])} rutas y {len(doc['components'].get('schemas', {}))} esquemas")
