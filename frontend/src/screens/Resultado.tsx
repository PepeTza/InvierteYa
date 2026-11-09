import { AnimatePresence, motion } from 'motion/react'
import {
  AlertTriangle, BadgeCheck, Check, ClipboardCheck, Clock, Code2, PieChart, RotateCcw, Undo2, Wallet, X,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useApp } from '../estado'
import { api, ErrorApi, type Aporte } from '../lib/api'
import { dinero, unidades } from '../lib/datos'
import { Boton, Hoja, MensajeError, TarjetaTutor, cx } from '../components/ui'
import VisorIso from '../components/VisorIso'

// Evita enviar dos veces la misma solicitud (React StrictMode monta los efectos dos veces en desarrollo).
const solicitudes = new Map<string, Promise<Aporte>>()

const PASOS: Record<string, { icono: LucideIcon; titulo: string; tono: 'ok' | 'error' | 'aviso' }> = {
  PENDIENTE: { icono: ClipboardCheck, titulo: 'Validaciones', tono: 'ok' },
  AUTORIZADO: { icono: BadgeCheck, titulo: 'Autorizado por tu banco', tono: 'ok' },
  CAPTURADO: { icono: Wallet, titulo: 'Cobro confirmado', tono: 'ok' },
  ASIGNADO: { icono: PieChart, titulo: 'Unidades asignadas', tono: 'ok' },
  RECHAZADO: { icono: X, titulo: 'Pago no aprobado', tono: 'error' },
  EN_REVERSO: { icono: AlertTriangle, titulo: 'Iniciando reverso', tono: 'aviso' },
  REVERSADO: { icono: Undo2, titulo: 'Cobro reversado', tono: 'aviso' },
  REVERSO_PENDIENTE: { icono: Clock, titulo: 'Reverso pendiente', tono: 'aviso' },
}

const DESENLACE = {
  ASIGNADO: { titulo: '¡Inversión lista!', icono: Check, fondo: 'bg-marca' },
  RECHAZADO: { titulo: 'Pago no aprobado', icono: X, fondo: 'bg-error' },
  REVERSADO: { titulo: 'No se realizó el cobro', icono: RotateCcw, fondo: 'bg-aviso' },
  REVERSO_PENDIENTE: { titulo: 'Confirmando con tu banco', icono: Clock, fondo: 'bg-aviso' },
} as const

const TONO = { ok: 'bg-marca text-white', error: 'bg-error text-white', aviso: 'bg-aviso text-white' }

export default function Resultado() {
  const { estado, ir, actualizar } = useApp()
  const { enCurso, usuario, tarjeta } = estado
  const [aporte, setAporte] = useState<Aporte | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [visibles, setVisibles] = useState(0)
  const [verIso, setVerIso] = useState(false)
  const registrado = useRef(false)

  useEffect(() => {
    if (!enCurso || !usuario || !tarjeta) return
    let vivo = true
    const inicio = Date.now()
    let p = solicitudes.get(enCurso.clave)
    if (!p) {
      p = api.aportar(usuario.usuario_id, enCurso.monto, tarjeta.token, enCurso.clave)
      solicitudes.set(enCurso.clave, p)
    }
    p.then(async a => {
      // Pausa mínima para que el usuario vea el proceso (la latencia de la pasarela está simulada).
      await new Promise(r => setTimeout(r, Math.max(0, 900 - (Date.now() - inicio))))
      if (vivo) setAporte(a)
    }).catch(e => vivo && setError(e instanceof ErrorApi ? e.message : 'No se pudo procesar el aporte.'))
    return () => { vivo = false }
  }, [enCurso, usuario, tarjeta])

  // Revela los eventos del aporte uno por uno.
  useEffect(() => {
    if (!aporte || visibles >= aporte.eventos.length) return
    const t = setTimeout(() => setVisibles(v => v + 1), visibles === 0 ? 150 : 520)
    return () => clearTimeout(t)
  }, [aporte, visibles])

  const listo = aporte !== null && visibles >= aporte.eventos.length

  // Guarda el aporte en el historial (una sola vez).
  useEffect(() => {
    if (listo && aporte && !registrado.current) {
      registrado.current = true
      if (!estado.aportes.some(a => a.id === aporte.id)) actualizar({ aportes: [{ ...aporte, registrado: Date.now() }, ...estado.aportes] })
    }
  }, [listo, aporte, actualizar, estado.aportes])

  const desenlace = listo ? DESENLACE[aporte.estado as keyof typeof DESENLACE] : undefined
  const IconoDesenlace = desenlace?.icono

  return (
    <div className="relative flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-6 pt-10 pb-6 sin-scrollbar @2xl:[&>*]:mx-auto @2xl:[&>*]:max-w-xl">
        {/* Indicador principal */}
        <div className="flex flex-col items-center text-center">
          <div className="relative grid size-24 place-items-center">
            <AnimatePresence mode="wait">
              {desenlace && IconoDesenlace ? (
                <motion.div key="fin" initial={{ scale: 0 }} animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 260, damping: 15 }}
                  className={cx('grid size-24 place-items-center rounded-full text-white', desenlace.fondo)}>
                  <IconoDesenlace className="size-11" strokeWidth={3} />
                </motion.div>
              ) : (
                <motion.div key="carga" exit={{ scale: 0.6, opacity: 0 }} className="absolute inset-0">
                  <svg viewBox="0 0 96 96" className="size-full animate-spin [animation-duration:1.2s]">
                    <circle cx="48" cy="48" r="40" fill="none" stroke="var(--color-marca-suave)" strokeWidth="8" />
                    <circle cx="48" cy="48" r="40" fill="none" stroke="var(--color-marca)" strokeWidth="8"
                      strokeLinecap="round" strokeDasharray="70 251" />
                  </svg>
                </motion.div>
              )}
            </AnimatePresence>
            {listo && aporte?.estado === 'ASIGNADO' && <Confeti />}
          </div>
          <motion.h1 key={desenlace?.titulo ?? 'proc'} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            className="mt-5 text-2xl font-extrabold tracking-tight">
            {desenlace?.titulo ?? 'Procesando tu aporte'}
          </motion.h1>
          <p className="cifra mt-1 text-4xl font-extrabold">{enCurso ? dinero(enCurso.monto) : ''}</p>
          {listo && aporte?.unidades && (
            <motion.p initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }}
              className="mt-2 rounded-full bg-lima px-3 py-1 text-sm font-bold">
              +<span className="cifra">{unidades(aporte.unidades)}</span> unidades
            </motion.p>
          )}
          {listo && aporte?.mensaje && aporte.estado !== 'ASIGNADO' && (
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 text-[15px] text-suave text-pretty">
              {aporte.mensaje}
            </motion.p>
          )}
          {aporte?.duplicado && (
            <p className="mt-2 rounded-full bg-conservador-suave px-3 py-1 text-xs font-semibold text-conservador">
              Solicitud repetida: se devolvió el resultado original
            </p>
          )}
        </div>

        {/* Línea de tiempo con los eventos reales del backend */}
        <ol className="mt-8 space-y-0">
          {!aporte && !error && (
            <li className="flex items-center gap-3 py-2 text-sm text-suave">
              <span className="size-8" />Pasarela aliada → suiche → tu banco…
            </li>
          )}
          {aporte?.eventos.slice(0, visibles).map((ev, i) => {
            const paso = PASOS[ev.estado] ?? PASOS.PENDIENTE
            const Icono = paso.icono
            const ultimo = i === aporte.eventos.length - 1
            return (
              <motion.li key={i} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                className="relative flex gap-3 pb-4">
                {!ultimo && <span className="absolute top-9 bottom-0 left-4 w-0.5 -translate-x-1/2 bg-borde" />}
                <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 18 }}
                  className={cx('relative grid size-8 shrink-0 place-items-center rounded-full', TONO[paso.tono])}>
                  <Icono className="size-4" />
                </motion.span>
                <div className="pt-1">
                  <p className="text-sm font-semibold">{paso.titulo}</p>
                  <p className="text-xs text-suave">{ev.detalle}</p>
                </div>
              </motion.li>
            )
          })}
        </ol>

        <MensajeError mensaje={error} />

        {listo && aporte?.estado === 'ASIGNADO' && <TarjetaTutor leccion={aporte.leccion} retraso={0.3} />}

        {listo && aporte && aporte.iso8583.length > 0 && (
          <motion.button initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}
            onClick={() => setVerIso(true)}
            className="mx-auto mt-5 flex items-center gap-1.5 rounded-full px-3 py-2 text-sm font-semibold text-marca hover:bg-marca-suave">
            <Code2 className="size-4" /> Ver mensajes ISO 8583
            {aporte.latencia_total_ms && <span className="cifra font-normal text-suave">· {Math.round(aporte.latencia_total_ms)} ms</span>}
          </motion.button>
        )}
      </div>

      <AnimatePresence>
        {(listo || error) && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="shrink-0 space-y-3 px-6 pt-2 pb-6 @2xl:mx-auto @2xl:w-full @2xl:max-w-xl">
            {aporte?.estado === 'ASIGNADO' || aporte?.estado === 'REVERSO_PENDIENTE' ? (
              <Boton onClick={() => ir('portafolio')}>Ver mi portafolio</Boton>
            ) : (
              <>
                <Boton onClick={() => ir('aporte', -1)}>Intentar de nuevo</Boton>
                {estado.aportes.some(a => a.estado === 'ASIGNADO') &&
                  <Boton variante="fantasma" onClick={() => ir('portafolio')}>Ir a mi portafolio</Boton>}
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <Hoja abierta={verIso} onCerrar={() => setVerIso(false)} titulo="Mensajería ISO 8583">
        {aporte && <VisorIso mensajes={aporte.iso8583} />}
      </Hoja>
    </div>
  )
}

/** Pequeña celebración al asignar unidades. */
function Confeti() {
  const piezas = Array.from({ length: 14 }, (_, i) => i)
  const colores = ['var(--color-lima)', 'var(--color-marca)', '#4fb98d', 'var(--color-moderado)']
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden>
      {piezas.map(i => {
        const angulo = (i / piezas.length) * Math.PI * 2
        return (
          <motion.span key={i} className="absolute top-1/2 left-1/2 size-2 rounded-sm"
            style={{ background: colores[i % colores.length] }}
            initial={{ x: 0, y: 0, opacity: 1, rotate: 0 }}
            animate={{ x: Math.cos(angulo) * 80, y: Math.sin(angulo) * 80, opacity: 0, rotate: 180 }}
            transition={{ duration: 0.9, ease: 'easeOut', delay: 0.1 }} />
        )
      })}
    </div>
  )
}
