# Verificación Legal SUDEBAN — Sesión 3 (Track 4)

**Responsable:** Ronald Gómez · **Fecha:** 26-nov-2026  
**Propósito:** Validar las 3 citas legales pendientes de `docs/equipo/PLAN_TRABAJO_S3.md` antes de llevarlas a las láminas de la presentación (`S3_EquipoD_Presentacion.pdf`) y al guion.

---

## 1. Resolución SUDEBAN N° 001.21 (*Normas que Regulan los Servicios de Tecnología Financiera — FINTECH*)

- **Publicación original:** Gaceta Oficial N° **42.151** (17 de junio de 2021).
- **Reimpresión por fallas en los originales:** Gaceta Oficial N° **42.162** (6 de julio de 2021), que además incorporó ajustes en el articulado (entre ellos, Proveedores no Bancarios de Servicios de Pago — PSP autorizados por el BCV).
- **Mínimo de 5 accionistas (ITFB):** **Artículo 5, literal a** — exige constituirse como sociedad anónima con acciones nominativas de una misma clase y *"poseer un mínimo de cinco (5) accionistas"*, sujetos a requisitos de honorabilidad y sin inhabilitaciones legales.
- **Registro cronológico con dirección IP:** **Artículo 24** — establece entre las obligaciones de las ITFB:
  > *"Disponer del registro cronológico de las transacciones u operaciones efectuadas a través de su plataforma tecnológica, que permita identificar origen y destino de los fondos, fecha, hora, dirección IP y usuario."*
  - **Cómo lo cumple InvierteYa:** exactamente con esos campos en `app/core/auditoria.py` (`BitacoraAuditoria`), encadenados además con SHA-256 (`hash_previo → hash_actual`).
  - **Nota de precisión para láminas:** citar como *"Res. SUDEBAN 001.21 (G.O. 42.151 / reimp. G.O. 42.162), Art. 5 lit. a (5 accionistas) y Art. 24 (registro cronológico con IP)"* — y si se menciona un numeral interno del Art. 24, verificar directamente contra el PDF de la G.O. 42.162 antes de proyectarlo.

---

## 2. Resolución SUDEBAN N° 010.25 (*Normas Relativas a la Administración y Supervisión de los Riesgos de LC/FT/FPADM*)

- **Publicación:** Gaceta Oficial N° **43.098** (31 de marzo de 2025). Deroga la Resolución N° 083.18.
- **¿Menciona el enfoque "Conozca al cliente de su cliente" (KYCC)?**
  - **Sí.** La Resolución 010.25 incorpora formalmente mecanismos de debida diligencia bajo el esquema **"conoce el cliente de tu cliente" (KYCC — *Know Your Customer's Customer*)**, obligando a los sujetos obligados (bancos) a profundizar la trazabilidad y control cuando operan con intermediarios o clientes cuyas transacciones involucran a terceros.
- **Implicación para InvierteYa (Fase 1):** Como proveedor tecnológico aliado de un banco fiduciario, el banco exige KYC completo y trazabilidad individual de cada inversionista final (fideicomitente) para cumplir con su debida diligencia KYCC ante SUDEBAN.

---

## 3. Gacetas Oficiales de las Resoluciones N° 083.12 y N° 063.15

| Resolución | Gaceta Oficial | Fecha de publicación | Materia principal y uso en InvierteYa |
|---|---|---|---|
| **Res. SUDEBAN N° 083.12** | **G.O. N° 39.941** | 11 de junio de 2012 *(dictada 31-may-2011)* | *Normas que Regulan las Operaciones de Fideicomisos*: deber de administrador diligente (*buen padre de familia*), protección del público, diversificación de riesgos y sistemas sólidos de registro/valuación. Respalda el vehículo fiduciario y la conciliación en 3 niveles. |
| **Res. SUDEBAN N° 063.15** | **G.O. N° 40.809** | 14 de diciembre de 2015 *(derogó Res. 083.11)* | *Normas Relativas a la Protección de los Usuarios y Usuarias de los Servicios Financieros*: obliga a transparentar y publicar de forma accesible tasas, comisiones, gastos y recargos. Respalda el desglose explícito de `comision_aporte_pct` (1%) y `recargo_medio_pago_pct` (2% tarjeta / 0% Pago Móvil). |

---

## 4. Vigencia y punto clave para la defensa

- **Las cuatro normas citadas están vigentes:** `083.12` (2012, fideicomisos), `063.15` (2015, protección al usuario), `001.21` (2021, Fintech/ITFB) y `010.25` (2025, LC/FT/FPADM).
- **Ojo con la confusión frecuente (pregunta típica de defensa):** no confundir la **Res. 083.12** (fideicomisos, **vigente**) con la **Res. 083.18** (prevención de legitimación de capitales, **derogada** en marzo de 2025 por la **Res. 010.25**). InvierteYa ya cita la `010.25` vigente para LC/FT/KYCC y la `083.12` vigente para la operación fiduciaria.
