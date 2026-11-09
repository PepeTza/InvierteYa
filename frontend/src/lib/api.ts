// Cliente de la API de InvierteYa (backend FastAPI) y de la pasarela SIMULADA.
// Autenticación SIMULADA: Bearer demo-token (en producción sería OAuth2/JWT en el API Gateway).

const TOKEN_DEMO = 'demo-token'

export type Perfil = 'CONSERVADOR' | 'MODERADO' | 'AGRESIVO'

export interface Leccion {
  id: string
  paso: string
  perfil: string
  nivel: string
  titulo: string
  texto: string
}

export interface Usuario {
  usuario_id: string
  nombre: string
  kyc_aprobado: boolean
  adhesion_firmada: boolean
  perfil: Perfil | null
}

export interface Cuestionario {
  edad: number
  ingreso_rango: number
  pct_invertible: number
  horizonte_anios: number
  objetivo: 'proteger' | 'crecer' | 'ganar_rapido'
  reaccion_caida_20: 'vender_todo' | 'esperar' | 'comprar_mas'
  experiencia_previa: boolean
  fondo_emergencia: boolean
  dependientes: number
  conocimiento: number
}

export interface ResultadoPerfil {
  perfil: Perfil
  puntaje: number
  puntaje_maximo: number
  explicacion: string
  factores_suben?: string[]
  factores_moderan?: string[]
  avisos: string[]
  leccion: Leccion | null
  motor: string
}

export interface ResultadoAdhesion {
  usuario_id: string
  adhesion: string
  fideicomitente_y_beneficiario: boolean
  leccion: Leccion | null
}

export type EstadoAporte =
  | 'PENDIENTE' | 'AUTORIZADO' | 'CAPTURADO' | 'ASIGNADO' | 'RECHAZADO'
  | 'EN_REVERSO' | 'REVERSADO' | 'REVERSO_PENDIENTE'

export interface MensajeIso {
  mti: string
  campos: Record<string, string>
}

export interface Aporte {
  id: string
  usuario_id: string
  portafolio: string
  monto: string
  estado: EstadoAporte
  unidades: string | null
  mensaje: string | null
  leccion: Leccion | null
  rrn: string | null
  auth_code: string | null
  eventos: { estado: string; detalle: string }[]
  iso8583: MensajeIso[]
  latencia_total_ms: number | null
  duplicado: boolean
  registrado?: number   // solo en el cliente: cuándo se mostró el resultado (para la tabla de actividad)
}

export interface Portafolio {
  usuario_id: string
  portafolio: Perfil | null
  unidades: string
  valor_unidad: string
  saldo: string
  composicion: Record<string, number>
  aportes: number
  leccion: Leccion | null
}

export interface ExcepcionConciliacion {
  tipo: string
  [k: string]: unknown
}

export interface NivelConciliacion {
  nivel: number
  cuadra: boolean
  excepciones: ExcepcionConciliacion[]
}

export interface ResultadoCierre {
  fecha: string
  conciliado: boolean
  niveles: NivelConciliacion[]
  excepciones: ExcepcionConciliacion[]
  propuesta_ordenes: { portafolio: string; instrumento: string; monto_centavos: number }[]
  batch: { aprobada: boolean; ordenes?: number; motivo?: string; nota: string }
  ya_cerrado: boolean
}

export class ErrorApi extends Error {
  codigo: string
  status: number
  constructor(status: number, codigo: string, mensaje: string) {
    super(mensaje)
    this.status = status
    this.codigo = codigo
  }
}

async function llamar<T>(ruta: string, opciones: RequestInit = {}): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(ruta, {
      ...opciones,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${TOKEN_DEMO}`,
        ...opciones.headers,
      },
    })
  } catch {
    throw new ErrorApi(0, 'SIN_CONEXION',
      'No hay conexión con el servidor de InvierteYa. ¿Está corriendo uvicorn?')
  }
  const cuerpo = await resp.json().catch(() => null)
  if (!resp.ok) {
    const codigo = cuerpo?.codigo ?? `HTTP_${resp.status}`
    let mensaje = cuerpo?.mensaje ?? 'Ocurrió un error inesperado.'
    if (Array.isArray(cuerpo?.detail)) mensaje = 'Revisa los datos ingresados.'
    else if (typeof cuerpo?.detail === 'string') mensaje = cuerpo.detail
    throw new ErrorApi(resp.status, codigo, mensaje)
  }
  return cuerpo as T
}

const post = <T>(ruta: string, cuerpo?: unknown, headers?: HeadersInit) =>
  llamar<T>(ruta, { method: 'POST', body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo), headers })

export const api = {
  registrar: (nombre: string, email: string) => post<Usuario>('/v1/usuarios', { nombre, email }),
  kyc: (id: string) => post<{ kyc: string }>(`/v1/usuarios/${id}/kyc`),
  perfil: (id: string, c: Cuestionario) => post<ResultadoPerfil>(`/v1/usuarios/${id}/perfil`, c),
  adhesion: (id: string) => post<ResultadoAdhesion>(`/v1/usuarios/${id}/adhesion`, { acepta: true }),
  leccion: (paso: string, perfil: Perfil, conocimiento: number) =>
    llamar<Leccion | null>(`/v1/lecciones?paso=${paso}&perfil=${perfil}&conocimiento=${conocimiento}`),
  aportar: (usuario_id: string, monto: number, token_tarjeta: string, clave: string) =>
    post<Aporte>('/v1/aportes', { usuario_id, monto, token_tarjeta }, { 'Idempotency-Key': clave }),
  portafolio: (id: string) => llamar<Portafolio>(`/v1/usuarios/${id}/portafolio`),
  // reemplazar=true: cada clic define el PRÓXIMO pago (no se acumula una cola).
  forzar: (escenarios: readonly string[]) =>
    post<{ forzados: string[] }>(`/v1/demo/forzar-escenario?reemplazar=true&${
      escenarios.map(e => `escenarios=${encodeURIComponent(e)}`).join('&')}`),
  reiniciarDemo: () => post<{ reiniciado: boolean }>('/v1/demo/reiniciar'),
  cierre: (inyectarDescuadre: boolean) =>
    post<ResultadoCierre>(`/v1/operaciones/cierre?inyectar_descuadre=${inyectarDescuadre}`),
  // Esto lo expone la PASARELA (su formulario/SDK), no InvierteYa: el PAN nunca llega a nuestro backend.
  tokenizar: (pan: string) => post<{ token: string }>('/pasarela/v1/tokens', { pan }),
}
