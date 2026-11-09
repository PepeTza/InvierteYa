import {
  Baby, BadgeCheck, Briefcase, Clock, Flame, GraduationCap, HeartHandshake, Hourglass,
  Mountain, PiggyBank, Rocket, Shield, ShieldAlert, ShoppingCart, Sprout, TrendingDown,
  TrendingUp, UserRound, Users, X, Check,
  type LucideIcon,
} from 'lucide-react'
import type { Cuestionario, Perfil } from './api'

// ------------------------------------------------------------------ formato
const dosDecimales = new Intl.NumberFormat('es-VE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const dinero = (n: number | string) => '$' + dosDecimales.format(Number(n))
export const unidades = (n: number | string) =>
  new Intl.NumberFormat('es-VE', { maximumFractionDigits: 4 }).format(Number(n))

// ------------------------------------------------------------------ portafolios
// Mismos valores que app/core/fideicomiso.py (PORTAFOLIOS).
export const PORTAFOLIOS: Record<Perfil, {
  nombre: string; valorUnidad: number; composicion: Record<string, number>
  color: string; suave: string; icono: LucideIcon; lema: string
}> = {
  CONSERVADOR: {
    nombre: 'Conservador', valorUnidad: 1.25, icono: Shield, lema: 'Estabilidad primero',
    composicion: { renta_fija: 70, fondos: 20, acciones: 10 },
    color: 'var(--color-conservador)', suave: 'var(--color-conservador-suave)',
  },
  MODERADO: {
    nombre: 'Moderado', valorUnidad: 1.32, icono: Mountain, lema: 'Equilibrio y crecimiento',
    composicion: { renta_fija: 40, fondos: 30, acciones: 30 },
    color: 'var(--color-moderado)', suave: 'var(--color-moderado-suave)',
  },
  AGRESIVO: {
    nombre: 'Agresivo', valorUnidad: 1.40, icono: Rocket, lema: 'Máximo crecimiento',
    composicion: { renta_fija: 15, fondos: 25, acciones: 60 },
    color: 'var(--color-agresivo)', suave: 'var(--color-agresivo-suave)',
  },
}

export const INSTRUMENTOS: Record<string, { nombre: string; color: string }> = {
  // Paleta validada (dataviz validate_palette.js, modo claro): pasa banda de luminosidad,
  // separación para daltonismo y piso de visión normal. Siempre va con etiquetas visibles.
  renta_fija: { nombre: 'Renta fija', color: '#0f7a55' },
  fondos: { nombre: 'Fondos', color: '#2f8fd0' },
  acciones: { nombre: 'Acciones', color: '#9cbf2e' },
}

// ------------------------------------------------------------------ cuestionario
export interface Opcion { valor: number | string | boolean; etiqueta: string; icono?: LucideIcon }

export interface Pregunta {
  campo: keyof Cuestionario
  titulo: string
  ayuda?: string
  tipo: 'opciones' | 'deslizador'
  opciones?: Opcion[]
  min?: number; max?: number; paso?: number; sufijo?: string; prefijo?: string
  inicial?: number
}

export const PREGUNTAS: Pregunta[] = [
  { campo: 'edad', titulo: '¿Cuántos años tienes?', tipo: 'deslizador',
    min: 18, max: 80, paso: 1, sufijo: ' años', inicial: 25 },
  { campo: 'ingreso_rango', titulo: '¿Cuánto ganas al mes?', ayuda: 'Un rango aproximado es suficiente.',
    tipo: 'opciones', opciones: [
      { valor: 1, etiqueta: 'Menos de $200' },
      { valor: 2, etiqueta: '$200 a $500' },
      { valor: 3, etiqueta: '$500 a $1.000' },
      { valor: 4, etiqueta: '$1.000 a $2.500' },
      { valor: 5, etiqueta: 'Más de $2.500' },
    ] },
  { campo: 'pct_invertible', titulo: '¿Qué parte de tu ingreso podrías invertir?', tipo: 'deslizador',
    min: 0, max: 50, paso: 1, sufijo: '%', inicial: 10 },
  { campo: 'horizonte_anios', titulo: '¿Cuándo necesitarás este dinero?', tipo: 'opciones', opciones: [
      { valor: 0.5, etiqueta: 'En menos de 1 año', icono: Clock },
      { valor: 2, etiqueta: 'En 1 a 3 años', icono: Hourglass },
      { valor: 4, etiqueta: 'En 3 a 5 años', icono: Sprout },
      { valor: 7, etiqueta: 'En más de 5 años', icono: Mountain },
    ] },
  { campo: 'objetivo', titulo: '¿Qué buscas al invertir?', tipo: 'opciones', opciones: [
      { valor: 'proteger', etiqueta: 'Que mi dinero no pierda valor', icono: Shield },
      { valor: 'crecer', etiqueta: 'Que crezca con el tiempo', icono: TrendingUp },
      { valor: 'ganar_rapido', etiqueta: 'Ganar lo más posible, rápido', icono: Flame },
    ] },
  { campo: 'reaccion_caida_20', titulo: 'Si tu inversión cae 20% en un mes…', tipo: 'opciones', opciones: [
      { valor: 'vender_todo', etiqueta: 'Vendo todo', icono: TrendingDown },
      { valor: 'esperar', etiqueta: 'Espero a que se recupere', icono: Hourglass },
      { valor: 'comprar_mas', etiqueta: 'Aprovecho y compro más', icono: ShoppingCart },
    ] },
  { campo: 'experiencia_previa', titulo: '¿Has invertido antes?', ayuda: 'Acciones, fondos, bonos u otros.',
    tipo: 'opciones', opciones: [
      { valor: true, etiqueta: 'Sí', icono: Check },
      { valor: false, etiqueta: 'Todavía no', icono: X },
    ] },
  { campo: 'fondo_emergencia', titulo: '¿Tienes un fondo de emergencia?',
    ayuda: 'Ahorros para cubrir al menos 3 meses de gastos.', tipo: 'opciones', opciones: [
      { valor: true, etiqueta: 'Sí, lo tengo', icono: PiggyBank },
      { valor: false, etiqueta: 'No por ahora', icono: ShieldAlert },
    ] },
  { campo: 'dependientes', titulo: '¿Cómo es tu hogar?',
    ayuda: 'Cuenta hijos, padres u otros familiares que mantienes.', tipo: 'opciones', opciones: [
      { valor: 0, etiqueta: 'Solo yo', icono: UserRound },
      { valor: 1, etiqueta: 'Yo y 1 persona a mi cargo', icono: HeartHandshake },
      { valor: 2, etiqueta: 'Yo y 2 personas a mi cargo', icono: Users },
      { valor: 3, etiqueta: 'Yo y 3 o más a mi cargo', icono: Baby },
    ] },
  { campo: 'conocimiento', titulo: '¿Cuánto sabes de inversiones?', tipo: 'opciones', opciones: [
      { valor: 1, etiqueta: 'Nada todavía', icono: Sprout },
      { valor: 2, etiqueta: 'Lo básico', icono: GraduationCap },
      { valor: 3, etiqueta: 'Intermedio', icono: Briefcase },
      { valor: 4, etiqueta: 'Bastante', icono: BadgeCheck },
      { valor: 5, etiqueta: 'Soy experto', icono: Rocket },
    ] },
]

// Respuestas del caso de María (speech): 24 años, freelance, ~$30/mes libres -> Moderado.
export const RESPUESTAS_MARIA: Cuestionario = {
  edad: 24, ingreso_rango: 2, pct_invertible: 15, horizonte_anios: 2, objetivo: 'crecer',
  reaccion_caida_20: 'esperar', experiencia_previa: false, fondo_emergencia: true,
  dependientes: 0, conocimiento: 2,
}

// ------------------------------------------------------------------ demo / ISO 8583
// `pasos`: lo que se encola en la pasarela simulada para el próximo aporte.
// La falla de captura necesita antes una autorización aprobada.
export const ESCENARIOS = [
  { id: 'APROBADA', etiqueta: 'Aprobada', detalle: '00', pasos: ['APROBADA'], ayuda: 'El banco aprueba el pago.' },
  { id: '51', etiqueta: 'Fondos insuficientes', detalle: '51', pasos: ['51'], ayuda: 'La cuenta no tiene saldo.' },
  { id: '05', etiqueta: 'No honrar', detalle: '05', pasos: ['05'], ayuda: 'El banco rechaza sin dar el motivo.' },
  { id: '59', etiqueta: 'Sospecha de fraude', detalle: '59', pasos: ['59'], ayuda: 'El banco cree que no es el titular.' },
  { id: 'TIMEOUT', etiqueta: 'Timeout → reverso', detalle: '30 s', pasos: ['TIMEOUT'], ayuda: 'El banco no responde a tiempo: InvierteYa reversa.' },
  { id: 'FALLA_CAPTURA', etiqueta: 'Falla en captura → reverso', detalle: '96', pasos: ['APROBADA', 'FALLA_CAPTURA'], ayuda: 'Se autoriza, pero el cobro falla: se reversa.' },
] as const

export const MTI: Record<string, string> = {
  '0100': 'Solicitud de autorización',
  '0110': 'Respuesta de autorización',
  '0220': 'Aviso de completación (captura)',
  '0230': 'Respuesta de completación',
  '0400': 'Solicitud de reverso',
  '0410': 'Respuesta de reverso',
  '0420': 'Aviso de reverso',
  '0421': 'Aviso de reverso (repetido)',
  '0500': 'Reconciliación',
  '0510': 'Respuesta de reconciliación',
}

export const CAMPOS_ISO: Record<string, string> = {
  '2': 'PAN (enmascarado)', '3': 'Código de proceso', '4': 'Monto', '7': 'Fecha/hora transmisión',
  '11': 'STAN (traza)', '37': 'RRN', '38': 'Código de autorización', '39': 'Código de respuesta',
  '41': 'Terminal', '42': 'Comercio', '49': 'Moneda', '74': 'Cantidad de créditos',
  '88': 'Monto total de créditos', '90': 'Datos originales',
}

export const TARJETAS_PRUEBA = [
  { pan: '4111111111111111', marca: 'Visa' },
  { pan: '5555555555554444', marca: 'Mastercard' },
]
