import { motion } from 'motion/react'
import { ArrowRight, ClipboardList, Coins, GraduationCap, Landmark, PieChart, Sparkles } from 'lucide-react'
import { useApp } from '../estado'
import { aparecer, Boton, Logo } from '../components/ui'

const PUNTOS = [
  { icono: Sparkles, texto: 'Desde $5' },
  { icono: Landmark, texto: 'Fideicomiso bancario' },
  { icono: GraduationCap, texto: 'Tutor que te enseña' },
]

/** Gráfico decorativo: una línea de crecimiento que se dibuja sola. */
function Crecimiento({ className = 'max-w-[320px]' }: { className?: string }) {
  return (
    <div className={`relative mx-auto aspect-[4/3] w-full ${className}`}>
      <motion.div className="absolute inset-6 rounded-[40px] bg-marca-suave"
        initial={{ scale: 0.85, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.6, ease: 'easeOut' }} />
      <motion.div className="absolute top-2 right-6 size-24 rounded-full bg-lima/70 blur-2xl"
        animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }} />
      <svg viewBox="0 0 320 240" className="relative size-full">
        <defs>
          <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--color-marca)" stopOpacity="0.25" />
            <stop offset="100%" stopColor="var(--color-marca)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <motion.path d="M40 190 L95 160 L140 172 L190 120 L230 132 L280 64 L280 210 L40 210 Z"
          fill="url(#area)" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1, duration: 0.6 }} />
        <motion.path d="M40 190 L95 160 L140 172 L190 120 L230 132 L280 64"
          fill="none" stroke="var(--color-marca)" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ delay: 0.3, duration: 1.2, ease: 'easeInOut' }} />
        <motion.circle cx="280" cy="64" r="11" fill="var(--color-lima)" stroke="var(--color-marca)" strokeWidth="5"
          initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 1.4, type: 'spring', stiffness: 300 }} />
      </svg>
      <motion.div className="absolute bottom-10 left-2 rounded-2xl bg-superficie px-3 py-2 shadow-tarjeta"
        initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 1.1 }}>
        <p className="text-[11px] font-medium text-suave">Tu aporte</p>
        <p className="cifra text-lg font-extrabold">$5,00</p>
      </motion.div>
      <motion.div className="absolute top-12 right-0 rounded-2xl bg-tinta px-3 py-2 text-white shadow-tarjeta"
        initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 1.6 }}>
        <p className="text-[11px] font-medium text-white/60">Unidades</p>
        <p className="cifra text-lg font-extrabold">+4,0000</p>
      </motion.div>
    </div>
  )
}

const COMO_FUNCIONA = [
  { icono: ClipboardList, titulo: 'Responde 10 preguntas', texto: 'Conocemos tu perfil de riesgo.' },
  { icono: Coins, titulo: 'Aporta desde $5', texto: 'Con tu tarjeta, sin papeleo.' },
  { icono: PieChart, titulo: 'Recibe unidades', texto: 'Tu parte del fideicomiso, al instante.' },
]

/** Versión web: landing de dos columnas (se activa cuando el contenedor es ancho). */
function BienvenidaWeb() {
  const { ir } = useApp()
  return (
    <div className="hidden h-full overflow-y-auto sin-scrollbar @3xl:block">
      <div className="mx-auto grid max-w-[1080px] grid-cols-[1.1fr_1fr] items-center gap-12 px-12 pt-14">
        <div className="space-y-7">
          <motion.span {...aparecer(0)} className="inline-flex items-center gap-2 rounded-full bg-marca-suave px-3 py-1.5 text-sm font-semibold text-marca">
            <Sparkles className="size-4" /> Inversión fraccionada con IA didáctica
          </motion.span>
          <motion.h1 {...aparecer(1)} className="text-[56px] leading-[1.02] font-extrabold tracking-tight text-balance">
            Invierte desde <span className="text-marca">$5</span>.<br />Aprende mientras creces.
          </motion.h1>
          <motion.p {...aparecer(2)} className="max-w-md text-lg text-suave">
            Un portafolio a tu medida y un tutor que te explica cada paso.
          </motion.p>
          <motion.div {...aparecer(3)} className="flex items-center gap-4">
            <Boton onClick={() => ir('registro')} className="w-auto px-8">Crear mi cuenta <ArrowRight className="size-5" /></Boton>
            <span className="flex items-center gap-1.5 text-sm text-suave"><Landmark className="size-4 text-marca" /> Fideicomiso en un banco regulado</span>
          </motion.div>
        </div>
        <Crecimiento className="max-w-[460px]" />
      </div>
      <motion.ul {...aparecer(5)} className="mx-auto mt-10 grid max-w-[1080px] grid-cols-3 gap-4 px-12 pb-10">
        {COMO_FUNCIONA.map(({ icono: Icono, titulo, texto }, i) => (
          <li key={titulo} className="flex items-start gap-3 rounded-3xl bg-superficie p-5 shadow-tarjeta">
            <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-marca-suave text-marca"><Icono className="size-5" /></span>
            <div>
              <p className="text-xs font-bold text-tenue">0{i + 1}</p>
              <p className="font-bold">{titulo}</p>
              <p className="text-sm text-suave">{texto}</p>
            </div>
          </li>
        ))}
      </motion.ul>
    </div>
  )
}

export default function Bienvenida() {
  const { ir } = useApp()
  return (
    <>
      <BienvenidaWeb />
      <div className="flex h-full flex-col @3xl:hidden">
        <motion.div {...aparecer(0)} className="px-6 pt-6"><Logo /></motion.div>
        <div className="flex min-h-0 flex-1 flex-col justify-center gap-6 overflow-y-auto px-6 py-4 sin-scrollbar">
          <Crecimiento />
          <motion.div {...aparecer(2)} className="space-y-3">
            <h1 className="text-[34px] leading-[1.05] font-extrabold tracking-tight text-balance">
              Invierte desde <span className="text-marca">$5</span>.<br />Aprende mientras creces.
            </h1>
          </motion.div>
          <motion.ul {...aparecer(3)} className="flex flex-wrap gap-2">
            {PUNTOS.map(({ icono: Icono, texto }) => (
              <li key={texto} className="flex items-center gap-1.5 rounded-full bg-superficie px-3 py-1.5 text-sm font-medium shadow-tarjeta">
                <Icono className="size-4 text-marca" />{texto}
              </li>
            ))}
          </motion.ul>
        </div>
        <motion.div {...aparecer(4)} className="shrink-0 space-y-3 px-6 pt-2 pb-6">
          <Boton onClick={() => ir('registro')} icono={null}>
            Comenzar <ArrowRight className="size-5" />
          </Boton>
          <p className="text-center text-xs text-suave">Prototipo académico · solo datos sintéticos</p>
        </motion.div>
      </div>
    </>
  )
}
