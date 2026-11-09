import { animate, motion, useMotionValue, useTransform } from 'motion/react'
import { AlertTriangle, BrainCircuit, Cpu, TrendingDown, TrendingUp, UserCheck } from 'lucide-react'
import { useEffect } from 'react'
import { useApp } from '../estado'
import type { Perfil as TPerfil } from '../lib/api'
import { dinero, PORTAFOLIOS } from '../lib/datos'
import { aparecer, BarraComposicion, Boton, Encabezado, Plantilla, TarjetaTutor } from '../components/ui'

/** Medidor semicircular del puntaje (0 a 19) con las zonas de cada perfil. */
function Medidor({ puntaje, maximo, color }: { puntaje: number; maximo: number; color: string }) {
  const valor = useMotionValue(0)
  const angulo = useTransform(valor, v => -90 + (v / maximo) * 180)
  const texto = useTransform(valor, v => v.toFixed(1).replace('.', ','))
  useEffect(() => {
    const c = animate(valor, puntaje, { duration: 1.1, ease: [0.2, 0.8, 0.2, 1], delay: 0.3 })
    return c.stop
  }, [puntaje, valor])

  const arco = (desde: number, hasta: number) => {
    const p = (v: number) => {
      const a = Math.PI - (v / maximo) * Math.PI
      return [100 + 80 * Math.cos(a), 100 - 80 * Math.sin(a)]
    }
    const [x1, y1] = p(desde), [x2, y2] = p(hasta)
    return `M ${x1} ${y1} A 80 80 0 0 1 ${x2} ${y2}`
  }
  // Umbrales de app/core/perfil.py: < 7 Conservador, < 13 Moderado, resto Agresivo
  const zonas = [[0, 6.8, 'var(--color-conservador)'], [7.2, 12.8, 'var(--color-moderado)'], [13.2, maximo, 'var(--color-agresivo)']] as const

  return (
    <div className="relative mx-auto w-56">
      <svg viewBox="0 0 200 112" className="w-full">
        {zonas.map(([d, h, c]) => (
          <path key={c} d={arco(d, h)} fill="none" stroke={c} strokeOpacity={0.22} strokeWidth="14" strokeLinecap="round" />
        ))}
        <motion.g style={{ rotate: angulo, originX: 0.5, originY: 1 }}>
          <line x1="100" y1="100" x2="100" y2="34" stroke={color} strokeWidth="5" strokeLinecap="round" />
        </motion.g>
        <circle cx="100" cy="100" r="9" fill={color} />
        <circle cx="100" cy="100" r="4" fill="white" />
      </svg>
      <p className="mt-1 text-center text-sm text-suave">
        Puntaje <motion.span className="cifra font-bold text-tinta">{texto}</motion.span> de {maximo}
      </p>
    </div>
  )
}

const UMBRAL_REVISION = 0.6
const pct = (v: number) => `${Math.round(v * 100)}%`

/** Confianza del modelo de IA: probabilidad de cada perfil frente al umbral de revisión humana (60%). */
function ConfianzaModelo({ probabilidades, asignado, revision }: {
  probabilidades: Record<TPerfil, number>; asignado: TPerfil; revision: boolean
}) {
  const orden: TPerfil[] = ['CONSERVADOR', 'MODERADO', 'AGRESIVO']
  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <p className="flex items-center gap-1.5 text-sm font-semibold"><BrainCircuit className="size-4 text-marca" /> Confianza del modelo</p>
        <p className="cifra text-2xl font-extrabold">{pct(probabilidades[asignado] ?? 0)}</p>
      </div>
      <ul className="space-y-2">
        {orden.map((k, i) => {
          const v = probabilidades[k] ?? 0
          return (
            <li key={k} className="grid grid-cols-[88px_1fr_40px] items-center gap-2 text-xs" title={`${PORTAFOLIOS[k].nombre}: ${pct(v)}`}>
              <span className={k === asignado ? 'font-bold' : 'text-suave'}>{PORTAFOLIOS[k].nombre}</span>
              <span className="relative h-2.5 rounded-full bg-fondo">
                <motion.span className="absolute inset-y-0 left-0 rounded-full"
                  style={{ background: PORTAFOLIOS[k].color, opacity: k === asignado ? 1 : 0.45 }}
                  initial={{ width: 0 }} animate={{ width: `${Math.max(v * 100, 1)}%` }}
                  transition={{ delay: 0.3 + i * 0.1, duration: 0.6, ease: 'easeOut' }} />
                <span className="absolute -inset-y-1 w-px bg-tinta/40" style={{ left: `${UMBRAL_REVISION * 100}%` }} />
              </span>
              <span className="cifra text-right font-semibold">{pct(v)}</span>
            </li>
          )
        })}
      </ul>
      <p className="text-[11px] text-suave">La línea marca el 60%: por debajo, un asesor revisa el perfil.</p>
      {revision && (
        <p className="flex items-center gap-1.5 rounded-xl bg-conservador-suave px-3 py-2 text-xs font-semibold text-conservador">
          <UserCheck className="size-4" /> Un asesor revisará tu perfil
        </p>
      )}
    </div>
  )
}

/** Por qué se asignó el perfil, en viñetas cortas. */
function Factores({ suben, moderan, explicacion }: { suben: string[]; moderan: string[]; explicacion: string }) {
  if (!suben.length && !moderan.length) {
    return <p className="rounded-2xl bg-superficie p-4 text-[15px] shadow-tarjeta">{explicacion}</p>
  }
  const grupos = [
    { titulo: 'Suben tu tolerancia', items: suben, icono: TrendingUp, clase: 'bg-marca-suave text-marca' },
    { titulo: 'La moderan', items: moderan, icono: TrendingDown, clase: 'bg-aviso-suave text-aviso' },
  ].filter(g => g.items.length)
  return (
    <motion.section {...aparecer(4)} className="space-y-4 rounded-3xl bg-superficie p-5 shadow-tarjeta">
      <h2 className="font-bold">¿Por qué este perfil?</h2>
      {grupos.map(({ titulo, items, icono: Icono, clase }) => (
        <div key={titulo} className="space-y-2">
          <p className="text-xs font-bold tracking-wide text-suave uppercase">{titulo}</p>
          <ul className="space-y-2">
            {items.map(t => (
              <li key={t} className="flex items-center gap-2.5 text-[15px]">
                <span className={`grid size-7 shrink-0 place-items-center rounded-lg ${clase}`}><Icono className="size-4" /></span>
                {t}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </motion.section>
  )
}

export default function Perfil() {
  const { estado, ir } = useApp()
  const r = estado.perfil!
  const p = PORTAFOLIOS[r.perfil]
  const Icono = p.icono
  const motor = r.probabilidades ? 'Modelo de IA · regresión logística · datos sintéticos' : 'Motor de reglas de idoneidad (sin modelo)'

  return (
    <Plantilla
      encabezado={<Encabezado pasoActual={2} totalPasos={5} />}
      pie={<Boton onClick={() => ir('adhesion')}>Continuar</Boton>}
    >
      <div className="space-y-6 pt-2 @3xl:grid @3xl:grid-cols-[0.9fr_1.1fr] @3xl:items-start @3xl:gap-8 @3xl:space-y-0">
        {/* Columna 1: resultado */}
        <div className="space-y-6 @3xl:sticky @3xl:top-0 @3xl:rounded-3xl @3xl:bg-superficie @3xl:p-6 @3xl:shadow-tarjeta">
          <div className="text-center">
            <motion.div initial={{ scale: 0, rotate: -20 }} animate={{ scale: 1, rotate: 0 }}
              transition={{ type: 'spring', stiffness: 260, damping: 16 }}
              className="mx-auto grid size-16 place-items-center rounded-3xl"
              style={{ background: p.suave, color: p.color }}>
              <Icono className="size-8" />
            </motion.div>
            <motion.p {...aparecer(1)} className="mt-4 text-sm font-semibold text-suave">Tu perfil es</motion.p>
            <motion.h1 {...aparecer(2)} className="text-4xl font-extrabold tracking-tight" style={{ color: p.color }}>
              {p.nombre}
            </motion.h1>
            <motion.p {...aparecer(3)} className="text-sm font-medium text-suave">{p.lema}</motion.p>
          </div>
          <motion.div {...aparecer(3)}>
            {r.probabilidades
              ? <ConfianzaModelo probabilidades={r.probabilidades} asignado={r.perfil} revision={Boolean(r.revision_humana)} />
              : <Medidor puntaje={r.puntaje} maximo={r.puntaje_maximo} color={p.color} />}
          </motion.div>
          <p className="hidden items-center justify-center gap-1.5 text-xs text-suave @3xl:flex">
            <Cpu className="size-3.5" /> {motor}
          </p>
        </div>

        {/* Columna 2: por qué + portafolio + tutor */}
        <div className="space-y-6">
          <Factores suben={r.factores_suben ?? []} moderan={r.factores_moderan ?? []} explicacion={r.explicacion} />

          {r.avisos.map(a => (
            <motion.div key={a} {...aparecer(5)} className="flex gap-2 rounded-2xl bg-aviso-suave p-3 text-sm text-aviso">
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />{a}
            </motion.div>
          ))}

          <motion.section {...aparecer(5)} className="space-y-4 rounded-3xl bg-superficie p-5 shadow-tarjeta">
            <div className="flex items-baseline justify-between">
              <h2 className="font-bold">Portafolio {p.nombre}</h2>
              <span className="text-sm text-suave">Unidad: <b className="cifra text-tinta">{dinero(p.valorUnidad)}</b></span>
            </div>
            <BarraComposicion composicion={p.composicion} />
          </motion.section>

          <TarjetaTutor leccion={r.leccion} retraso={0.6} />

          <p className="flex items-center justify-center gap-1.5 text-xs text-suave @3xl:hidden">
            <Cpu className="size-3.5" /> {motor}
          </p>
        </div>
      </div>
    </Plantilla>
  )
}
