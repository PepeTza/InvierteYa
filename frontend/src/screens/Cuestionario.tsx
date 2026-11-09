import { AnimatePresence, motion } from 'motion/react'
import { Check, Loader2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useApp } from '../estado'
import { api, type Cuestionario as TCuestionario } from '../lib/api'
import { PREGUNTAS, type Opcion, type Pregunta } from '../lib/datos'
import { useLlamada } from '../lib/useLlamada'
import { Boton, Encabezado, MensajeError, cx } from '../components/ui'

function Opciones({ pregunta, valor, onElegir }: {
  pregunta: Pregunta; valor: unknown; onElegir: (o: Opcion) => void
}) {
  const conIconos = pregunta.opciones!.some(o => o.icono)
  return (
    <div className="space-y-2.5 @2xl:grid @2xl:grid-cols-2 @2xl:gap-3 @2xl:space-y-0">
      {pregunta.opciones!.map((o, i) => {
        const elegida = valor === o.valor
        const Icono = o.icono
        return (
          <motion.button key={String(o.valor)} type="button" onClick={() => onElegir(o)}
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 + i * 0.05 }}
            whileTap={{ scale: 0.98 }}
            className={cx('flex w-full items-center gap-3 rounded-2xl border-2 bg-superficie p-4 text-left transition-colors',
              elegida ? 'border-marca bg-marca-suave' : 'border-transparent shadow-tarjeta hover:border-marca/30')}>
            {conIconos && Icono && (
              <span className={cx('grid size-10 shrink-0 place-items-center rounded-xl transition-colors',
                elegida ? 'bg-marca text-white' : 'bg-fondo text-marca')}>
                <Icono className="size-5" />
              </span>
            )}
            <span className="flex-1 font-semibold">{o.etiqueta}</span>
            <span className={cx('grid size-6 place-items-center rounded-full border-2 transition-colors',
              elegida ? 'border-marca bg-marca text-white' : 'border-borde')}>
              {elegida && <Check className="size-3.5" strokeWidth={3} />}
            </span>
          </motion.button>
        )
      })}
    </div>
  )
}

function Deslizador({ pregunta, valor, onCambiar }: {
  pregunta: Pregunta; valor: number; onCambiar: (v: number) => void
}) {
  const { min = 0, max = 100, paso = 1, sufijo = '' } = pregunta
  const progreso = ((valor - min) / (max - min)) * 100
  return (
    <div className="space-y-10 pt-6 @2xl:max-w-xl">
      <div className="text-center">
        <motion.span key={valor} initial={{ y: -4, opacity: 0.6 }} animate={{ y: 0, opacity: 1 }}
          className="cifra inline-block text-6xl font-extrabold text-marca">{valor}</motion.span>
        <span className="text-2xl font-bold text-suave">{sufijo}</span>
      </div>
      <div className="space-y-2">
        <input type="range" className="deslizador w-full" min={min} max={max} step={paso} value={valor}
          aria-label={pregunta.titulo}
          style={{ '--progreso': `${progreso}%` } as React.CSSProperties}
          onChange={e => onCambiar(Number(e.target.value))} />
        <div className="flex justify-between text-xs font-medium text-suave">
          <span>{min}{sufijo}</span><span>{max}{sufijo}</span>
        </div>
      </div>
    </div>
  )
}

export default function Cuestionario() {
  const { estado, ir, actualizar } = useApp()
  const { cargando, error, ejecutar } = useLlamada()
  const { respuestas, preguntaActual: actual } = estado
  const [dir, setDir] = useState(1)
  const enviado = useRef(false)
  const total = PREGUNTAS.length
  const pregunta = PREGUNTAS[Math.min(actual, total - 1)]
  const valor = respuestas[pregunta.campo] ?? pregunta.inicial

  async function enviar(r: Partial<TCuestionario>) {
    if (enviado.current) return
    enviado.current = true
    const perfil = await ejecutar(() => api.perfil(estado.usuario!.usuario_id, r as TCuestionario))
    enviado.current = false
    if (perfil) {
      actualizar({ perfil, usuario: { ...estado.usuario!, perfil: perfil.perfil } })
      ir('perfil')
    } else {
      actualizar({ preguntaActual: total - 1 })
    }
  }

  // El panel de demo puede completar todas las respuestas (preguntaActual = total): se envían solas.
  useEffect(() => {
    if (actual >= total) enviar(respuestas)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actual])

  // Elegir solo marca la respuesta; el usuario confirma con "Continuar" (puede cambiar de opinión).
  function responder(v: unknown) {
    actualizar({ respuestas: { ...respuestas, [pregunta.campo]: v } })
  }

  function siguiente(r = respuestas) {
    const conValor = { ...r, [pregunta.campo]: r[pregunta.campo] ?? pregunta.inicial }
    setDir(1)
    if (actual < total - 1) actualizar({ respuestas: conValor, preguntaActual: actual + 1 })
    else { actualizar({ respuestas: conValor }); enviar(conValor) }
  }

  function atras() {
    setDir(-1)
    actualizar({ preguntaActual: actual - 1 })
  }

  const enviando = cargando || actual >= total

  return (
    <div className="flex h-full flex-col">
      <Encabezado onAtras={actual > 0 && !enviando ? atras : undefined} pasoActual={2} totalPasos={5} />
      <div className="px-6 pt-2 @2xl:mx-auto @2xl:w-full @2xl:max-w-[920px] @2xl:px-8">
        <div className="flex items-center justify-between text-sm font-semibold">
          <span className="text-marca">Tu perfil de inversión</span>
          <span className="cifra text-suave">{Math.min(actual + 1, total)} / {total}</span>
        </div>
      </div>
      <div className="relative flex-1 overflow-hidden">
        <AnimatePresence mode="popLayout" custom={dir} initial={false}>
          <motion.div key={pregunta.campo} custom={dir}
            className="absolute inset-0 overflow-y-auto px-6 pt-6 pb-4 sin-scrollbar @2xl:mx-auto @2xl:max-w-[920px] @2xl:px-8"
            variants={{
              entra: (d: number) => ({ x: d * 60, opacity: 0 }),
              centro: { x: 0, opacity: 1 },
              sale: (d: number) => ({ x: d * -60, opacity: 0 }),
            }}
            initial="entra" animate="centro" exit="sale"
            transition={{ duration: 0.28, ease: [0.2, 0.8, 0.2, 1] }}>
            <h1 className="text-[26px] leading-tight font-extrabold tracking-tight text-balance">{pregunta.titulo}</h1>
            {pregunta.ayuda && <p className="mt-2 text-[15px] text-suave">{pregunta.ayuda}</p>}
            <div className="mt-7">
              {pregunta.tipo === 'opciones'
                ? <Opciones pregunta={pregunta} valor={valor} onElegir={o => responder(o.valor)} />
                : <Deslizador pregunta={pregunta} valor={Number(valor)} onCambiar={v => responder(v)} />}
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
      <div className="shrink-0 px-6 pt-2 pb-6 @2xl:border-t @2xl:border-borde @2xl:bg-superficie/70 @2xl:px-8 @2xl:py-4">
        <div className="space-y-3 @2xl:mx-auto @2xl:flex @2xl:max-w-[920px] @2xl:flex-row-reverse @2xl:items-center @2xl:gap-4 @2xl:space-y-0 @2xl:[&>button]:w-auto @2xl:[&>button]:min-w-56 @2xl:[&>button]:px-8 @2xl:[&>div]:flex-1">
          <MensajeError mensaje={error} />
          {enviando ? (
            <div className="flex h-14 items-center justify-center gap-2 font-semibold text-marca">
              <Loader2 className="size-5 animate-spin" /> Calculando tu perfil…
            </div>
          ) : (
            <Boton onClick={() => siguiente()} disabled={valor === undefined}>
              {actual === total - 1 ? 'Ver mi perfil' : 'Continuar'}
            </Boton>
          )}
        </div>
      </div>
    </div>
  )
}
