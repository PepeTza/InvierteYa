import { AnimatePresence, motion, MotionConfig } from 'motion/react'
import {
  ArrowLeft, ArrowRight, BatteryFull, Check, FlaskConical, Info, Lock, RotateCw, ShieldCheck, SignalHigh, Wifi, X,
} from 'lucide-react'
import { useEffect, useState, type ComponentType, type ReactNode } from 'react'
import { CongelarAlSalir, PASOS_REGISTRO, useApp, type Pantalla } from './estado'
import { Isotipo, Logo, cx } from './components/ui'
import PanelDemo, { type Vista } from './components/PanelDemo'
import Bienvenida from './screens/Bienvenida'
import Registro from './screens/Registro'
import Kyc from './screens/Kyc'
import Cuestionario from './screens/Cuestionario'
import Perfil from './screens/Perfil'
import Adhesion from './screens/Adhesion'
import Tarjeta from './screens/Tarjeta'
import Aporte from './screens/Aporte'
import Resultado from './screens/Resultado'
import Portafolio from './screens/Portafolio'

const PANTALLAS: Record<Pantalla, ComponentType> = {
  bienvenida: Bienvenida, registro: Registro, kyc: Kyc, cuestionario: Cuestionario, perfil: Perfil,
  adhesion: Adhesion, tarjeta: Tarjeta, aporte: Aporte, resultado: Resultado, portafolio: Portafolio,
}

// Ruta que se muestra en la barra de direcciones de la versión web.
const RUTAS: Record<Pantalla, string> = {
  bienvenida: '', registro: 'registro', kyc: 'verificacion', cuestionario: 'perfil/cuestionario',
  perfil: 'perfil', adhesion: 'contrato', tarjeta: 'metodo-de-pago', aporte: 'aportar',
  resultado: 'aportar/estado', portafolio: 'portafolio',
}

// Mapa del flujo: ayuda a la audiencia a ubicarse durante la demo.
const FLUJO: { nombre: string; corto: string; pantallas: Pantalla[] }[] = [
  { nombre: 'Registro', corto: 'Registro', pantallas: ['bienvenida', 'registro'] },
  { nombre: 'Verificación KYC', corto: 'KYC', pantallas: ['kyc'] },
  { nombre: 'Perfil de riesgo + tutor', corto: 'Perfil', pantallas: ['cuestionario', 'perfil'] },
  { nombre: 'Contrato de adhesión', corto: 'Contrato', pantallas: ['adhesion'] },
  { nombre: 'Tarjeta (pasarela)', corto: 'Tarjeta', pantallas: ['tarjeta'] },
  { nombre: 'Aporte: autorización y captura', corto: 'Aporte', pantallas: ['aporte', 'resultado'] },
  { nombre: 'Portafolio', corto: 'Portafolio', pantallas: ['portafolio'] },
]

// Tamaños de diseño. En ventanas chicas el marco se ESCALA completo para que nada quede cortado.
const TEL = { ancho: 400, alto: 860 }
const WEB = { ancho: 1280, alto: 800 }
const PANEL = 340, SEPARACION = 24, BARRA_SUPERIOR = 64, MARGEN = 32

function useVentana() {
  const leer = () => ({ ancho: window.innerWidth, alto: window.innerHeight })
  const [v, setV] = useState(leer)
  useEffect(() => {
    const alCambiar = () => setV(leer())
    window.addEventListener('resize', alCambiar)
    return () => window.removeEventListener('resize', alCambiar)
  }, [])
  return v
}

function useVista(): [Vista, (v: Vista) => void] {
  const [vista, setVista] = useState<Vista>(() => {
    try { return localStorage.getItem('invierteya.vista') === 'web' ? 'web' : 'movil' } catch { return 'movil' }
  })
  const cambiar = (v: Vista) => {
    setVista(v)
    try { localStorage.setItem('invierteya.vista', v) } catch { /* sin almacenamiento */ }
  }
  return [vista, cambiar]
}

// ------------------------------------------------------------------ piezas comunes
function MapaFlujo({ actual, horizontal = false }: { actual: Pantalla; horizontal?: boolean }) {
  const indice = FLUJO.findIndex(f => f.pantallas.includes(actual))
  const punto = (i: number) => cx('grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-bold transition-colors duration-300',
    i < indice ? 'bg-marca text-white' : i === indice ? 'bg-lima text-tinta ring-4 ring-lima/40' : 'bg-borde text-suave')

  if (horizontal) {
    return (
      <ol className="flex items-center gap-1.5">
        {FLUJO.map((f, i) => (
          <li key={f.nombre} className="flex items-center gap-1.5">
            <span className={punto(i)}>{i + 1}</span>
            <span className={cx('text-xs whitespace-nowrap transition-colors', i === indice ? 'font-bold text-tinta' : 'text-suave')}>{f.corto}</span>
            {i < FLUJO.length - 1 && <span className={cx('mx-1 h-px w-5', i < indice ? 'bg-marca' : 'bg-borde')} />}
          </li>
        ))}
      </ol>
    )
  }
  return (
    <div className="max-w-64 space-y-8">
      <div className="space-y-2">
        <Logo />
        <p className="text-sm text-suave">Prototipo navegable · Sesión 2 · Equipo D</p>
      </div>
      <ol className="space-y-1">
        {FLUJO.map((f, i) => (
          <li key={f.nombre} className="flex items-center gap-3 py-1.5">
            <span className={punto(i)}>{i + 1}</span>
            <span className={cx('text-sm transition-colors duration-300', i === indice ? 'font-bold text-tinta' : 'text-suave')}>{f.nombre}</span>
          </li>
        ))}
      </ol>
      <p className="text-xs leading-relaxed text-suave">
        Pasarela, suiche, emisor, banco fiduciario y casa de bolsa están <b className="text-aviso">simulados</b>. Solo datos sintéticos.
      </p>
    </div>
  )
}

/** Aviso no bloqueante (por ejemplo, cuando el servidor se reinició). */
function AvisoFlotante() {
  const { estado, actualizar } = useApp()
  useEffect(() => {
    if (!estado.aviso) return
    const t = setTimeout(() => actualizar({ aviso: undefined }), 6000)
    return () => clearTimeout(t)
  }, [estado.aviso, actualizar])
  return (
    <AnimatePresence>
      {estado.aviso && (
        <motion.div role="status" initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }}
          className="absolute inset-x-4 top-3 z-50 mx-auto flex max-w-md items-start gap-2 rounded-2xl bg-tinta p-3 text-sm text-white shadow-lg">
          <Info className="mt-0.5 size-4 shrink-0 text-lima" />
          <span className="flex-1">{estado.aviso}</span>
          <button onClick={() => actualizar({ aviso: undefined })} aria-label="Cerrar aviso"><X className="size-4 opacity-70" /></button>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function Contenido() {
  const { estado } = useApp()
  const Vista = PANTALLAS[estado.pantalla]
  return (
    <AnimatePresence mode="wait" initial={false} custom={estado.direccion}>
      <motion.div key={estado.pantalla} custom={estado.direccion} className="absolute inset-0"
        variants={{
          entra: (d: number) => ({ opacity: 0, x: d * 32 }),
          centro: { opacity: 1, x: 0 },
          sale: (d: number) => ({ opacity: 0, x: d * -32 }),
        }}
        initial="entra" animate="centro" exit="sale"
        transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1] }}>
        <CongelarAlSalir><Vista /></CongelarAlSalir>
      </motion.div>
    </AnimatePresence>
  )
}

// ------------------------------------------------------------------ vista móvil
function BarraEstado() {
  return (
    <div className="relative flex h-11 shrink-0 items-center justify-between px-7 text-[13px] font-semibold">
      <span className="cifra">9:41</span>
      <div className="absolute top-2.5 left-1/2 h-[26px] w-[100px] -translate-x-1/2 rounded-full bg-tinta" />
      <span className="flex items-center gap-1"><SignalHigh className="size-4" /><Wifi className="size-4" /><BatteryFull className="size-5" /></span>
    </div>
  )
}

function Telefono({ escala }: { escala: number }) {
  return (
    <div className="shrink-0" style={{ width: TEL.ancho * escala, height: TEL.alto * escala }}>
      <div className="relative origin-top-left rounded-[54px] bg-tinta p-[11px] shadow-telefono"
        style={{ width: TEL.ancho, height: TEL.alto, transform: `scale(${escala})` }}>
        <div className="relative flex h-full flex-col overflow-hidden rounded-[44px] bg-fondo">
          <BarraEstado />
          <div className="relative flex-1 @container"><Contenido /><AvisoFlotante /></div>
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ vista web
// Pasos del registro: en la web llevan una columna lateral con el progreso y el "por qué".
const ONBOARDING: Pantalla[] = ['registro', 'kyc', 'cuestionario', 'perfil', 'adhesion', 'tarjeta']

const POR_QUE: Record<string, string[]> = {
  Cuenta: ['Solo usamos tu correo para avisarte de tus aportes.', 'Tus datos viajan cifrados.'],
  Identidad: ['Lo exige la normativa (prevención LC/FT).', 'El banco fiduciario recibe el resultado.'],
  Perfil: ['10 preguntas, unos 2 minutos.', 'Define cuánto riesgo te conviene.', 'Tu tutor te explica el resultado.'],
  Contrato: ['Tu dinero queda en un fideicomiso a tu nombre.', 'Lo administra un banco regulado.'],
  Pago: ['La pasarela guarda tu tarjeta.', 'InvierteYa solo recibe un token.'],
}

function LateralRegistro() {
  const { estado } = useApp()
  const actual = PASOS_REGISTRO.findIndex(p => p.pantallas.includes(estado.pantalla))
  const nombre = PASOS_REGISTRO[actual]?.nombre ?? ''
  return (
    <aside className="flex w-[300px] shrink-0 flex-col border-r border-borde bg-superficie px-8 py-8">
      <p className="text-xs font-bold tracking-wide text-marca uppercase">Abre tu cuenta</p>
      <h2 className="mt-1 text-xl font-extrabold">5 pasos · 3 minutos</h2>
      <ol className="mt-7 space-y-1">
        {PASOS_REGISTRO.map((p, i) => {
          const hecho = i < actual, activo = i === actual
          return (
            <li key={p.nombre} className="relative flex items-center gap-3 py-2">
              {i < PASOS_REGISTRO.length - 1 && (
                <span className={cx('absolute top-10 left-[15px] h-4 w-0.5', hecho ? 'bg-marca' : 'bg-borde')} />
              )}
              <span className={cx('grid size-8 shrink-0 place-items-center rounded-full text-sm font-bold transition-colors duration-300',
                hecho ? 'bg-marca text-white' : activo ? 'bg-lima text-tinta ring-4 ring-lima/40' : 'bg-fondo text-suave')}>
                {hecho ? <Check className="size-4" strokeWidth={3} /> : i + 1}
              </span>
              <span className={cx('text-sm', activo ? 'font-bold' : hecho ? 'text-tinta' : 'text-suave')}>{p.nombre}</span>
            </li>
          )
        })}
      </ol>
      <AnimatePresence mode="wait">
        <motion.div key={nombre} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
          className="mt-8 rounded-2xl bg-fondo p-4">
          <p className="text-xs font-bold text-suave">¿Por qué te lo pedimos?</p>
          <ul className="mt-2 space-y-1.5">
            {(POR_QUE[nombre] ?? []).map(t => (
              <li key={t} className="flex gap-2 text-sm"><Check className="mt-0.5 size-4 shrink-0 text-marca" />{t}</li>
            ))}
          </ul>
        </motion.div>
      </AnimatePresence>
      <p className="mt-auto flex items-center gap-2 text-xs text-suave">
        <ShieldCheck className="size-4 text-marca" /> Prototipo · solo datos sintéticos
      </p>
    </aside>
  )
}

function BarraSitio() {
  const { estado, ir } = useApp()
  const paso = PASOS_REGISTRO.findIndex(p => p.pantallas.includes(estado.pantalla))
  const conCuenta = Boolean(estado.tarjeta) && paso < 0 && estado.pantalla !== 'bienvenida'
  const nombre = estado.usuario?.nombre ?? ''
  const iniciales = nombre.split(' ').map(p => p[0]).slice(0, 2).join('')

  return (
    <header className="flex h-16 shrink-0 items-center gap-6 border-b border-borde bg-superficie px-8">
      <Logo tamano="sm" />
      {paso >= 0 && (
        <div className="flex items-center gap-3 text-sm">
          <span className="h-5 w-px bg-borde" />
          <span className="text-suave">Paso <b className="cifra text-tinta">{paso + 1}</b> de {PASOS_REGISTRO.length}</span>
          <span className="font-semibold">{PASOS_REGISTRO[paso].nombre}</span>
        </div>
      )}
      {conCuenta && (
        <nav className="flex items-center gap-1 text-sm font-semibold">
          {([['portafolio', 'Mi portafolio'], ['aporte', 'Aportar']] as const).map(([p, texto]) => {
            const activo = estado.pantalla === p || (p === 'aporte' && estado.pantalla === 'resultado')
            return (
              <button key={p} onClick={() => ir(p)}
                className={cx('rounded-full px-4 py-2 transition-colors', activo ? 'bg-marca-suave text-marca' : 'text-suave hover:text-tinta')}>
                {texto}
              </button>
            )
          })}
        </nav>
      )}
      <div className="ml-auto flex items-center gap-3">
        {estado.usuario ? (
          <div className="flex items-center gap-2.5">
            <span className="grid size-9 place-items-center rounded-full bg-marca-suave text-sm font-bold text-marca">{iniciales}</span>
            <span className="text-sm font-semibold">{nombre}</span>
          </div>
        ) : (
          <span className="rounded-full bg-fondo px-3 py-1.5 text-xs font-semibold text-suave">Prototipo · datos sintéticos</span>
        )}
      </div>
    </header>
  )
}

function Navegador({ escala }: { escala: number }) {
  const { estado } = useApp()
  const registro = ONBOARDING.includes(estado.pantalla)
  return (
    <div className="shrink-0" style={{ width: WEB.ancho * escala, height: WEB.alto * escala }}>
      <div className="flex origin-top-left flex-col overflow-hidden rounded-2xl bg-superficie shadow-telefono"
        style={{ width: WEB.ancho, height: WEB.alto, transform: `scale(${escala})` }}>
        {/* Barra del navegador (decorativa) */}
        <div className="flex h-12 shrink-0 items-center gap-4 border-b border-borde bg-[#eef2ef] px-4">
          <div className="flex gap-2">
            <span className="size-3 rounded-full bg-[#ff5f57]" /><span className="size-3 rounded-full bg-[#febc2e]" /><span className="size-3 rounded-full bg-[#28c840]" />
          </div>
          <div className="flex gap-3 text-tenue"><ArrowLeft className="size-4" /><ArrowRight className="size-4" /><RotateCw className="size-4" /></div>
          <div className="flex h-8 flex-1 items-center gap-2 rounded-lg bg-superficie px-3 text-sm">
            <Lock className="size-3.5 text-marca" />
            <span className="text-suave">invierteya.app/</span>
            <motion.span key={estado.pantalla} initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-tinta">
              {RUTAS[estado.pantalla]}
            </motion.span>
          </div>
          <Isotipo className="size-6" />
        </div>
        <BarraSitio />
        <main className="relative flex-1 overflow-hidden bg-[radial-gradient(ellipse_at_top,_#eaf6ef,_var(--color-fondo)_55%)]">
          {registro ? (
            <div className="flex h-full">
              <LateralRegistro />
              <div className="relative flex-1 @container"><Contenido /></div>
            </div>
          ) : (
            <div className="relative h-full @container"><Contenido /></div>
          )}
          <AvisoFlotante />
        </main>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ App
export default function App() {
  const { estado } = useApp()
  const [panelMovil, setPanelMovil] = useState(false)
  const [vista, setVista] = useVista()
  const ventana = useVentana()

  const esCelular = ventana.ancho < 640
  const conPanel = ventana.ancho >= 1024
  const web = vista === 'web' && conPanel   // la versión web necesita una pantalla de escritorio

  const escalaWeb = Math.min(1,
    (ventana.ancho - MARGEN - PANEL - SEPARACION) / WEB.ancho,
    (ventana.alto - BARRA_SUPERIOR - MARGEN) / WEB.alto)
  const escalaTel = Math.min(1, (ventana.alto - MARGEN) / TEL.alto)

  let marco: ReactNode
  if (esCelular) {
    marco = (
      <div className="relative flex h-dvh w-full flex-col overflow-hidden bg-fondo">
        <div className="relative flex-1 @container"><Contenido /><AvisoFlotante /></div>
      </div>
    )
  } else if (web) {
    marco = <Navegador escala={escalaWeb} />
  } else {
    marco = <Telefono escala={escalaTel} />
  }

  const panel = (
    <aside className="w-[340px] shrink-0" style={{ height: web ? WEB.alto * escalaWeb : TEL.alto * escalaTel }}>
      <PanelDemo vista={vista} onVista={setVista} />
    </aside>
  )

  return (
    <MotionConfig reducedMotion="user">
      <div className="min-h-dvh bg-fondo sm:bg-[radial-gradient(ellipse_at_top,_#e3f3ea,_var(--color-fondo)_60%)]">
        {web ? (
          <div className="flex min-h-dvh flex-col items-center justify-center px-4 pb-4">
            <div className="flex h-16 w-full items-center gap-4" style={{ maxWidth: WEB.ancho * escalaWeb + PANEL + SEPARACION }}>
              <Logo tamano="sm" />
              <span className="hidden text-xs text-suave 2xl:inline">Prototipo navegable · Sesión 2 · Equipo D</span>
              <div className="ml-auto"><MapaFlujo actual={estado.pantalla} horizontal /></div>
            </div>
            <div className="flex items-start" style={{ gap: SEPARACION }}>{marco}{panel}</div>
          </div>
        ) : (
          <div className="mx-auto flex min-h-dvh max-w-[1280px] items-center justify-center gap-12 sm:p-4">
            {conPanel && <aside className="hidden flex-1 justify-end xl:flex"><MapaFlujo actual={estado.pantalla} /></aside>}
            {marco}
            {conPanel && panel}
          </div>
        )}

        {/* Panel de demo en pantallas pequeñas */}
        {!conPanel && (
          <button onClick={() => setPanelMovil(true)} aria-label="Abrir panel de demo"
            className="fixed right-4 bottom-24 z-30 grid size-11 place-items-center rounded-full bg-tinta text-white shadow-lg">
            <FlaskConical className="size-5" />
          </button>
        )}
        <AnimatePresence>
          {panelMovil && !conPanel && (
            <motion.div className="fixed inset-0 z-50 bg-fondo p-4"
              initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 30 }}>
              <PanelDemo onCerrar={() => setPanelMovil(false)} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </MotionConfig>
  )
}
