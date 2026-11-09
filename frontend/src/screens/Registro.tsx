import { motion } from 'motion/react'
import { useState, type FormEvent } from 'react'
import { useApp } from '../estado'
import { api } from '../lib/api'
import { useLlamada } from '../lib/useLlamada'
import { aparecer, Boton, Campo, Encabezado, MensajeError, Plantilla, Titulo } from '../components/ui'

export default function Registro() {
  const { ir, actualizar } = useApp()
  const { cargando, error, ejecutar } = useLlamada()
  const [nombre, setNombre] = useState('María Pérez')
  const [email, setEmail] = useState('maria@example.com')
  const valido = nombre.trim().length >= 3 && /^\S+@\S+\.\S+$/.test(email)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    const usuario = await ejecutar(() => api.registrar(nombre.trim(), email.trim()))
    if (usuario) {
      actualizar({ usuario })
      ir('kyc')
    }
  }

  return (
    <form onSubmit={enviar} className="h-full">
      <Plantilla
        encabezado={<Encabezado onAtras={() => ir('bienvenida', -1)} pasoActual={0} totalPasos={5} />}
        pie={<Boton type="submit" cargando={cargando} disabled={!valido}>Crear cuenta</Boton>}
      >
        <div className="space-y-8 pt-4">
          <motion.div {...aparecer(0)}>
            <Titulo sub="Usa datos ficticios: esto es una demo.">Creemos tu cuenta</Titulo>
          </motion.div>
          <motion.div {...aparecer(1)} className="space-y-4 @2xl:grid @2xl:grid-cols-2 @2xl:gap-4 @2xl:space-y-0">
            <Campo etiqueta="Nombre y apellido" value={nombre} onChange={e => setNombre(e.target.value)}
              autoComplete="name" />
            <Campo etiqueta="Correo" type="email" value={email} onChange={e => setEmail(e.target.value)}
              autoComplete="email" />
          </motion.div>
          <MensajeError mensaje={error} />
        </div>
      </Plantilla>
    </form>
  )
}
