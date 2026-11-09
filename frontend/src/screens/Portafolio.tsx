import { animate, motion, useMotionValue, useTransform } from 'motion/react'
import {
  ArrowDownToLine, CheckCircle2, Clock, Coins, Hash, Landmark, Layers, Plus, Undo2, Wallet, XCircle,
  type LucideIcon,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { useApp } from '../estado'
import { api, type Aporte, type EstadoAporte, type Leccion, type Portafolio as TPortafolio } from '../lib/api'
import { dinero, INSTRUMENTOS, PORTAFOLIOS, unidades } from '../lib/datos'
import { useLlamada } from '../lib/useLlamada'
import { aparecer, Boton, Hoja, Isotipo, MensajeError, TarjetaTutor, cx } from '../components/ui'

const ESTADOS: Partial<Record<EstadoAporte, { texto: string; icono: LucideIcon; clase: string; fondo: string }>> = {
  ASIGNADO: { texto: 'Invertido', icono: CheckCircle2, clase: 'text-marca', fondo: 'bg-marca-suave' },
  RECHAZADO: { texto: 'Rechazado', icono: XCircle, clase: 'text-error', fondo: 'bg-error-suave' },
  REVERSADO: { texto: 'Reversado', icono: Undo2, clase: 'text-aviso', fondo: 'bg-aviso-suave' },
  REVERSO_PENDIENTE: { texto: 'En revisión', icono: Clock, clase: 'text-aviso', fondo: 'bg-aviso-suave' },
}
const hora = new Intl.DateTimeFormat('es-VE', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

function Animado({ valor, formato }: { valor: number; formato: (n: number) => string }) {
  const mv = useMotionValue(0)
  const texto = useTransform(mv, formato)
  useEffect(() => animate(mv, valor, { duration: 1, ease: [0.2, 0.8, 0.2, 1] }).stop, [valor, mv])
  return <motion.span className="cifra">{texto}</motion.span>
}

function EstadoChip({ estado }: { estado: EstadoAporte }) {
  const e = ESTADOS[estado]
  const Icono = e?.icono ?? Clock
  return (
    <span className={cx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold', e?.clase ?? 'text-suave', e?.fondo ?? 'bg-fondo')}>
      <Icono className="size-3.5" />{e?.texto ?? estado}
    </span>
  )
}

/** Indicador del tablero (web). */
function Indicador({ icono: Icono, etiqueta, children, i }: { icono: LucideIcon; etiqueta: string; children: ReactNode; i: number }) {
  return (
    <motion.div {...aparecer(i)} className="rounded-3xl bg-superficie p-5 shadow-tarjeta">
      <div className="flex items-center gap-2 text-sm text-suave">
        <span className="grid size-8 place-items-center rounded-xl bg-fondo text-marca"><Icono className="size-4" /></span>
        {etiqueta}
      </div>
      <p className="mt-3 text-2xl font-extrabold tracking-tight">{children}</p>
    </motion.div>
  )
}

/** Composición: barra segmentada + tabla con % y monto (parte de un todo, con etiquetas visibles). */
function Composicion({ composicion, saldo }: { composicion: Record<string, number>; saldo: number }) {
  const items = Object.entries(composicion)
  return (
    <div className="space-y-4">
      <div className="flex h-4 gap-[2px] overflow-hidden rounded-full" role="img"
        aria-label={items.map(([k, v]) => `${INSTRUMENTOS[k]?.nombre} ${v}%`).join(', ')}>
        {items.map(([k, v], i) => (
          <motion.div key={k} title={`${INSTRUMENTOS[k]?.nombre}: ${v}% · ${dinero((saldo * v) / 100)}`}
            className="h-full transition-opacity first:rounded-l-full last:rounded-r-full hover:opacity-80"
            style={{ background: INSTRUMENTOS[k]?.color }}
            initial={{ width: 0 }} animate={{ width: `${v}%` }}
            transition={{ delay: 0.2 + i * 0.12, duration: 0.6, ease: 'easeOut' }} />
        ))}
      </div>
      <table className="w-full text-sm">
        <thead className="sr-only"><tr><th>Instrumento</th><th>Porcentaje</th><th>Monto</th></tr></thead>
        <tbody className="divide-y divide-borde">
          {items.map(([k, v]) => (
            <tr key={k}>
              <td className="py-2.5">
                <span className="flex items-center gap-2">
                  <span className="size-2.5 rounded-full" style={{ background: INSTRUMENTOS[k]?.color }} />
                  {INSTRUMENTOS[k]?.nombre ?? k}
                </span>
              </td>
              <td className="cifra py-2.5 text-right text-suave">{v}%</td>
              <td className="cifra w-28 py-2.5 text-right font-semibold">{dinero((saldo * v) / 100)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ListaActividad({ aportes }: { aportes: Aporte[] }) {
  return (
    <ul className="divide-y divide-borde">
      {aportes.map(a => (
        <li key={a.id} className="flex items-center gap-3 py-3">
          <div className="flex-1 space-y-1">
            <p className="text-sm font-semibold">Aporte</p>
            <EstadoChip estado={a.estado} />
          </div>
          <div className="text-right">
            <p className={cx('cifra text-sm font-bold', a.estado !== 'ASIGNADO' && 'text-suave line-through')}>{dinero(a.monto)}</p>
            {a.unidades && <p className="cifra text-xs text-suave">+{unidades(a.unidades)} u.</p>}
          </div>
        </li>
      ))}
    </ul>
  )
}

function TablaActividad({ aportes }: { aportes: Aporte[] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-borde text-left text-xs text-suave">
          <th className="pb-2.5 font-semibold">Fecha</th>
          <th className="pb-2.5 font-semibold">Estado</th>
          <th className="pb-2.5 text-right font-semibold">Monto</th>
          <th className="pb-2.5 text-right font-semibold">Unidades</th>
          <th className="pb-2.5 text-right font-semibold">Referencia (RRN)</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-borde">
        {aportes.map(a => (
          <tr key={a.id}>
            <td className="py-3 text-suave">{a.registrado ? hora.format(a.registrado) : '—'}</td>
            <td className="py-3"><EstadoChip estado={a.estado} /></td>
            <td className={cx('cifra py-3 text-right font-semibold', a.estado !== 'ASIGNADO' && 'text-suave line-through')}>{dinero(a.monto)}</td>
            <td className="cifra py-3 text-right">{a.unidades ? unidades(a.unidades) : '—'}</td>
            <td className="py-3 text-right font-mono text-xs text-suave">{a.rrn ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function Portafolio() {
  const { estado, ir } = useApp()
  const { error, ejecutar } = useLlamada()
  const [datos, setDatos] = useState<TPortafolio | null>(null)
  const [leccion, setLeccion] = useState<Leccion | null>(null)
  const [rescate, setRescate] = useState<Leccion | null | undefined>(undefined)
  const perfil = estado.perfil!.perfil
  const p = PORTAFOLIOS[perfil]
  const nombre = estado.usuario?.nombre.split(' ')[0] ?? ''
  const saldo = datos ? Number(datos.saldo) : 0

  useEffect(() => {
    ejecutar(() => api.portafolio(estado.usuario!.usuario_id)).then(d => {
      if (!d) return
      setDatos(d)
      if (d.leccion) setLeccion(d.leccion)
    })
  }, [ejecutar, estado.usuario])

  async function abrirRescate() {
    const l = await ejecutar(() => api.leccion('ANTES_RESCATE', perfil, estado.respuestas.conocimiento ?? 1))
    setRescate(l ?? null)
  }

  const chipPerfil = (
    <span className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-bold" style={{ background: p.suave, color: p.color }}>
      <p.icono className="size-3.5" />{p.nombre}
    </span>
  )
  const custodia = (
    <p className="flex items-center gap-2 rounded-2xl bg-fondo px-3 py-2.5 text-xs text-suave">
      <Landmark className="size-4 shrink-0 text-marca" /> Custodiado por el fideicomiso en el banco fiduciario
    </p>
  )

  return (
    <div className="relative h-full">
      {/* ============================ WEB: tablero ============================ */}
      <div className="hidden h-full overflow-y-auto sin-scrollbar @3xl:block">
        <div className="mx-auto max-w-[1120px] space-y-6 px-10 py-8">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-sm text-suave">Resumen de tu inversión</p>
              <h1 className="text-3xl font-extrabold tracking-tight">Hola, {nombre}</h1>
            </div>
            <div className="flex items-center gap-3">
              {chipPerfil}
              <button onClick={abrirRescate}
                className="flex h-11 items-center gap-1.5 rounded-full border border-borde bg-superficie px-5 text-sm font-semibold transition hover:border-marca/40">
                <ArrowDownToLine className="size-4" /> Retirar
              </button>
              <button onClick={() => ir('aporte')}
                className="flex h-11 items-center gap-1.5 rounded-full bg-marca px-5 text-sm font-semibold text-white transition hover:bg-marca-fuerte">
                <Plus className="size-4" /> Aportar
              </button>
            </div>
          </div>

          <MensajeError mensaje={error} />

          {/* Fila de indicadores */}
          <div className="grid grid-cols-4 gap-4">
            <motion.div {...aparecer(0)}
              className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-marca to-marca-fuerte p-5 text-white">
              <div className="absolute -top-12 -right-10 size-36 rounded-full bg-lima/25 blur-2xl" />
              <div className="relative flex items-center gap-2 text-sm text-white/75">
                <span className="grid size-8 place-items-center rounded-xl bg-white/15"><Wallet className="size-4" /></span>
                Saldo invertido
              </div>
              <p className="relative mt-3 text-2xl font-extrabold tracking-tight">
                {datos ? <Animado valor={saldo} formato={dinero} /> : '$—'}
              </p>
            </motion.div>
            <Indicador i={1} icono={Layers} etiqueta="Unidades">{datos ? <span className="cifra">{unidades(datos.unidades)}</span> : '—'}</Indicador>
            <Indicador i={2} icono={Coins} etiqueta="Valor de la unidad">{datos ? <span className="cifra">{dinero(datos.valor_unidad)}</span> : '—'}</Indicador>
            <Indicador i={3} icono={Hash} etiqueta="Aportes confirmados">{datos ? <span className="cifra">{datos.aportes}</span> : '—'}</Indicador>
          </div>

          <div className="grid grid-cols-3 items-start gap-6">
            <motion.section {...aparecer(4)} className="col-span-2 space-y-4 rounded-3xl bg-superficie p-6 shadow-tarjeta">
              <div className="flex items-baseline justify-between">
                <h2 className="text-lg font-bold">¿En qué está tu dinero?</h2>
                <span className="text-sm text-suave">Portafolio {p.nombre}</span>
              </div>
              <Composicion composicion={p.composicion} saldo={saldo} />
              {custodia}
            </motion.section>

            <div className="space-y-6">
              <motion.section {...aparecer(5)} className="rounded-3xl bg-superficie p-6 shadow-tarjeta">
                <p className="text-sm text-suave">Tu perfil</p>
                <div className="mt-2 flex items-center gap-3">
                  <span className="grid size-11 place-items-center rounded-2xl" style={{ background: p.suave, color: p.color }}>
                    <p.icono className="size-5" />
                  </span>
                  <div>
                    <p className="text-lg font-bold">{p.nombre}</p>
                    <p className="text-sm text-suave">{p.lema}</p>
                  </div>
                </div>
              </motion.section>
              <TarjetaTutor leccion={leccion} retraso={0.4} />
            </div>
          </div>

          <motion.section {...aparecer(6)} className="rounded-3xl bg-superficie p-6 shadow-tarjeta">
            <h2 className="mb-4 text-lg font-bold">Actividad</h2>
            {estado.aportes.length
              ? <TablaActividad aportes={estado.aportes} />
              : <p className="py-6 text-center text-sm text-suave">Aún no tienes aportes.</p>}
          </motion.section>
        </div>
      </div>

      {/* ============================ MÓVIL ============================ */}
      <div className="flex h-full flex-col @3xl:hidden">
        <div className="flex-1 overflow-y-auto pb-28 sin-scrollbar">
          <div className="flex items-center justify-between px-6 pt-5">
            <div className="flex items-center gap-3">
              <Isotipo className="size-9" />
              <div>
                <p className="text-xs text-suave">Hola,</p>
                <p className="-mt-0.5 font-bold">{nombre}</p>
              </div>
            </div>
            {chipPerfil}
          </div>

          <motion.section {...aparecer(0)}
            className="relative mx-4 mt-5 overflow-hidden rounded-[28px] bg-gradient-to-br from-marca to-marca-fuerte p-6 text-white">
            <div className="absolute -top-20 -right-16 size-56 rounded-full bg-lima/25 blur-3xl" />
            <div className="relative">
              <p className="text-sm text-white/70">Saldo invertido</p>
              <p className="mt-1 text-[40px] leading-none font-extrabold tracking-tight">
                {datos ? <Animado valor={saldo} formato={dinero} /> : <span className="opacity-40">$—</span>}
              </p>
              <div className="mt-4 flex gap-5 text-sm">
                <div><p className="text-white/60">Unidades</p><p className="cifra font-bold">{datos ? unidades(datos.unidades) : '—'}</p></div>
                <div><p className="text-white/60">Valor unidad</p><p className="cifra font-bold">{datos ? dinero(datos.valor_unidad) : '—'}</p></div>
                <div><p className="text-white/60">Aportes</p><p className="cifra font-bold">{datos?.aportes ?? '—'}</p></div>
              </div>
            </div>
          </motion.section>

          <div className="space-y-5 px-4 pt-5">
            <MensajeError mensaje={error} />
            <TarjetaTutor leccion={leccion} retraso={0.5} />
            <motion.section {...aparecer(2)} className="space-y-4 rounded-3xl bg-superficie p-5 shadow-tarjeta">
              <h2 className="font-bold">¿En qué está tu dinero?</h2>
              <Composicion composicion={p.composicion} saldo={saldo} />
              {custodia}
            </motion.section>
            {estado.aportes.length > 0 && (
              <motion.section {...aparecer(3)} className="rounded-3xl bg-superficie p-5 shadow-tarjeta">
                <h2 className="mb-1 font-bold">Actividad</h2>
                <ListaActividad aportes={estado.aportes} />
              </motion.section>
            )}
          </div>
        </div>

        <div className="absolute inset-x-0 bottom-0 flex gap-3 bg-gradient-to-t from-fondo via-fondo to-transparent px-4 pt-6 pb-6">
          <Boton variante="secundario" className="flex-1" onClick={abrirRescate} icono={<ArrowDownToLine className="size-5" />}>Retirar</Boton>
          <Boton className="flex-[1.4]" onClick={() => ir('aporte')} icono={<Plus className="size-5" />}>Aportar</Boton>
        </div>
      </div>

      <Hoja abierta={rescate !== undefined} onCerrar={() => setRescate(undefined)} titulo="Retirar dinero">
        <div className="space-y-4">
          <TarjetaTutor leccion={rescate} />
          <p className="rounded-2xl bg-fondo p-4 text-sm text-suave">El rescate de unidades llega en la próxima versión (MVP · Sesión 3).</p>
          <Boton variante="secundario" onClick={() => setRescate(undefined)}>Entendido</Boton>
        </div>
      </Hoja>
    </div>
  )
}
