import { motion } from 'motion/react'
import { CreditCard, Gift, Pencil } from 'lucide-react'
import { useRef, useState } from 'react'
import { useApp } from '../estado'
import { dinero, PORTAFOLIOS, unidades } from '../lib/datos'
import { aparecer, Boton, Encabezado, Plantilla, cx } from '../components/ui'

const SUGERIDOS = [5, 10, 20, 50, 100]
const MIN = 5, MAX = 1000

export default function Aporte() {
  const { estado, ir, actualizar } = useApp()
  const [texto, setTexto] = useState('20')
  const campo = useRef<HTMLInputElement>(null)
  const monto = Number(texto.replace(',', '.')) || 0
  const p = PORTAFOLIOS[estado.perfil!.perfil]
  const valido = monto >= MIN && monto <= MAX
  const esPrimero = estado.aportes.length === 0

  function invertir() {
    // Clave de idempotencia nueva por intento: si la red reintenta, el backend no cobra dos veces.
    actualizar({ enCurso: { monto, clave: crypto.randomUUID() } })
    ir('resultado')
  }

  return (
    <Plantilla
      encabezado={<Encabezado onAtras={esPrimero ? undefined : () => ir('portafolio', -1)} />}
      pie={<Boton onClick={invertir} disabled={!valido}>Invertir {valido ? dinero(monto) : ''}</Boton>}
    >
      <div className="space-y-6 pt-2 @3xl:grid @3xl:grid-cols-[1.1fr_1fr] @3xl:items-start @3xl:gap-8 @3xl:space-y-0">
        <div className="space-y-6">
          <motion.h1 {...aparecer(0)} className="text-[26px] font-extrabold tracking-tight">
            {esPrimero ? 'Tu primer aporte' : '¿Cuánto quieres invertir?'}
          </motion.h1>

          {/* Monto libre: el campo es el protagonista; los montos sugeridos son atajos */}
          <motion.div {...aparecer(1)}>
            <label htmlFor="monto" className="text-sm font-semibold text-suave">Monto a invertir</label>
            <div onClick={() => campo.current?.focus()}
              className={cx('mt-1.5 flex cursor-text items-center gap-2 rounded-3xl border-2 bg-superficie px-5 py-4 transition focus-within:ring-4',
                valido ? 'border-marca/30 focus-within:border-marca focus-within:ring-marca/15' : 'border-error/50 focus-within:ring-error/15')}>
              <span className="text-3xl font-extrabold text-tenue">$</span>
              <input id="monto" ref={campo} value={texto} inputMode="decimal" autoComplete="off"
                onChange={e => setTexto(e.target.value.replace(/[^\d.,]/g, '').slice(0, 7))}
                onFocus={e => e.target.select()}
                className="cifra w-full min-w-0 bg-transparent text-5xl font-extrabold outline-none" />
              <Pencil className="size-5 shrink-0 text-tenue" />
            </div>
            <p className={cx('mt-2 text-sm font-medium', valido ? 'text-marca' : 'text-error')}>
              {valido
                ? <>≈ <span className="cifra">{unidades(monto / p.valorUnidad)}</span> unidades del portafolio {p.nombre}</>
                : `Escribe un monto entre ${dinero(MIN)} y ${dinero(MAX)}`}
            </p>
          </motion.div>

          <motion.div {...aparecer(2)} className="space-y-2">
            <p className="text-xs font-semibold text-suave">Sugeridos</p>
            <div className="flex flex-wrap gap-2">
              {SUGERIDOS.map(v => (
                <motion.button key={v} whileTap={{ scale: 0.95 }} onClick={() => setTexto(String(v))}
                  className={cx('h-10 rounded-full px-4 text-sm font-bold transition-colors',
                    monto === v ? 'bg-tinta text-white' : 'bg-superficie shadow-tarjeta hover:bg-marca-suave')}>
                  ${v}
                </motion.button>
              ))}
            </div>
          </motion.div>
        </div>

        <motion.div {...aparecer(3)} className="divide-y divide-borde rounded-3xl bg-superficie shadow-tarjeta @3xl:mt-14">
          <div className="flex items-center justify-between p-4">
            <span className="text-sm text-suave">Portafolio</span>
            <span className="text-sm font-bold">{p.nombre}</span>
          </div>
          <div className="flex items-center justify-between p-4">
            <span className="text-sm text-suave">Valor de la unidad</span>
            <span className="cifra text-sm font-bold">{dinero(p.valorUnidad)}</span>
          </div>
          <div className="flex items-center gap-3 p-4">
            <span className="grid size-10 place-items-center rounded-xl bg-fondo"><CreditCard className="size-5 text-suave" /></span>
            <div className="flex-1">
              <p className="text-sm font-semibold">{estado.tarjeta?.marca} ···· {estado.tarjeta?.ultimos4}</p>
              <p className="text-xs text-suave">{estado.tarjeta?.tipo ? `${estado.tarjeta.tipo} · ` : ''}tokenizada por la pasarela</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-4">
            <span className="grid size-10 place-items-center rounded-xl bg-lima-suave"><Gift className="size-5 text-marca" /></span>
            <div className="flex-1">
              <p className="text-sm font-semibold">Comisión de la pasarela cubierta</p>
              <p className="text-xs text-suave">Al fideicomiso llega el 100% de tu aporte</p>
            </div>
          </div>
        </motion.div>
      </div>
    </Plantilla>
  )
}
