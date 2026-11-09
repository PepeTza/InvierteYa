import { useCallback, useState } from 'react'
import { useApp } from '../estado'
import { ErrorApi } from './api'

/** Ejecuta una llamada a la API manejando "cargando" y el mensaje de error.
 *  Si el servidor se reinició (datos en memoria), el usuario ya no existe: se reinicia el recorrido. */
export function useLlamada() {
  const { reiniciar } = useApp()
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ejecutar = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setCargando(true)
    setError(null)
    try {
      return await fn()
    } catch (e) {
      if (e instanceof ErrorApi && e.codigo === 'USUARIO_NO_EXISTE') {
        reiniciar('El servidor se reinició y los datos de la demo se borraron. Empecemos de nuevo.')
        return undefined
      }
      setError(e instanceof Error ? e.message : 'Ocurrió un error inesperado.')
      return undefined
    } finally {
      setCargando(false)
    }
  }, [reiniciar])

  return { cargando, error, setError, ejecutar }
}
