import { AnimatePresence, motion } from 'motion/react'
import {
  BookOpen, CalendarCheck, Check, ChevronDown, ExternalLink, FlaskConical, Monitor, RotateCcw, Smartphone,
  Sparkles, X, Zap,
} from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useApp } from '../estado'
import { api, type ResultadoCierre } from '../lib/api'
import { dinero, ESCENARIOS, PREGUNTAS, RESPUESTAS_MARIA } from '../lib/datos'
import { cx } from './ui'

const NIVELES = ['Pagos vs. liquidación de la pasarela', 'Aportes vs. abono al fideicomiso', 'Unidades vs. custodia (CVV)']

function Seccion({ titulo, icono, children, abierta = true }: {
  titulo: string; icono: ReactNode; children: ReactNode; abierta?: boolean
}) {
  const [abierto, setAbierto] = useState(abierta)
  return (
    <section className="rounded-2xl border border-borde bg-superficie">
      <button onClick={() => setAbierto(a => !a)} aria-expanded={abierto}
        className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm font-bold">
        <span className="text-marca">{icono}</span>{titulo}
        <motion.span className="ml-auto" animate={{ rotate: abierto ? 180 : 0 }}><ChevronDown className="size-4 text-suave" /></motion.span>
      </button>
      <AnimatePresence initial={false}>
        {abierto && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden">
            <div className="px-4 pb-4">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

export type Vista = 'movil' | 'web'

/** Selector de vista del prototipo: app móvil o versión web. */
function SelectorVista({ vista, onVista }: { vista: Vista; onVista: (v: Vista) => void }) {
  const opciones = [
    { id: 'movil' as const, etiqueta: 'Móvil', icono: Smartphone },
    { id: 'web' as const, etiqueta: 'Web', icono: Monitor },
  ]
  return (
    <div className="relative grid grid-cols-2 rounded-2xl bg-borde/70 p-1" role="tablist" aria-label="Vista del prototipo">
      {opciones.map(({ id, etiqueta, icono: Icono }) => (
        <button key={id} role="tab" aria-selected={vista === id} onClick={() => onVista(id)}
          className={cx('relative z-10 flex items-center justify-center gap-1.5 rounded-xl py-2 text-sm font-semibold transition-colors',
            vista === id ? 'text-tinta' : 'text-suave hover:text-tinta')}>
          {vista === id && (
            <motion.span layoutId="vista-activa" className="absolute inset-0 -z-10 rounded-xl bg-superficie shadow-tarjeta"
              transition={{ type: 'spring', stiffness: 400, damping: 32 }} />
          )}
          <Icono className="size-4" />{etiqueta}
        </button>
      ))}
    </div>
  )
}

/** Panel del presentador: NO es parte de la app; sirve para controlar la demo en vivo. */
export default function PanelDemo({ onCerrar, vista, onVista }: {
  onCerrar?: () => void; vista?: Vista; onVista?: (v: Vista) => void
}) {
  const { estado, actualizar, reiniciar } = useApp()
  const [confirmando, setConfirmando] = useState(false)
  const temporizador = useRef<number | undefined>(undefined)
  // Escenario elegido para el PRÓXIMO pago (null = resultado aleatorio de la pasarela).
  const [elegido, setElegido] = useState<string | null>(null)
  const [cierre, setCierre] = useState<ResultadoCierre | null>(null)
  const [descuadre, setDescuadre] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function forzar(id: string, pasos: readonly string[]) {
    try {
      setError(null)
      await api.forzar(pasos)
      setElegido(id)
    } catch (e) { setError((e as Error).message) }
  }

  async function cerrarDia() {
    setOcupado(true); setError(null)
    try { setCierre(await api.cierre(descuadre)) } catch (e) { setError((e as Error).message) }
    setOcupado(false)
  }

  // El aporte siguiente consume el escenario elegido: vuelve a quedar en aleatorio.
  const totalAportes = estado.aportes.length
  useEffect(() => { setElegido(null) }, [totalAportes])
  const escenario = ESCENARIOS.find(e => e.id === elegido)

  const enCuestionario = estado.pantalla === 'cuestionario'

  // Reinicio en dos toques (sin diálogos nativos del navegador, que Chrome puede bloquear).
  async function pedirReinicio() {
    if (!confirmando) {
      setConfirmando(true)
      window.clearTimeout(temporizador.current)
      temporizador.current = window.setTimeout(() => setConfirmando(false), 4000)
      return
    }
    window.clearTimeout(temporizador.current)
    setConfirmando(false)
    try { await api.reiniciarDemo() } catch { /* si el servidor no responde, igual se reinicia la app */ }
    setElegido(null); setCierre(null); setError(null); setDescuadre(false)
    reiniciar()
    onCerrar?.()
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-1 pb-3">
        <FlaskConical className="size-5 text-marca" />
        <div className="flex-1">
          <h2 className="font-bold">Panel de demo</h2>
          <p className="text-xs text-suave">Para el presentador · no forma parte de la app</p>
        </div>
        {onCerrar && (
          <button onClick={onCerrar} aria-label="Cerrar panel" className="grid size-9 place-items-center rounded-full hover:bg-borde">
            <X className="size-4.5" />
          </button>
        )}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto pb-4 sin-scrollbar">
        {vista && onVista && <SelectorVista vista={vista} onVista={onVista} />}
        {error && <p className="rounded-xl bg-error-suave p-3 text-xs text-error">{error}</p>}

        <Seccion titulo="Próximo resultado del pago" icono={<Zap className="size-4" />}>
          <div className="grid grid-cols-2 gap-2">
            {ESCENARIOS.map(e => (
              <button key={e.id} onClick={() => forzar(e.id, e.pasos)} aria-pressed={elegido === e.id} title={e.ayuda}
                className={cx('flex items-center justify-between gap-1 rounded-xl border px-2.5 py-2 text-left text-xs font-semibold transition',
                  elegido === e.id ? 'border-marca bg-marca-suave ring-2 ring-marca/20' : 'border-borde hover:border-marca hover:bg-marca-suave')}>
                <span>{e.etiqueta}</span>
                <span className="shrink-0 rounded bg-fondo px-1 font-mono text-[10px] whitespace-nowrap text-suave">{e.detalle}</span>
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-suave">
            {escenario
              ? <>Próximo pago: <b className="text-tinta">{escenario.etiqueta}</b>. {escenario.ayuda} Luego vuelve a ser aleatorio.</>
              : 'Sin forzar: resultado aleatorio (≈88% aprobadas).'}
          </p>
          <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-fondo px-2.5 py-2 text-[11px] text-suave">
            <span className="mt-px rounded bg-superficie px-1 font-mono text-[10px]">51</span>
            Código de respuesta del banco emisor (ISO 8583, campo 39).
          </p>
        </Seccion>

        <Seccion titulo="Atajos" icono={<Sparkles className="size-4" />}>
          <div className="space-y-2">
            <button disabled={!enCuestionario}
              onClick={() => actualizar({ respuestas: RESPUESTAS_MARIA, preguntaActual: PREGUNTAS.length })}
              className="flex w-full items-center gap-2 rounded-xl border border-borde px-3 py-2.5 text-left text-xs font-semibold transition enabled:hover:border-marca enabled:hover:bg-marca-suave disabled:opacity-50">
              <BookOpen className="size-4 text-marca" />
              Responder el cuestionario como María
              {!enCuestionario && <span className="ml-auto font-normal text-suave">(en el cuestionario)</span>}
            </button>
            <a href="/docs" target="_blank" rel="noreferrer"
              className="flex items-center gap-2 rounded-xl border border-borde px-3 py-2.5 text-xs font-semibold transition hover:border-marca hover:bg-marca-suave">
              <ExternalLink className="size-4 text-marca" /> Abrir Swagger (OpenAPI 3)
            </a>
            <button onClick={pedirReinicio}
              className={cx('flex w-full items-center gap-2 rounded-xl border px-3 py-2.5 text-left text-xs font-semibold transition',
                confirmando ? 'border-error bg-error text-white' : 'border-borde hover:border-error hover:bg-error-suave')}>
              <RotateCcw className={cx('size-4', confirmando ? 'text-white' : 'text-error')} />
              {confirmando ? '¿Seguro? Toca otra vez para borrar todo' : 'Reiniciar recorrido'}
            </button>
          </div>
        </Seccion>

        <Seccion titulo="Cierre del día · conciliación" icono={<CalendarCheck className="size-4" />}>
          <label className="mb-3 flex items-center gap-2 text-xs">
            <input type="checkbox" checked={descuadre} onChange={e => setDescuadre(e.target.checked)} className="accent-[var(--color-marca)]" />
            Simular que la pasarela omite una transacción
          </label>
          <button onClick={cerrarDia} disabled={ocupado}
            className="w-full rounded-xl bg-tinta py-2.5 text-xs font-bold text-white transition hover:bg-tinta/85 disabled:opacity-60">
            {ocupado ? 'Ejecutando…' : 'Ejecutar cierre (T+1)'}
          </button>
          <AnimatePresence>
            {cierre && (
              <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="mt-3 space-y-2">
                <div className={cx('rounded-xl px-3 py-2 text-xs font-bold',
                  cierre.conciliado ? 'bg-marca-suave text-marca' : 'bg-error-suave text-error')}>
                  {cierre.conciliado ? 'Conciliado en los 3 niveles' : `${cierre.excepciones.length} excepción(es) a revisión`}
                  {cierre.ya_cerrado && <span className="font-normal"> · el día ya estaba cerrado</span>}
                </div>
                {cierre.niveles.map((n, i) => (
                  <motion.div key={n.nivel} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.12 }}
                    className="flex items-start gap-2 text-xs">
                    <span className={cx('mt-0.5 grid size-4 shrink-0 place-items-center rounded-full text-white', n.cuadra ? 'bg-marca' : 'bg-error')}>
                      {n.cuadra ? <Check className="size-3" strokeWidth={3} /> : <X className="size-3" strokeWidth={3} />}
                    </span>
                    <div>
                      <p className="font-semibold">Nivel {n.nivel}: {NIVELES[n.nivel - 1]}</p>
                      {n.excepciones.map((ex, j) => (
                        <p key={j} className="text-error">{ex.tipo.replaceAll('_', ' ').toLowerCase()}</p>
                      ))}
                    </div>
                  </motion.div>
                ))}
                {cierre.propuesta_ordenes.length > 0 && (
                  <div className="rounded-xl bg-fondo p-3 text-xs">
                    <p className="mb-1 font-bold">Órdenes por lote (InvierteYa propone · fiduciario aprueba)</p>
                    {cierre.propuesta_ordenes.map((o, i) => (
                      <p key={i} className="flex justify-between text-suave">
                        <span>{o.portafolio.toLowerCase()} · {o.instrumento.replace('_', ' ')}</span>
                        <span className="cifra font-semibold text-tinta">{dinero(o.monto_centavos / 100)}</span>
                      </p>
                    ))}
                    <p className="mt-1 text-suave">{cierre.batch.aprobada ? '✓ Aprobado' : '✗ Rechazado'} · {cierre.batch.nota}</p>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
          <p className="mt-2 text-[11px] text-suave">El cierre de cada fecha corre una sola vez.</p>
        </Seccion>
      </div>
    </div>
  )
}
