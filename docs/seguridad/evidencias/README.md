# Evidencias DevSecOps (`docs/seguridad/evidencias/`)

Guardar en esta carpeta los reportes descargados de **GitHub Actions** y las capturas de pantalla de la corrida en verde (primero en el PR de `feat/s3-devsecops-seguridad` y luego tras el merge en `main`):

- [ ] Captura del resumen de los 5 jobs en verde en GitHub Actions (`actions_pipeline_verde.png`)
- [ ] `bandit-report.txt` (SAST Python sin hallazgos críticos/altos sin mitigar)
- [ ] `pip-audit-report.txt` (SCA dependencias Python)
- [ ] `npm-audit-report.txt` (SCA dependencias front-end)
- [ ] `gitleaks-report.json` (0 secretos expuestos en historial Git)
- [ ] `zap-report.md` / `zap-report.html` (DAST OWASP ZAP Baseline contra FastAPI)
