import { motion } from 'motion/react'
import { ArrowDownLeft, ArrowUpRight } from 'lucide-react'
import type { MensajeIso } from '../lib/api'
import { CAMPOS_ISO, MTI } from '../lib/datos'
import { cx } from './ui'

/** Muestra los mensajes ISO 8583 (SIMULADOS) del tramo pasarela ↔ adquirente ↔ suiche ↔ emisor. */
export default function VisorIso({ mensajes }: { mensajes: MensajeIso[] }) {
  return (
    <div className="space-y-3">
      {mensajes.map((m, i) => {
        const respuesta = Number(m.mti[2]) % 2 === 1 // x1x0: el tercer dígito impar es respuesta
        const codigo = m.campos['39']
        return (
          <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
            className="overflow-hidden rounded-2xl border border-borde">
            <div className="flex items-center gap-2 bg-fondo px-3 py-2">
              {respuesta
                ? <ArrowDownLeft className="size-4 text-marca" />
                : <ArrowUpRight className="size-4 text-conservador" />}
              <span className="rounded-md bg-tinta px-1.5 py-0.5 font-mono text-xs font-bold text-white">{m.mti}</span>
              <span className="truncate text-xs font-semibold">{MTI[m.mti] ?? 'Mensaje'}</span>
              {codigo && (
                <span className={cx('ml-auto rounded-md px-1.5 py-0.5 font-mono text-xs font-bold',
                  codigo === '00' ? 'bg-marca-suave text-marca' : 'bg-error-suave text-error')}>
                  {codigo}
                </span>
              )}
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 px-3 py-2 text-xs">
              {Object.entries(m.campos).map(([campo, valor]) => (
                <div key={campo} className="contents">
                  <dt className="text-suave"><span className="cifra font-mono font-semibold text-tinta">{campo.padStart(3, '0')}</span> {CAMPOS_ISO[campo] ?? ''}</dt>
                  <dd className="truncate text-right font-mono">{valor}</dd>
                </div>
              ))}
            </dl>
          </motion.div>
        )
      })}
      <p className="text-center text-[11px] text-suave">Mensajes ISO 8583 simulados · tramo pasarela → suiche → emisor</p>
    </div>
  )
}
