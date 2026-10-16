import { Pencil, Plus, Trash2, Undo2, Wrench } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useNotificar } from '../../components/Notificaciones'
import { SelectorUbicacion, UBICACION_VACIA, validarUbicacion } from '../../components/SelectorUbicacion'
import { Aviso, Boton, Campo, Cargando, EstadoRecurso, Modal, claseInput } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { TIPO_RECURSO, hace } from '../../lib/format'
import { useDatos } from '../../lib/hooks'
import type { Catalogos, Recurso, ResourceType, UbicacionForm } from '../../lib/types'

export function Flota() {
  const { puede } = useAuth()
  const editar = puede('flota', 2)
  const notificar = useNotificar()
  const recursos = useDatos(api.recursos, [], 15000)
  const { datos: cat } = useDatos(api.catalogos)
  const [filtro, setFiltro] = useState<ResourceType | ''>('')
  const [depto, setDepto] = useState('')
  const [editando, setEditando] = useState<Recurso | 'nuevo' | null>(null)
  const [ocupado, setOcupado] = useState<string | null>(null)

  const accion = async (code: string, fn: () => Promise<unknown>, ok: string) => {
    setOcupado(code)
    try { await fn(); notificar('success', ok); recursos.recargar() }
    catch (e) { notificar('error', mensajeError(e)) }
    finally { setOcupado(null) }
  }

  const lista = (recursos.datos ?? []).filter((r) => (!filtro || r.type === filtro) && (!depto || r.department_code === depto))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex flex-wrap rounded-md border border-line bg-surface p-0.5" role="group" aria-label="Filtrar por tipo">
          {([['', 'Todas'], ...Object.entries(TIPO_RECURSO)] as [ResourceType | '', string][]).map(([v, l]) => (
            <button key={v} onClick={() => setFiltro(v)} aria-pressed={filtro === v}
              className={`rounded px-3 py-1 text-sm font-medium ${filtro === v ? 'bg-ink text-white' : 'text-muted hover:text-ink'}`}>{l}</button>
          ))}
        </div>
        <select aria-label="Departamento" className="rounded-md border border-line bg-surface px-3 py-1.5 text-sm" value={depto} onChange={(e) => setDepto(e.target.value)}>
          <option value="">Todo el país</option>
          {cat?.departments.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>
        <span className="num text-sm text-muted">{lista.length} unidades</span>
        {editar && <Boton className="ml-auto" icono={<Plus className="size-4" />} onClick={() => setEditando('nuevo')}>Agregar unidad</Boton>}
      </div>

      {recursos.error && <Aviso>{recursos.error}</Aviso>}
      <div className="overflow-hidden rounded-lg border border-line bg-surface">
        {recursos.cargando && !recursos.datos ? <Cargando /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead className="border-b border-line bg-paper/60 text-left text-xs text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Código</th><th className="px-3 py-2.5 font-medium">Nombre</th>
                  <th className="px-3 py-2.5 font-medium">Base</th><th className="px-3 py-2.5 font-medium">Ubicación actual</th>
                  <th className="px-3 py-2.5 font-medium">Estado</th><th className="px-3 py-2.5 font-medium">Actualizado</th>
                  <th className="px-4 py-2.5 text-right font-medium">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {lista.map((r) => (
                  <tr key={r.code}>
                    <td className="px-4 py-2.5 font-semibold">{r.code}<span className="block text-xs font-normal text-muted">{r.type_label}</span></td>
                    <td className="px-3 py-2.5">{r.name}</td>
                    <td className="px-3 py-2.5">{r.base_label}</td>
                    <td className="px-3 py-2.5">
                      {r.current_node === r.base_node ? <span className="text-muted">En base</span> : r.current_label}
                    </td>
                    <td className="px-3 py-2.5">
                      <EstadoRecurso estado={r.status} />
                      {r.incident_id && <a href={`#/admin/incidentes/${r.incident_id}`} className="num mt-0.5 block text-xs text-route hover:underline">{r.incident_id}</a>}
                    </td>
                    <td className="px-3 py-2.5 text-muted">{hace(r.updated_at)}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-1">
                        {!editar && <span className="text-xs text-muted">Solo lectura</span>}
                        {editar && r.status === 'available' && r.current_node !== r.base_node && (
                          <IconoAccion titulo="Regresar a base" onClick={() => accion(r.code, () => api.retornarBase(r.code), `${r.code} regresó a su base.`)} deshabilitado={ocupado === r.code}><Undo2 className="size-4" /></IconoAccion>
                        )}
                        {editar && (r.status === 'available' || r.status === 'maintenance') && (
                          <IconoAccion titulo={r.status === 'maintenance' ? 'Marcar disponible' : 'Enviar a mantenimiento'} deshabilitado={ocupado === r.code}
                            onClick={() => accion(r.code, () => api.actualizarRecurso(r.code, { status: r.status === 'maintenance' ? 'available' : 'maintenance' }),
                              r.status === 'maintenance' ? `${r.code} vuelve a estar disponible.` : `${r.code} en mantenimiento.`)}>
                            <Wrench className={`size-4 ${r.status === 'maintenance' ? 'text-ok' : ''}`} />
                          </IconoAccion>
                        )}
                        {editar && <IconoAccion titulo="Editar" onClick={() => setEditando(r)}><Pencil className="size-4" /></IconoAccion>}
                        {editar && (
                          <IconoAccion titulo="Eliminar" deshabilitado={ocupado === r.code}
                            onClick={() => { if (window.confirm(`¿Eliminar la unidad ${r.code}?`)) accion(r.code, () => api.eliminarRecurso(r.code), `${r.code} eliminada.`) }}>
                            <Trash2 className="size-4 text-critical" />
                          </IconoAccion>
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

      <FormRecurso recurso={editando} cat={cat} onCerrar={() => setEditando(null)}
        onGuardado={(msg) => { setEditando(null); notificar('success', msg); recursos.recargar() }} />
    </div>
  )
}

function IconoAccion({ titulo, onClick, deshabilitado, children }: { titulo: string; onClick: () => void; deshabilitado?: boolean; children: ReactNode }) {
  return (
    <button title={titulo} aria-label={titulo} onClick={onClick} disabled={deshabilitado}
      className="rounded p-1.5 text-muted hover:bg-paper hover:text-ink disabled:opacity-40">{children}</button>
  )
}

function FormRecurso({ recurso, cat, onCerrar, onGuardado }: {
  recurso: Recurso | 'nuevo' | null; cat: Catalogos | null; onCerrar: () => void; onGuardado: (m: string) => void
}) {
  const nuevo = recurso === 'nuevo'
  const r = recurso && recurso !== 'nuevo' ? recurso : null
  const [code, setCode] = useState('')
  const [tipo, setTipo] = useState<ResourceType>('ambulance')
  const [nombre, setNombre] = useState('')
  const [base, setBase] = useState<UbicacionForm>(UBICACION_VACIA)
  const [intento, setIntento] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [guardando, setGuardando] = useState(false)
  const [abiertoPara, setAbiertoPara] = useState<string | null>(null)

  const clave = r?.code ?? (nuevo ? 'nuevo' : null)
  if (clave !== abiertoPara) {
    setAbiertoPara(clave)
    setError(null)
    setCode(r?.code ?? '')
    setTipo(r?.type ?? 'ambulance')
    setNombre(r?.name ?? '')
    setIntento(false)
    setBase(r ? {
      ...UBICACION_VACIA, department_code: r.base_department_code ?? '',
      municipality_code: r.base_municipality_code, zone: r.base_zone,
    } : UBICACION_VACIA)
  }

  const guardar = async (e: FormEvent) => {
    e.preventDefault()
    setIntento(true)
    if (Object.keys(validarUbicacion(base, cat)).length) {
      setError('Complete la base: departamento, municipio y zona si aplica.')
      return
    }
    setGuardando(true)
    setError(null)
    const datosBase = {
      base_department_code: base.department_code, base_municipality_code: base.municipality_code, base_zone: base.zone,
    }
    try {
      if (nuevo) {
        await api.crearRecurso({ code: code.trim().toUpperCase(), type: tipo, name: nombre.trim(), ...datosBase })
        onGuardado(`Unidad ${code.toUpperCase()} agregada.`)
      } else if (r) {
        await api.actualizarRecurso(r.code, { name: nombre.trim(), ...datosBase })
        onGuardado(`Unidad ${r.code} actualizada.`)
      }
    } catch (err) { setError(mensajeError(err)) } finally { setGuardando(false) }
  }

  return (
    <Modal abierto={recurso !== null} titulo={nuevo ? 'Agregar unidad' : `Editar ${r?.code ?? ''}`} onCerrar={onCerrar}>
      <form onSubmit={guardar} className="space-y-4">
        {nuevo && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Campo etiqueta="Código" htmlFor="r-code" ayuda="Mayúsculas, números y guion. Ej. AMB-07">
              <input id="r-code" className={`${claseInput} uppercase`} value={code} onChange={(e) => setCode(e.target.value)} required maxLength={20} />
            </Campo>
            <Campo etiqueta="Tipo" htmlFor="r-tipo">
              <select id="r-tipo" className={claseInput} value={tipo} onChange={(e) => setTipo(e.target.value as ResourceType)}>
                {Object.entries(TIPO_RECURSO).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Campo>
          </div>
        )}
        <Campo etiqueta="Nombre" htmlFor="r-nom">
          <input id="r-nom" className={claseInput} value={nombre} onChange={(e) => setNombre(e.target.value)} required maxLength={100} />
        </Campo>
        <fieldset>
          <legend className="mb-2 text-sm font-semibold">Base de la unidad</legend>
          {cat && <SelectorUbicacion valor={base} onChange={setBase} cat={cat} conLugar={false} idPrefijo="base"
            errores={intento ? validarUbicacion(base, cat) : {}} />}
        </fieldset>
        {error && <Aviso>{error}</Aviso>}
        <div className="flex justify-end gap-2">
          <Boton type="button" variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" cargando={guardando}>Guardar</Boton>
        </div>
      </form>
    </Modal>
  )
}
