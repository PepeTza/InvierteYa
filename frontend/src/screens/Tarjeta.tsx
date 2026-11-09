import { motion } from 'motion/react'
import { ArrowRight, Check, Lock, Nfc, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useApp } from '../estado'
import { api } from '../lib/api'
import { TARJETAS_PRUEBA } from '../lib/datos'
import { useLlamada } from '../lib/useLlamada'
import { aparecer, Boton, Encabezado, MensajeError, Plantilla, Simulado, Titulo, cx } from '../components/ui'

type Marca = 'Visa' | 'Mastercard' | 'Amex'
type Tipo = 'Crédito' | 'Débito'
const MARCAS: Marca[] = ['Visa', 'Mastercard', 'Amex']

const soloDigitos = (s: string) => s.replace(/\D/g, '')
const largoDe = (m: Marca) => (m === 'Amex' ? 15 : 16)

function detectarMarca(pan: string): Marca | null {
  if (/^3[47]/.test(pan)) return 'Amex'
  if (/^(5[1-5]|2[2-7])/.test(pan)) return 'Mastercard'
  if (/^4/.test(pan)) return 'Visa'
  return null
}

/** Agrupa el número como se imprime en la tarjeta (Amex: 4-6-5). */
function agrupar(digitos: string, marca: Marca, relleno = '') {
  const d = relleno ? digitos.padEnd(largoDe(marca), relleno) : digitos
  if (marca === 'Amex') return [d.slice(0, 4), d.slice(4, 10), d.slice(10, 15)].filter(Boolean).join(' ')
  return d.slice(0, 16).replace(/(.{4})(?=.)/g, '$1 ')
}

function formatearVence(valor: string) {
  const d = soloDigitos(valor).slice(0, 4)
  return d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d
}

function errorVence(v: string): string | null {
  const m = /^(\d{2})\/(\d{2})$/.exec(v)
  if (!m) return 'Escribe el vencimiento como MM/AA.'
  const mes = Number(m[1]), anio = 2000 + Number(m[2])
  if (mes < 1 || mes > 12) return 'El mes de vencimiento no es válido.'
  const hoy = new Date()
  if (anio < hoy.getFullYear() || (anio === hoy.getFullYear() && mes < hoy.getMonth() + 1)) return 'Esa tarjeta está vencida.'
  return null
}

function VistaTarjeta({ numero, titular, vence, marca, tipo }: {
  numero: string; titular: string; vence: string; marca: Marca; tipo: Tipo
}) {
  return (
    <motion.div {...aparecer(1)}
      className="relative aspect-[1.586] w-full overflow-hidden rounded-3xl bg-gradient-to-br from-[#1b4d3a] via-marca to-[#3aa57a] p-5 text-white shadow-[0_20px_40px_-20px_rgb(15_122_85/0.8)]">
      <div className="absolute -top-16 -right-10 size-48 rounded-full bg-lima/30 blur-2xl" />
      <div className="relative flex h-full flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="h-8 w-11 rounded-md bg-gradient-to-br from-yellow-100 to-yellow-400/80" />
          <div className="flex items-center gap-2">
            <span className="rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-semibold">{tipo}</span>
            <Nfc className="size-6 opacity-80" />
          </div>
        </div>
        <p className="cifra text-[20px] font-semibold tracking-[0.14em]">{agrupar(numero, marca, '•')}</p>
        <div className="flex items-end justify-between text-xs">
          <div><p className="opacity-60">Titular</p><p className="font-semibold uppercase">{titular || 'Nombre Apellido'}</p></div>
          <div className="text-right"><p className="opacity-60">Vence</p><p className="cifra font-semibold">{vence || 'MM/AA'}</p></div>
          <motion.p key={marca} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="text-base font-extrabold italic">
            {marca === 'Amex' ? 'AMEX' : marca}
          </motion.p>
        </div>
      </div>
    </motion.div>
  )
}

function Segmentado<T extends string>({ opciones, valor, onCambiar, etiqueta }: {
  opciones: readonly T[]; valor: T; onCambiar: (v: T) => void; etiqueta: string
}) {
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-semibold text-slate-500">{etiqueta}</p>
      <div className="flex gap-1.5" role="radiogroup" aria-label={etiqueta}>
        {opciones.map(o => (
          <button key={o} type="button" role="radio" aria-checked={valor === o} onClick={() => onCambiar(o)}
            className={cx('h-10 flex-1 rounded-xl border text-sm font-semibold transition',
              valor === o ? 'border-slate-800 bg-slate-800 text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-400')}>
            {o}
          </button>
        ))}
      </div>
    </div>
  )
}

const campo = 'h-12 w-full rounded-xl border bg-white px-3.5 outline-none transition focus:ring-4'
const campoOk = 'border-slate-200 focus:border-slate-500 focus:ring-slate-200'
const campoMal = 'border-error/60 focus:border-error focus:ring-error/15'

export default function Tarjeta() {
  const { estado, ir, actualizar } = useApp()
  const { cargando, error, setError, ejecutar } = useLlamada()
  const [numero, setNumero] = useState('')
  const [marcaManual, setMarcaManual] = useState<Marca | null>(null)
  const [tipo, setTipo] = useState<Tipo>('Crédito')
  const [vence, setVence] = useState('12/29')
  const [cvv, setCvv] = useState('123')
  const [titular, setTitular] = useState(estado.usuario?.nombre ?? '')
  const [intentado, setIntentado] = useState(false)

  const marca: Marca = marcaManual ?? detectarMarca(numero) ?? 'Visa'
  const largo = largoDe(marca)
  const largoCvv = marca === 'Amex' ? 4 : 3
  const errores = {
    numero: numero.length !== largo ? `El número de una tarjeta ${marca} tiene ${largo} dígitos.` : null,
    vence: errorVence(vence),
    cvv: cvv.length !== largoCvv ? `El CVV tiene ${largoCvv} dígitos.` : null,
    titular: titular.trim().length < 3 ? 'Escribe el nombre del titular.' : null,
  }
  const primerError = Object.values(errores).find(Boolean) ?? null

  async function guardar() {
    setIntentado(true)
    if (primerError) { setError(primerError); return }
    // El PAN va SOLO a la pasarela; InvierteYa recibe un token (alcance PCI: SAQ A).
    const r = await ejecutar(() => api.tokenizar(numero))
    if (r) actualizar({ tarjeta: { token: r.token, ultimos4: numero.slice(-4), marca, tipo } })
  }

  function cambiarNumero(v: string) {
    const d = soloDigitos(v)
    const m = marcaManual ?? detectarMarca(d) ?? 'Visa'
    setNumero(d.slice(0, largoDe(m)))
    setError(null)
  }

  if (estado.tarjeta) {
    return (
      <Plantilla encabezado={<Encabezado pasoActual={4} totalPasos={5} />}
        pie={<Boton onClick={() => ir('aporte')}>Hacer mi primer aporte <ArrowRight className="size-5" /></Boton>}>
        <div className="mx-auto flex max-w-md flex-col items-center gap-6 pt-10 text-center">
          <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 260, damping: 15 }}
            className="grid size-20 place-items-center rounded-full bg-marca text-white">
            <Check className="size-10" strokeWidth={3} />
          </motion.div>
          <motion.div {...aparecer(1)}>
            <Titulo sub={`${estado.tarjeta.marca}${estado.tarjeta.tipo ? ` de ${estado.tarjeta.tipo.toLowerCase()}` : ''} terminada en ${estado.tarjeta.ultimos4}`}>
              Tarjeta guardada
            </Titulo>
          </motion.div>
          <motion.div {...aparecer(2)} className="w-full rounded-2xl border border-dashed border-marca/40 bg-marca-suave/60 p-4 text-left">
            <p className="text-xs font-semibold text-marca-fuerte">InvierteYa solo recibió un token</p>
            <p className="mt-1 font-mono text-sm break-all">{estado.tarjeta.token}</p>
            <p className="mt-2 text-xs text-suave">El número de tu tarjeta nunca llega a nuestros servidores.</p>
          </motion.div>
        </div>
      </Plantilla>
    )
  }

  return (
    <Plantilla
      encabezado={<Encabezado onAtras={() => ir('adhesion', -1)} pasoActual={4} totalPasos={5} />}
      pie={<>
        <MensajeError mensaje={error} />
        <Boton onClick={guardar} cargando={cargando} icono={<Lock className="size-4.5" />}>Guardar tarjeta</Boton>
      </>}
    >
      <div className="space-y-5 pt-2 @3xl:grid @3xl:grid-cols-2 @3xl:items-start @3xl:gap-8 @3xl:space-y-0">
        <div className="space-y-5">
          <motion.div {...aparecer(0)}><Titulo>Agrega tu tarjeta</Titulo></motion.div>
          <VistaTarjeta numero={numero} titular={titular} vence={vence} marca={marca} tipo={tipo} />
          <motion.div {...aparecer(3)} className="space-y-2">
            <p className="text-xs font-semibold text-suave">¿Sin tarjeta a mano? Usa una de prueba</p>
            <div className="flex flex-wrap gap-2">
              {TARJETAS_PRUEBA.map(t => (
                <button key={t.pan} onClick={() => { setNumero(t.pan); setMarcaManual(null); setError(null) }}
                  className="cifra rounded-full border border-borde bg-superficie px-3 py-1.5 text-xs font-semibold transition hover:border-marca hover:text-marca">
                  {t.marca} ···· {t.pan.slice(-4)}
                </button>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Formulario alojado por la pasarela (iframe/SDK en producción) */}
        <motion.section {...aparecer(2)} className="overflow-hidden rounded-3xl border border-slate-200 bg-slate-50">
          <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2.5">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-slate-600">
              <Lock className="size-3.5" /> Pasarela aliada · pago seguro
            </span>
            <Simulado />
          </div>
          <div className="space-y-3.5 p-4">
            <Segmentado etiqueta="Tipo de tarjeta" opciones={['Crédito', 'Débito'] as const} valor={tipo} onCambiar={setTipo} />
            <Segmentado etiqueta="Marca" opciones={MARCAS} valor={marca}
              onCambiar={m => { setMarcaManual(m); setNumero(n => n.slice(0, largoDe(m))) }} />
            <input inputMode="numeric" autoComplete="cc-number" placeholder="Número de tarjeta" aria-label="Número de tarjeta"
              value={agrupar(numero, marca)} onChange={e => cambiarNumero(e.target.value)}
              className={cx(campo, 'cifra tracking-wider', intentado && errores.numero ? campoMal : campoOk)} />
            <div className="grid grid-cols-2 gap-3">
              <input placeholder="MM/AA" aria-label="Vencimiento" value={vence} inputMode="numeric"
                onChange={e => { setVence(formatearVence(e.target.value)); setError(null) }}
                className={cx(campo, 'cifra', intentado && errores.vence ? campoMal : campoOk)} />
              <input placeholder="CVV" aria-label="CVV" inputMode="numeric" value={cvv} type="password"
                onChange={e => { setCvv(soloDigitos(e.target.value).slice(0, 4)); setError(null) }}
                className={cx(campo, 'cifra', intentado && errores.cvv ? campoMal : campoOk)} />
            </div>
            <input placeholder="Titular" aria-label="Titular" value={titular} onChange={e => { setTitular(e.target.value); setError(null) }}
              className={cx(campo, intentado && errores.titular ? campoMal : campoOk)} />
            <p className="flex items-start gap-1.5 text-[11px] text-slate-500">
              <ShieldCheck className="mt-px size-3.5 shrink-0" /> Usa un número ficticio. Nunca ingreses una tarjeta real en esta demo.
            </p>
          </div>
        </motion.section>
      </div>
    </Plantilla>
  )
}
