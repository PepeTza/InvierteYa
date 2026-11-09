import { Component, type ReactNode } from 'react'
import { CLAVE_ESTADO } from '../estado'

/** Red de seguridad para la demo: si algo falla, en vez de una página en blanco se ofrece reiniciar. */
export default class ErrorPantalla extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  reiniciar = () => {
    try { sessionStorage.removeItem(CLAVE_ESTADO) } catch { /* sin almacenamiento */ }
    location.reload()
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="grid min-h-dvh place-items-center bg-fondo p-6">
        <div className="max-w-sm space-y-4 rounded-3xl bg-superficie p-6 text-center shadow-tarjeta">
          <h1 className="text-xl font-extrabold">Algo salió mal</h1>
          <p className="text-sm text-suave">La demo encontró un error inesperado. Puedes empezar el recorrido de nuevo.</p>
          <button onClick={this.reiniciar}
            className="h-12 w-full rounded-2xl bg-marca font-semibold text-white hover:bg-marca-fuerte">
            Reiniciar recorrido
          </button>
          <p className="font-mono text-[11px] break-words text-tenue">{this.state.error.message}</p>
        </div>
      </div>
    )
  }
}
