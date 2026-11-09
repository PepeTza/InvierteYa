import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useIsPresent } from 'motion/react'
import type { Aporte, Cuestionario, Leccion, ResultadoPerfil, Usuario } from './lib/api'

export type Pantalla =
  | 'bienvenida' | 'registro' | 'kyc' | 'cuestionario' | 'perfil'
  | 'adhesion' | 'tarjeta' | 'aporte' | 'resultado' | 'portafolio'

// Pasos visibles en la barra de progreso del registro.
export const PASOS_REGISTRO: { pantallas: Pantalla[]; nombre: string }[] = [
  { pantallas: ['registro'], nombre: 'Cuenta' },
  { pantallas: ['kyc'], nombre: 'Identidad' },
  { pantallas: ['cuestionario', 'perfil'], nombre: 'Perfil' },
  { pantallas: ['adhesion'], nombre: 'Contrato' },
  { pantallas: ['tarjeta'], nombre: 'Pago' },
]

export interface Tarjeta { token: string; ultimos4: string; marca: string; tipo?: string }
export interface AporteEnCurso { monto: number; clave: string }

export interface Estado {
  pantalla: Pantalla
  direccion: 1 | -1
  usuario?: Usuario
  respuestas: Partial<Cuestionario>
  preguntaActual: number
  perfil?: ResultadoPerfil
  leccionAdhesion?: Leccion | null
  tarjeta?: Tarjeta
  enCurso?: AporteEnCurso
  aportes: Aporte[]
  aviso?: string
}

const INICIAL: Estado = { pantalla: 'bienvenida', direccion: 1, respuestas: {}, preguntaActual: 0, aportes: [] }
const CLAVE = 'invierteya.estado.v1'

function leer(): Estado {
  try {
    const guardado = sessionStorage.getItem(CLAVE)
    return guardado ? { ...INICIAL, ...JSON.parse(guardado) } : INICIAL
  } catch {
    return INICIAL
  }
}

interface Contexto {
  estado: Estado
  ir: (pantalla: Pantalla, direccion?: 1 | -1) => void
  actualizar: (cambios: Partial<Estado>) => void
  reiniciar: (aviso?: string) => void
}

const Ctx = createContext<Contexto | null>(null)

export function ProveedorEstado({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>(leer)

  useEffect(() => {
    try { sessionStorage.setItem(CLAVE, JSON.stringify(estado)) } catch { /* modo privado */ }
  }, [estado])

  const ir = useCallback((pantalla: Pantalla, direccion: 1 | -1 = 1) =>
    setEstado(e => ({ ...e, pantalla, direccion })), [])
  const actualizar = useCallback((cambios: Partial<Estado>) => setEstado(e => ({ ...e, ...cambios })), [])
  const reiniciar = useCallback((aviso?: string) => setEstado({ ...INICIAL, direccion: -1, aviso }), [])

  const valor = useMemo(() => ({ estado, ir, actualizar, reiniciar }), [estado, ir, actualizar, reiniciar])
  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>
}

export function useApp() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useApp fuera de ProveedorEstado')
  return ctx
}

/** Mientras una pantalla hace su animación de salida, sigue viendo el estado que tenía.
 *  Sin esto, al reiniciar la pantalla saliente (p. ej. Portafolio) leería un perfil ya borrado y fallaría. */
export function CongelarAlSalir({ children }: { children: ReactNode }) {
  const ctx = useApp()
  const presente = useIsPresent()
  const ultimo = useRef(ctx)
  if (presente) ultimo.current = ctx
  return <Ctx.Provider value={presente ? ctx : ultimo.current}>{children}</Ctx.Provider>
}

export const CLAVE_ESTADO = CLAVE
