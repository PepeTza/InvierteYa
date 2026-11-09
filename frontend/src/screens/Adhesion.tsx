import { AnimatePresence, motion } from 'motion/react'
import { Check, ChevronDown, Coins, FileSignature, Landmark, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useApp } from '../estado'
import { api } from '../lib/api'
import { useLlamada } from '../lib/useLlamada'
import { aparecer, Boton, Encabezado, MensajeError, Plantilla, Simulado, TarjetaTutor, Titulo, cx } from '../components/ui'

const PUNTOS = [
  { icono: Landmark, titulo: 'Lo administra un banco', texto: 'Banco fiduciario regulado por SUDEBAN.' },
  { icono: ShieldCheck, titulo: 'Tu dinero está aparte', texto: 'Patrimonio separado del banco y de InvierteYa.' },
  { icono: Coins, titulo: 'Recibes unidades', texto: 'Cada aporte se convierte en unidades de participación.' },
]

const CLAUSULAS = [
  'El Usuario se adhiere como fideicomitente y beneficiario del Fideicomiso de Inversión InvierteYa.',
  'El Banco Fiduciario administra el patrimonio autónomo según la política de inversión del portafolio asignado.',
  'InvierteYa propone las órdenes de inversión por lote; el Fiduciario las aprueba antes de ejecutarlas.',
  'El retiro se realiza mediante el rescate de unidades al valor del día.',
  'El Usuario autoriza compartir el resultado de su verificación de identidad con el Fiduciario (prevención LC/FT).',
]

export default function Adhesion() {
  const { estado, ir, actualizar } = useApp()
  const { cargando, error, ejecutar } = useLlamada()
  const [acepta, setAcepta] = useState(false)
  const [verContrato, setVerContrato] = useState(false)
  const firmado = estado.usuario?.adhesion_firmada

  async function firmar() {
    const r = await ejecutar(() => api.adhesion(estado.usuario!.usuario_id))
    if (r) actualizar({ usuario: { ...estado.usuario!, adhesion_firmada: true }, leccionAdhesion: r.leccion })
  }

  if (firmado) {
    return (
      <Plantilla encabezado={<Encabezado pasoActual={3} totalPasos={5} />}
        pie={<Boton onClick={() => ir('tarjeta')}>Agregar método de pago</Boton>}>
        <div className="flex flex-col items-center gap-6 pt-8 text-center">
          <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 260, damping: 15 }}
            className="grid size-20 place-items-center rounded-full bg-marca text-white shadow-[0_12px_30px_-10px_rgb(15_122_85/0.7)]">
            <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.2 }}>
              <Check className="size-10" strokeWidth={3} />
            </motion.span>
          </motion.div>
          <motion.div {...aparecer(1)}>
            <Titulo sub="Ya eres parte del fideicomiso.">¡Contrato firmado!</Titulo>
          </motion.div>
          <div className="w-full text-left"><TarjetaTutor leccion={estado.leccionAdhesion} retraso={0.4} /></div>
        </div>
      </Plantilla>
    )
  }

  return (
    <Plantilla
      encabezado={<Encabezado onAtras={() => ir('perfil', -1)} pasoActual={3} totalPasos={5} />}
      pie={<>
        <MensajeError mensaje={error} />
        <Boton onClick={firmar} disabled={!acepta} cargando={cargando} icono={<FileSignature className="size-5" />}>
          Firmar contrato
        </Boton>
      </>}
    >
      <div className="space-y-6 pt-4">
        <motion.div {...aparecer(0)}>
          <Titulo sub="Así funciona donde vive tu inversión.">Únete al fideicomiso</Titulo>
        </motion.div>

        <ul className="space-y-3 @3xl:grid @3xl:grid-cols-3 @3xl:gap-4 @3xl:space-y-0">
          {PUNTOS.map(({ icono: Icono, titulo, texto }, i) => (
            <motion.li key={titulo} {...aparecer(i + 1)} className="flex gap-3.5">
              <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-marca-suave text-marca">
                <Icono className="size-5" />
              </span>
              <div>
                <p className="font-semibold">{titulo}</p>
                <p className="text-sm text-suave">{texto}</p>
              </div>
            </motion.li>
          ))}
        </ul>

        <motion.div {...aparecer(4)} className="overflow-hidden rounded-2xl border border-borde bg-superficie">
          <button onClick={() => setVerContrato(v => !v)} aria-expanded={verContrato}
            className="flex w-full items-center justify-between p-4 text-left text-sm font-semibold">
            <span className="flex items-center gap-2">Contrato de adhesión <Simulado>Sintético</Simulado></span>
            <motion.span animate={{ rotate: verContrato ? 180 : 0 }}><ChevronDown className="size-5 text-suave" /></motion.span>
          </button>
          <AnimatePresence initial={false}>
            {verContrato && (
              <motion.ol initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }}
                className="list-decimal space-y-2 overflow-hidden pr-4 pl-9 text-[13px] leading-relaxed text-suave">
                {CLAUSULAS.map(c => <li key={c}>{c}</li>)}
                <li className="list-none pb-4" />
              </motion.ol>
            )}
          </AnimatePresence>
        </motion.div>

        <motion.label {...aparecer(5)} className="flex cursor-pointer items-start gap-3">
          <input type="checkbox" className="peer sr-only" checked={acepta} onChange={e => setAcepta(e.target.checked)} />
          <span className={cx('mt-0.5 grid size-6 shrink-0 place-items-center rounded-lg border-2 transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-marca',
            acepta ? 'border-marca bg-marca text-white' : 'border-borde bg-superficie')}>
            {acepta && <Check className="size-4" strokeWidth={3} />}
          </span>
          <span className="text-sm">Leí y acepto el contrato de adhesión al fideicomiso.</span>
        </motion.label>
      </div>
    </Plantilla>
  )
}
