import { ArrowLeft, MailCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Aviso, Boton, Campo, claseInput } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { navegar } from '../../lib/router'

/** Sin token: pide el enlace por correo. Con token (enlace del correo): define la contraseña nueva. */
export function RecuperarContrasena({ token }: { token: string | null }) {
  return (
    <div className="grid min-h-screen place-items-center bg-surface px-6 py-10">
      <div className="w-full max-w-md">
        <button onClick={() => navegar('/admin/login')} className="mb-8 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
          <ArrowLeft className="size-4" /> Volver a iniciar sesión
        </button>
        {token ? <Restablecer token={token} /> : <Solicitar />}
      </div>
    </div>
  )
}

function Solicitar() {
  const [identificador, setIdentificador] = useState('')
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setEnviando(true); setError(null)
    try { setMensaje((await api.olvideContrasena(identificador.trim())).message) }
    catch (err) { setError(mensajeError(err, 'No se pudo enviar la solicitud.')) }
    finally { setEnviando(false) }
  }

  if (mensaje) {
    return (
      <div>
        <MailCheck className="size-10 text-route" aria-hidden />
        <h1 className="mt-4 font-display text-3xl font-bold">Revise su correo</h1>
        <p className="mt-2 text-muted">{mensaje}</p>
        <p className="mt-4 text-sm text-muted">El enlace vence en pocos minutos. Si su cuenta no tiene correo registrado, pida a un administrador que restablezca su contraseña.</p>
      </div>
    )
  }
  return (
    <div>
      <h1 className="font-display text-3xl font-bold">¿Olvidó su contraseña?</h1>
      <p className="mt-1 text-muted">Escriba su usuario o correo y le enviaremos un enlace para crear una nueva.</p>
      <form onSubmit={enviar} className="mt-6 space-y-4">
        <Campo etiqueta="Usuario o correo" htmlFor="r-id">
          <input id="r-id" className={claseInput} value={identificador} onChange={(e) => setIdentificador(e.target.value)}
            required minLength={3} maxLength={120} autoComplete="username" autoFocus />
        </Campo>
        {error && <Aviso>{error}</Aviso>}
        <Boton type="submit" cargando={enviando} className="w-full py-2.5">Enviar enlace</Boton>
      </form>
    </div>
  )
}

function Restablecer({ token }: { token: string }) {
  const [password, setPassword] = useState('')
  const [repetida, setRepetida] = useState('')
  const [hecho, setHecho] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    if (password !== repetida) { setError('Las contraseñas no coinciden.'); return }
    setEnviando(true); setError(null)
    try { await api.restablecerContrasena(token, password); setHecho(true) }
    catch (err) { setError(mensajeError(err, 'No se pudo cambiar la contraseña.')) }
    finally { setEnviando(false) }
  }

  if (hecho) {
    return (
      <div>
        <h1 className="font-display text-3xl font-bold">Contraseña actualizada</h1>
        <p className="mt-2 text-muted">Sus sesiones anteriores se cerraron. Ya puede iniciar sesión con la nueva contraseña.</p>
        <Boton className="mt-6 w-full py-2.5" onClick={() => navegar('/admin/login')}>Ir a iniciar sesión</Boton>
      </div>
    )
  }
  return (
    <div>
      <h1 className="font-display text-3xl font-bold">Nueva contraseña</h1>
      <p className="mt-1 text-muted">Mínimo 8 caracteres.</p>
      <form onSubmit={enviar} className="mt-6 space-y-4">
        <Campo etiqueta="Nueva contraseña" htmlFor="n-pass">
          <input id="n-pass" type="password" className={claseInput} value={password} onChange={(e) => setPassword(e.target.value)}
            required minLength={8} maxLength={128} autoComplete="new-password" autoFocus />
        </Campo>
        <Campo etiqueta="Repita la contraseña" htmlFor="n-pass2">
          <input id="n-pass2" type="password" className={claseInput} value={repetida} onChange={(e) => setRepetida(e.target.value)}
            required minLength={8} maxLength={128} autoComplete="new-password" />
        </Campo>
        {error && <Aviso>{error}</Aviso>}
        <Boton type="submit" cargando={enviando} className="w-full py-2.5">Cambiar contraseña</Boton>
      </form>
    </div>
  )
}
