import { AnimatePresence, motion } from 'motion/react'
import { AlertCircle, ChevronLeft, GraduationCap, Loader2, X } from 'lucide-react'
import { useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'
import type { Leccion } from '../lib/api'
import { INSTRUMENTOS } from '../lib/datos'

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

// ------------------------------------------------------------------ marca
/** Isotipo: una "Y" cuyo brazo derecho es una flecha que sube (Invierte·Ya = crecer ya). */
export function Isotipo({ className = 'size-10' }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden>
      <rect width="48" height="48" rx="14" fill="var(--color-marca)" />
      <path d="M14 14 L24 26 V36" fill="none" stroke="white" strokeWidth="4.5"
        strokeLinecap="round" strokeLinejoin="round" />
      <path d="M24 26 L35 13" fill="none" stroke="var(--color-lima)" strokeWidth="4.5"
        strokeLinecap="round" strokeLinejoin="round" />
      <path d="M28.5 12.5 H35.5 V19.5" fill="none" stroke="var(--color-lima)" strokeWidth="4.5"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function Logo({ tamano = 'md' }: { tamano?: 'sm' | 'md' | 'lg' }) {
  const t = { sm: ['size-7', 'text-lg'], md: ['size-9', 'text-xl'], lg: ['size-14', 'text-3xl'] }[tamano]
  return (
    <div className="flex items-center gap-2.5">
      <Isotipo className={t[0]} />
      <span className={cx('font-extrabold tracking-tight', t[1])}>
        Invierte<span className="text-marca">Ya</span>
      </span>
    </div>
  )
}

// ------------------------------------------------------------------ botones
type VarianteBoton = 'primario' | 'secundario' | 'fantasma'
interface BotonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: VarianteBoton
  cargando?: boolean
  icono?: ReactNode
}

export function Boton({ variante = 'primario', cargando, icono, className, children, disabled, ...props }: BotonProps) {
  const estilos: Record<VarianteBoton, string> = {
    primario: 'bg-marca text-white hover:bg-marca-fuerte shadow-[0_8px_20px_-8px_rgb(15_122_85/0.6)] disabled:bg-tenue disabled:shadow-none',
    secundario: 'bg-superficie text-tinta border border-borde hover:border-marca/40 hover:bg-marca-suave',
    fantasma: 'text-marca hover:bg-marca-suave',
  }
  return (
    <motion.button
      whileTap={{ scale: disabled || cargando ? 1 : 0.97 }}
      transition={{ duration: 0.12 }}
      className={cx('inline-flex h-14 w-full items-center justify-center gap-2 rounded-2xl px-5 text-[15px] font-semibold transition-colors',
        estilos[variante], className)}
      disabled={disabled || cargando}
      {...(props as object)}
    >
      {cargando ? <Loader2 className="size-5 animate-spin" /> : icono}
      {children}
    </motion.button>
  )
}

// ------------------------------------------------------------------ encabezado
export function Encabezado({ onAtras, pasoActual, totalPasos, derecha }: {
  onAtras?: () => void; pasoActual?: number; totalPasos?: number; derecha?: ReactNode
}) {
  return (
    <div className="flex h-14 shrink-0 items-center gap-3 px-4 @2xl:mx-auto @2xl:w-full @2xl:max-w-[920px] @2xl:px-6 @2xl:pt-4">
      {onAtras ? (
        <button onClick={onAtras} aria-label="Volver"
          className="grid size-10 place-items-center rounded-full text-tinta transition-colors hover:bg-black/5">
          <ChevronLeft className="size-6" />
        </button>
      ) : <div className="size-10" />}
      {totalPasos !== undefined && pasoActual !== undefined ? (
        <div className="flex flex-1 gap-1.5 @2xl:invisible" role="progressbar" aria-valuenow={pasoActual + 1} aria-valuemax={totalPasos}>
          {Array.from({ length: totalPasos }, (_, i) => (
            <div key={i} className="h-1.5 flex-1 overflow-hidden rounded-full bg-borde">
              <motion.div className="h-full rounded-full bg-marca"
                initial={false}
                animate={{ width: i < pasoActual ? '100%' : i === pasoActual ? '50%' : '0%' }}
                transition={{ duration: 0.4, ease: 'easeOut' }} />
            </div>
          ))}
        </div>
      ) : <div className="flex-1" />}
      <div className="flex min-w-10 justify-end">{derecha}</div>
    </div>
  )
}

// ------------------------------------------------------------------ bloques
export function Titulo({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="space-y-2">
      <h1 className="text-[28px] leading-tight font-extrabold tracking-tight text-balance @2xl:text-[34px]">{children}</h1>
      {sub && <p className="text-[15px] leading-relaxed text-suave text-pretty">{sub}</p>}
    </div>
  )
}

export function Simulado({ children = 'Simulado' }: { children?: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-aviso-suave px-2 py-0.5 text-[11px] font-semibold tracking-wide text-aviso uppercase">
      <span className="size-1.5 rounded-full bg-aviso" />{children}
    </span>
  )
}

export function MensajeError({ mensaje }: { mensaje?: string | null }) {
  return (
    <AnimatePresence>
      {mensaje && (
        <motion.div role="alert"
          initial={{ opacity: 0, y: -6, height: 0 }} animate={{ opacity: 1, y: 0, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="overflow-hidden">
          <div className="flex items-start gap-2 rounded-2xl bg-error-suave p-3 text-sm text-error">
            <AlertCircle className="mt-0.5 size-4 shrink-0" />{mensaje}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function Campo({ etiqueta, ...props }: InputHTMLAttributes<HTMLInputElement> & { etiqueta: string }) {
  const id = useId()
  return (
    <label htmlFor={id} className="block space-y-1.5">
      <span className="text-sm font-semibold text-suave">{etiqueta}</span>
      <input id={id} {...props}
        className="h-14 w-full rounded-2xl border border-borde bg-superficie px-4 text-base outline-none transition placeholder:text-tenue focus:border-marca focus:ring-4 focus:ring-marca/15" />
    </label>
  )
}

/** Tarjeta del tutor didáctico: contenido PREDEFINIDO seleccionado por regla. */
export function TarjetaTutor({ leccion, retraso = 0 }: { leccion?: Leccion | null; retraso?: number }) {
  if (!leccion) return null
  return (
    <motion.aside
      initial={{ opacity: 0, y: 16, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ delay: retraso, duration: 0.4, ease: [0.2, 0.8, 0.2, 1] }}
      className="relative overflow-hidden rounded-3xl bg-lima-suave p-4 ring-1 ring-lima">
      <div className="flex items-center gap-2">
        <span className="grid size-8 place-items-center rounded-xl bg-lima text-tinta">
          <GraduationCap className="size-4.5" />
        </span>
        <span className="text-xs font-bold tracking-wide text-marca-fuerte uppercase">Tu tutor</span>
        <span className="ml-auto rounded-full bg-white/70 px-2 py-0.5 text-[11px] font-medium text-suave">
          {leccion.id} · {leccion.nivel === 'basico' ? 'Básico' : 'Intermedio'}
        </span>
      </div>
      <h3 className="mt-3 font-bold">{leccion.titulo}</h3>
      <p className="mt-1 text-sm leading-relaxed text-tinta/80">{leccion.texto}</p>
    </motion.aside>
  )
}

/** Barra horizontal de composición del portafolio, animada. */
export function BarraComposicion({ composicion }: { composicion: Record<string, number> }) {
  const items = Object.entries(composicion)
  return (
    <div className="space-y-3">
      <div className="flex h-3 gap-1 overflow-hidden rounded-full">
        {items.map(([k, v], i) => (
          <motion.div key={k} className="h-full rounded-full"
            style={{ background: INSTRUMENTOS[k]?.color }}
            initial={{ width: 0 }} animate={{ width: `${v}%` }}
            transition={{ delay: 0.2 + i * 0.12, duration: 0.6, ease: 'easeOut' }} />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {items.map(([k, v]) => (
          <div key={k} className="flex items-center gap-1.5 text-sm">
            <span className="size-2.5 rounded-full" style={{ background: INSTRUMENTOS[k]?.color }} />
            <span className="text-suave">{INSTRUMENTOS[k]?.nombre ?? k}</span>
            <span className="cifra font-semibold">{v}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

/** Hoja inferior (bottom sheet) dentro del teléfono. */
export function Hoja({ abierta, onCerrar, titulo, children }: {
  abierta: boolean; onCerrar: () => void; titulo: string; children: ReactNode
}) {
  return (
    <AnimatePresence>
      {abierta && (
        <div className="absolute inset-0 z-40 flex flex-col justify-end @3xl:items-center @3xl:justify-center @3xl:p-8">
          <motion.div className="absolute inset-0 bg-tinta/40 backdrop-blur-[2px]" onClick={onCerrar}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.div role="dialog" aria-label={titulo}
            className="relative max-h-[85%] overflow-y-auto rounded-t-[28px] bg-superficie px-5 pt-3 pb-8 sin-scrollbar @3xl:w-full @3xl:max-w-lg @3xl:rounded-[28px] @3xl:pb-6"
            initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 320 }}>
            <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-borde" />
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold">{titulo}</h2>
              <button onClick={onCerrar} aria-label="Cerrar"
                className="grid size-9 place-items-center rounded-full bg-fondo hover:bg-borde">
                <X className="size-4.5" />
              </button>
            </div>
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

export { cx }

/** Estructura de cada pantalla: encabezado fijo, contenido con scroll y pie con la acción principal. */
export function Plantilla({ encabezado, children, pie }: {
  encabezado?: ReactNode; children: ReactNode; pie?: ReactNode
}) {
  return (
    <div className="flex h-full flex-col">
      {encabezado}
      <div className="flex-1 overflow-y-auto px-6 pb-6 sin-scrollbar @2xl:px-8">
        <div className="@2xl:mx-auto @2xl:max-w-[920px] @2xl:pt-2">{children}</div>
      </div>
      {pie && (
        <div className="shrink-0 px-6 pt-2 pb-6 @2xl:border-t @2xl:border-borde @2xl:bg-superficie/70 @2xl:px-8 @2xl:py-4">
          <div className="space-y-3 @2xl:mx-auto @2xl:flex @2xl:max-w-[920px] @2xl:flex-row-reverse @2xl:items-center @2xl:gap-4 @2xl:space-y-0 @2xl:[&>button]:w-auto @2xl:[&>button]:min-w-56 @2xl:[&>button]:px-8 @2xl:[&>div]:flex-1">
            {pie}
          </div>
        </div>
      )}
    </div>
  )
}

/** Entrada escalonada para listas y bloques. */
export const aparecer = (i = 0) => ({
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { delay: 0.05 + i * 0.07, duration: 0.35, ease: [0.2, 0.8, 0.2, 1] as const },
})
