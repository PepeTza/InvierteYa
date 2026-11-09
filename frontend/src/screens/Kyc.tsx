import { motion } from 'motion/react'
import { Check, IdCard, ScanFace } from 'lucide-react'
import { useState } from 'react'
import { useApp } from '../estado'
import { api } from '../lib/api'
import { useLlamada } from '../lib/useLlamada'
import { aparecer, Boton, Encabezado, MensajeError, Plantilla, Simulado, Titulo, cx } from '../components/ui'

const PASOS = [
  { icono: IdCard, titulo: 'Foto de tu cédula', detalle: 'Frente y reverso' },
  { icono: ScanFace, titulo: 'Selfie', detalle: 'Para confirmar que eres tú' },
]

export default function Kyc() {
  const { estado, ir } = useApp()
  const { error, ejecutar } = useLlamada()
  // -1: sin empezar · 0..1: escaneando paso i · 2: aprobado
  const [fase, setFase] = useState(-1)

  async function verificar() {
    for (let i = 0; i < PASOS.length; i++) {
      setFase(i)
      await new Promise(r => setTimeout(r, 1100))
    }
    const ok = await ejecutar(() => api.kyc(estado.usuario!.usuario_id))
    if (!ok) { setFase(-1); return }
    setFase(2)
    setTimeout(() => ir('cuestionario'), 900)
  }

  return (
    <Plantilla
      encabezado={<Encabezado onAtras={() => ir('registro', -1)} pasoActual={1} totalPasos={5} derecha={<Simulado />} />}
      pie={<Boton onClick={verificar} cargando={fase >= 0 && fase < 2} disabled={fase === 2}>
        {fase === 2 ? 'Identidad verificada' : 'Verificar identidad'}
      </Boton>}
    >
      <div className="space-y-8 pt-4">
        <motion.div {...aparecer(0)}>
          <Titulo sub="Lo exige la ley para proteger tu dinero. Toma menos de un minuto.">Verifica tu identidad</Titulo>
        </motion.div>
        <div className="space-y-3 @2xl:grid @2xl:grid-cols-2 @2xl:gap-4 @2xl:space-y-0">
          {PASOS.map(({ icono: Icono, titulo, detalle }, i) => {
            const listo = fase > i
            const activo = fase === i
            return (
              <motion.div key={titulo} {...aparecer(i + 1)}
                className={cx('relative flex items-center gap-4 overflow-hidden rounded-3xl border bg-superficie p-4 transition-colors',
                  listo ? 'border-marca/40' : activo ? 'border-marca' : 'border-borde')}>
                <div className={cx('grid size-12 place-items-center rounded-2xl transition-colors',
                  listo ? 'bg-marca text-white' : 'bg-marca-suave text-marca')}>
                  {listo
                    ? <motion.div key="ok" initial={{ scale: 0, rotate: -45 }} animate={{ scale: 1, rotate: 0 }}
                        transition={{ type: 'spring', stiffness: 400, damping: 15 }}><Check className="size-6" strokeWidth={3} /></motion.div>
                    : <Icono className="size-6" />}
                </div>
                <div>
                  <p className="font-semibold">{titulo}</p>
                  <p className="text-sm text-suave">{activo ? 'Analizando…' : detalle}</p>
                </div>
                {activo && (
                  <motion.div className="absolute inset-y-0 w-24 bg-gradient-to-r from-transparent via-marca/15 to-transparent"
                    initial={{ left: '-30%' }} animate={{ left: '110%' }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }} />
                )}
              </motion.div>
            )
          })}
        </div>
        <MensajeError mensaje={error} />
      </div>
    </Plantilla>
  )
}
