import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { ProveedorEstado } from './estado'
import ErrorPantalla from './components/ErrorPantalla'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorPantalla>
      <ProveedorEstado>
        <App />
      </ProveedorEstado>
    </ErrorPantalla>
  </StrictMode>,
)
