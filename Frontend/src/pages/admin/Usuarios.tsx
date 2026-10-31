import { KeyRound, RotateCcw, ShieldCheck, UserPlus } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNotificar } from '../../components/Notificaciones'
import { Aviso, Boton, Campo, Cargando, Modal, claseInput } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useDatos } from '../../lib/hooks'
import type { CatalogoRoles, Modulo, Nivel, Permisos, Usuario } from '../../lib/types'

const NIVEL_TEXTO = ['Sin acceso', 'Ver', 'Editar'] as const
const NIVEL_CLASE = ['bg-line/60 text-muted line-through decoration-muted/50', 'bg-route-soft text-route', 'bg-ink text-white'] as const

export function Usuarios() {
  const { usuario: yo, esAdmin } = useAuth()
  const notificar = useNotificar()
  const usuarios = useDatos(api.usuarios)
  const catalogo = useDatos(api.rolesUsuarios)
  const [editor, setEditor] = useState<Usuario | 'nuevo' | null>(null)
  const [clave, setClave] = useState<Usuario | null>(null)

  const cambiar = async (u: Usuario, datos: { is_active?: boolean }, msg: string) => {
    try { await api.actualizarUsuario(u.id, datos); notificar('success', msg); usuarios.recargar() }
    catch (e) { notificar('error', mensajeError(e)) }
  }

  if (!esAdmin || !yo) return <Aviso>Solo un administrador puede gestionar usuarios y permisos.</Aviso>
  const cat = catalogo.datos

  return (
    <div className="max-w-6xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted">
          Cada usuario tiene un <strong className="text-ink">perfil</strong> que define qué módulos puede ver o editar.
          El administrador puede ajustar cualquier módulo de cualquier usuario.
        </p>
        <Boton icono={<UserPlus className="size-4" />} onClick={() => setEditor('nuevo')} disabled={!cat}>Nuevo usuario</Boton>
      </div>
      {(usuarios.error || catalogo.error) && <Aviso>{usuarios.error || catalogo.error}</Aviso>}

      <div className="overflow-hidden rounded-lg border border-line bg-surface">
        {(usuarios.cargando && !usuarios.datos) || !cat ? <Cargando /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead className="border-b border-line bg-paper/60 text-left text-xs text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Usuario</th>
                  <th className="px-3 py-2.5 font-medium">Perfil</th>
                  <th className="px-3 py-2.5 font-medium">Acceso por módulo</th>
                  <th className="px-3 py-2.5 font-medium">Estado</th>
                  <th className="px-4 py-2.5 text-right font-medium">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {usuarios.datos?.map((u) => (
                  <tr key={u.id} className={u.is_active ? '' : 'opacity-60'}>
                    <td className="px-4 py-2.5">
                      <strong>{u.username}</strong>
                      <span className="block text-xs text-muted">{u.full_name}{u.email ? ` · ${u.email}` : ''}</span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="font-medium">{u.role_label}</span>
                      {u.custom_permissions && <span className="mt-0.5 block text-xs font-semibold text-high">Permisos ajustados</span>}
                    </td>
                    <td className="px-3 py-2.5">
                      {u.role === 'admin'
                        ? <span className="rounded bg-ink px-2 py-0.5 text-xs font-semibold text-white">Acceso total + usuarios</span>
                        : <ChipsPermisos permisos={u.permissions} cat={cat} />}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={`rounded px-2 py-0.5 text-xs font-semibold ${u.is_active ? 'bg-ok-soft text-ok' : 'bg-line text-muted'}`}>{u.is_active ? 'Activo' : 'Desactivado'}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-1">
                        <Boton variante="fantasma" onClick={() => setEditor(u)} icono={<ShieldCheck className="size-4" />}>Permisos</Boton>
                        <Boton variante="fantasma" onClick={() => setClave(u)} icono={<KeyRound className="size-4" />}>Clave</Boton>
                        {u.id !== yo.id && (
                          <Boton variante="fantasma" onClick={() => cambiar(u, { is_active: !u.is_active }, u.is_active ? `${u.username} desactivado.` : `${u.username} activado.`)}>
                            {u.is_active ? 'Desactivar' : 'Activar'}
                          </Boton>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {cat && <TablaPerfiles cat={cat} />}

      {cat && (
        <EditorUsuario
          key={editor === null ? 'cerrado' : editor === 'nuevo' ? 'nuevo' : editor.id}
          usuario={editor} cat={cat} esYo={editor !== null && editor !== 'nuevo' && editor.id === yo.id}
          onCerrar={() => setEditor(null)}
          onGuardado={(u, nuevo) => {
            setEditor(null)
            notificar('success', nuevo ? `Usuario ${u.username} creado.` : `Permisos de ${u.username} actualizados.`)
            usuarios.recargar()
          }} />
      )}
      <FormClave usuario={clave} onCerrar={() => setClave(null)} onGuardado={() => { notificar('success', 'Contraseña actualizada.'); setClave(null) }} />
    </div>
  )
}

/** Resumen compacto: un chip por módulo, con su nivel. */
function ChipsPermisos({ permisos, cat }: { permisos: Permisos; cat: CatalogoRoles }) {
  return (
    <div className="flex flex-wrap gap-1">
      {cat.modules.map((m) => {
        const n = permisos[m.value] ?? 0
        return (
          <span key={m.value} title={`${m.label}: ${NIVEL_TEXTO[n]}`}
            className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${NIVEL_CLASE[n]}`}>
            {m.label.replace(' de control', '')}{n === 2 ? ' ✎' : ''}
          </span>
        )
      })}
    </div>
  )
}

/** Matriz de referencia: qué puede hacer cada perfil predefinido. */
function TablaPerfiles({ cat }: { cat: CatalogoRoles }) {
  return (
    <section className="rounded-lg border border-line bg-surface">
      <header className="border-b border-line px-4 py-3">
        <h2 className="font-display text-lg font-semibold">Perfiles predefinidos</h2>
        <p className="text-sm text-muted">Permisos con los que empieza cada perfil. <span className="whitespace-nowrap">✎ = puede editar.</span></p>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th className="px-4 py-2 font-medium">Perfil</th>
              {cat.modules.map((m) => <th key={m.value} className="px-2 py-2 text-center font-medium">{m.label.replace(' de control', '')}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {cat.roles.map((r) => (
              <tr key={r.value}>
                <td className="px-4 py-2.5 align-top">
                  <p className="font-semibold">{r.label}</p>
                  <p className="max-w-xs text-xs text-muted">{r.description}</p>
                </td>
                {cat.modules.map((m) => {
                  const n = r.permissions[m.value] ?? 0
                  return (
                    <td key={m.value} className="px-2 py-2.5 text-center align-top">
                      <span className={`inline-block min-w-16 rounded px-1.5 py-0.5 text-[11px] font-semibold ${NIVEL_CLASE[n]}`}>
                        {NIVEL_TEXTO[n]}{n === 2 ? ' ✎' : ''}
                      </span>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

/** Crear usuario o editar su perfil y sus permisos por módulo. */
function EditorUsuario({ usuario, cat, esYo, onCerrar, onGuardado }: {
  usuario: Usuario | 'nuevo' | null; cat: CatalogoRoles; esYo: boolean
  onCerrar: () => void; onGuardado: (u: Usuario, nuevo: boolean) => void
}) {
  const nuevo = usuario === 'nuevo'
  const existente = usuario !== null && usuario !== 'nuevo' ? usuario : null
  const perfilDe = (rol: string) => cat.roles.find((r) => r.value === rol)
  const rolInicial = existente?.role ?? 'incidentes'

  const [rol, setRol] = useState(rolInicial)
  const [permisos, setPermisos] = useState<Permisos>(existente?.permissions ?? perfilDe(rolInicial)!.permissions)
  const [nombre, setNombre] = useState(existente?.full_name ?? '')
  const [correo, setCorreo] = useState(existente?.email ?? '')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)

  const perfil = perfilDe(rol)
  const esAdminRol = rol === 'admin'
  const ajustados = !esAdminRol && perfil ? cat.modules.filter((m) => perfil.permissions[m.value] !== permisos[m.value]).length : 0

  const elegirRol = (r: string) => { setRol(r); setPermisos(perfilDe(r)!.permissions) }
  const fijar = (m: Modulo, n: Nivel) => setPermisos((p) => ({ ...p, [m]: n }))

  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    setGuardando(true); setError(null)
    try {
      const ajustes = esAdminRol ? undefined : permisos
      const u = nuevo
        ? await api.crearUsuario({ username: username.trim(), password, full_name: nombre.trim(), email: correo.trim() || undefined, role: rol, permissions: ajustes })
        : await api.actualizarUsuario(existente!.id, {
            full_name: nombre.trim(), email: correo.trim(), role: rol,
            ...(ajustados === 0 ? { reset_permissions: true } : { permissions: ajustes }),
          })
      onGuardado(u, nuevo)
    } catch (err) { setError(mensajeError(err)) } finally { setGuardando(false) }
  }

  return (
    <Modal abierto={usuario !== null} ancho="max-w-3xl"
      titulo={nuevo ? 'Nuevo usuario' : `Permisos de ${existente?.username ?? ''}`} onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Nombre completo" htmlFor="u-nom">
            <input id="u-nom" className={claseInput} value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={100} />
          </Campo>
          <Campo etiqueta="Perfil" htmlFor="u-rol" ayuda={esYo ? 'No puede quitarse a sí mismo el perfil de administrador.' : perfil?.description}>
            <select id="u-rol" className={claseInput} value={rol} disabled={esYo} onChange={(e) => elegirRol(e.target.value)}>
              {cat.roles.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </Campo>
        </div>
        <Campo etiqueta="Correo electrónico" htmlFor="u-mail" ayuda="Se usa para «¿Olvidó su contraseña?». Sin correo, solo un administrador puede restablecerla.">
          <input id="u-mail" type="email" className={claseInput} value={correo} onChange={(e) => setCorreo(e.target.value)} maxLength={120} autoComplete="off" />
        </Campo>
        {nuevo && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Usuario" htmlFor="u-user" ayuda="Letras, números, punto o guion">
              <input id="u-user" className={claseInput} value={username} onChange={(e) => setUsername(e.target.value)} required minLength={3} maxLength={50} autoComplete="off" />
            </Campo>
            <Campo etiqueta="Contraseña" htmlFor="u-pass" ayuda="Mínimo 8 caracteres">
              <input id="u-pass" type="password" className={claseInput} value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete="new-password" />
            </Campo>
          </div>
        )}

        <fieldset>
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <legend className="text-sm font-semibold">Permisos por módulo</legend>
            {ajustados > 0 && (
              <button type="button" onClick={() => setPermisos(perfil!.permissions)} className="inline-flex items-center gap-1 text-xs font-semibold text-route hover:underline">
                <RotateCcw className="size-3.5" /> Volver al perfil ({ajustados} {ajustados === 1 ? 'ajuste' : 'ajustes'})
              </button>
            )}
          </div>
          {esAdminRol ? (
            <p className="rounded-md bg-paper px-3 py-2.5 text-sm">El administrador tiene acceso total a todos los módulos y es el único que gestiona usuarios y permisos.</p>
          ) : (
            <ul className="divide-y divide-line rounded-md border border-line">
              {cat.modules.map((m) => {
                const n = permisos[m.value] ?? 0
                const cambiado = perfil && perfil.permissions[m.value] !== n
                return (
                  <li key={m.value} className="grid items-center gap-2 px-3 py-2.5 sm:grid-cols-[1fr_auto]">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold">
                        {m.label}
                        {cambiado && <span className="ml-2 rounded bg-high-fill/20 px-1.5 py-0.5 text-[11px] font-semibold text-high">ajustado</span>}
                      </p>
                      <p className="text-xs text-muted">
                        {n === 0 ? 'No ve este módulo.' : n === 1 ? `Ver: ${m.view}.` : `Editar: ${m.edit}.`}
                      </p>
                    </div>
                    <div className="inline-flex rounded-md border border-line bg-surface p-0.5" role="radiogroup" aria-label={`Nivel en ${m.label}`}>
                      {([0, 1, 2] as Nivel[]).map((v) => {
                        const deshabilitado = v === 2 && m.read_only
                        return (
                          <button key={v} type="button" role="radio" aria-checked={n === v} disabled={deshabilitado}
                            title={deshabilitado ? 'Este módulo es de solo consulta' : undefined}
                            onClick={() => fijar(m.value, v)}
                            className={`rounded px-2.5 py-1 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-30 ${
                              n === v ? (v === 0 ? 'bg-muted text-white' : v === 1 ? 'bg-route text-white' : 'bg-ink text-white') : 'text-muted hover:text-ink'}`}>
                            {NIVEL_TEXTO[v]}
                          </button>
                        )
                      })}
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </fieldset>

        {error && <Aviso>{error}</Aviso>}
        <div className="flex justify-end gap-2">
          <Boton type="button" variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={guardando}>{nuevo ? 'Crear usuario' : 'Guardar cambios'}</Boton>
        </div>
      </form>
    </Modal>
  )
}

function FormClave({ usuario, onCerrar, onGuardado }: { usuario: Usuario | null; onCerrar: () => void; onGuardado: () => void }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    if (!usuario) return
    try { await api.actualizarUsuario(usuario.id, { password }); setPassword(''); setError(null); onGuardado() }
    catch (err) { setError(mensajeError(err)) }
  }
  return (
    <Modal abierto={usuario !== null} titulo={`Cambiar contraseña de ${usuario?.username ?? ''}`} onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        <Campo etiqueta="Nueva contraseña" htmlFor="c-pass" ayuda="Mínimo 8 caracteres">
          <input id="c-pass" type="password" className={claseInput} value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete="new-password" />
        </Campo>
        {error && <Aviso>{error}</Aviso>}
        <div className="flex justify-end gap-2">
          <Boton type="button" variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit">Guardar</Boton>
        </div>
      </form>
    </Modal>
  )
}
