import { ArrowLeft, Siren } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Aviso, Boton, Campo, claseInput } from '../../components/ui'
import { mensajeError } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { navegar } from '../../lib/router'

export function Login() {
  const { iniciarSesion } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      await iniciarSesion(username.trim(), password)
      navegar('/admin')
    } catch (err) {
      setError(mensajeError(err, 'No se pudo iniciar sesión.'))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-[1fr_480px]">
      <div className="relative hidden overflow-hidden bg-ink p-10 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-2.5">
          <span className="grid size-10 place-items-center rounded-md bg-critical"><Siren className="size-5" aria-hidden /></span>
          <span className="font-display text-2xl font-semibold">Centro de despacho</span>
        </div>
        <div className="max-w-md">
          <p className="font-display text-5xl font-bold leading-[1.02]">Cada minuto cuenta. El sistema elige la ruta; usted toma las decisiones.</p>
          <p className="mt-4 text-white/70">Asignación automática por ruta más corta, cola de prioridad y analítica en tiempo real.</p>
        </div>
        <p className="text-sm text-white/50">DWG EMS-05 REV A</p>
      </div>

      <div className="flex flex-col justify-center bg-surface px-6 py-10 sm:px-12">
        <button onClick={() => navegar('/')} className="mb-10 inline-flex items-center gap-1.5 self-start text-sm text-muted hover:text-ink">
          <ArrowLeft className="size-4" /> Portal ciudadano
        </button>
        <h1 className="font-display text-4xl font-bold">Iniciar sesión</h1>
        <p className="mt-1 text-muted">Acceso para operadores y administradores.</p>
        <form onSubmit={enviar} className="mt-8 space-y-4">
          <Campo etiqueta="Usuario" htmlFor="u">
            <input id="u" autoComplete="username" className={claseInput} value={username}
              onChange={(e) => setUsername(e.target.value)} required autoFocus />
          </Campo>
          <Campo etiqueta="Contraseña" htmlFor="p">
            <input id="p" type="password" autoComplete="current-password" className={claseInput} value={password}
              onChange={(e) => setPassword(e.target.value)} required />
          </Campo>
          {error && <Aviso>{error}</Aviso>}
          <Boton type="submit" cargando={enviando} className="w-full py-2.5">Entrar</Boton>
          <button type="button" onClick={() => navegar('/admin/recuperar')}
            className="block w-full text-center text-sm font-semibold text-route hover:underline">
            ¿Olvidó su contraseña?
          </button>
        </form>
      </div>
    </div>
  )
}
