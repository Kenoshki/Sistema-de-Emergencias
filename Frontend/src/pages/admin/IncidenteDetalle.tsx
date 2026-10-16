import { ArrowLeft, CircleCheck, CircleX, MapPin, Phone, Radio, Send, Truck, User } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { IconoIncidente } from '../../components/iconos'
import { MapaRed } from '../../components/MapaRed'
import { SelectorVista, vistaPara, type VistaMapa } from '../../components/MapaZonas'
import { useNotificar } from '../../components/Notificaciones'
import { Aviso, Boton, Campo, Cargando, EstadoIncidente, Modal, Panel, Prioridad, claseInput } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { TIPO_RECURSO, describirFaltantes, fechaHora, hace, hora, minutos } from '../../lib/format'
import { useDatos } from '../../lib/hooks'
import { navegar } from '../../lib/router'
import type { Incidente, ResourceType } from '../../lib/types'

const ACTIVOS = ['pending', 'dispatched', 'on_scene']

export function IncidenteDetalle({ id }: { id: string }) {
  const notificar = useNotificar()
  const inc = useDatos(() => api.incidente(id), [id], 15000)
  const red = useDatos(api.red)
  const { puede } = useAuth()
  // Gestionar el incidente: módulo Incidentes (editar). Asignar unidades: también Despacho (editar).
  const gestionar = puede('incidentes', 2)
  const asignar = puede(['incidentes', 'despacho'], 2)
  const activo = inc.datos ? ACTIVOS.includes(inc.datos.status) : false
  const preview = useDatos(() => (activo ? api.vistaPrevia(id) : Promise.resolve(null)), [id, activo, inc.datos?.active_units.join()])
  const [rutaSel, setRutaSel] = useState<number | null>(null)
  const [vistaManual, setVistaManual] = useState<VistaMapa | null>(null)
  const [accion, setAccion] = useState<string | null>(null)
  const [modal, setModal] = useState<'resolver' | 'cancelar' | null>(null)
  const [texto, setTexto] = useState('')
  const [nota, setNota] = useState('')

  useEffect(() => { setRutaSel(null); setVistaManual(null) }, [id])

  const ejecutar = async (nombre: string, fn: () => Promise<Incidente>, exito: (i: Incidente) => string) => {
    setAccion(nombre)
    try {
      const r = await fn()
      inc.setDatos(r)
      notificar('success', exito(r))
      preview.recargar()
    } catch (e) {
      notificar('error', mensajeError(e))
    } finally {
      setAccion(null)
    }
  }

  if (inc.cargando && !inc.datos) return <Cargando />
  if (inc.error && !inc.datos) return <Aviso>{inc.error}</Aviso>
  const i = inc.datos!
  const asignaciones = i.assignments ?? []
  const asignacionActiva = asignaciones.filter((a) => a.active)
  const rutaMostrada = asignaciones.find((a) => a.id === rutaSel)?.route ?? asignacionActiva[0]?.route ?? []
  const faltan = Object.keys(i.pending_requirements).length > 0
  const nombreNodo = (n: number) => red.datos?.nodes.find((x) => x.node === n)?.label ?? String(n)
  const nombreCorto = (n: number) => {
    const nodo = red.datos?.nodes.find((x) => x.node === n)
    return nodo ? nodo.name : String(n)
  }
  const vista: VistaMapa = vistaManual ?? (red.datos ? vistaPara(red.datos.nodes, rutaMostrada.length ? rutaMostrada : [i.node]) : 'pais')

  return (
    <div className="space-y-5">
      <button onClick={() => navegar('/admin/incidentes')} className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> Incidentes
      </button>

      {/* Encabezado */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <span className="grid size-12 shrink-0 place-items-center rounded-lg bg-ink text-white"><IconoIncidente tipo={i.type} className="size-6" /></span>
          <div>
            <h2 className="num font-display text-3xl font-bold leading-tight">{i.id}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm">
              <span className="font-semibold">{i.type_label}</span>
              <Prioridad valor={i.priority} />
              <EstadoIncidente estado={i.status} />
              <span className="text-muted">Reportado {hace(i.reported_at)}</span>
            </div>
          </div>
        </div>
        {activo && (asignar || gestionar) && (
          <div className="flex flex-wrap gap-2">
            {faltan && asignar && (
              <Boton variante="ruta" icono={<Radio className="size-4" />} cargando={accion === 'despachar'}
                onClick={() => ejecutar('despachar', async () => (await api.despachar(i.id)).incident,
                  (r) => Object.keys(r.pending_requirements).length ? `Aún faltan: ${describirFaltantes(r.pending_requirements)}` : 'Unidades asignadas.')}>
                Buscar unidades
              </Boton>
            )}
            {i.status === 'dispatched' && gestionar && (
              <Boton icono={<Truck className="size-4" />} cargando={accion === 'llegada'}
                onClick={() => ejecutar('llegada', () => api.llegada(i.id), (r) => `Llegada registrada: ${minutos(r.response_time_min)} de respuesta.`)}>
                Marcar llegada
              </Boton>
            )}
            {gestionar && <>
              <Boton variante="secundario" icono={<CircleCheck className="size-4 text-ok" />} onClick={() => { setTexto(''); setModal('resolver') }}>Resolver</Boton>
              <Boton variante="fantasma" icono={<CircleX className="size-4" />} onClick={() => { setTexto(''); setModal('cancelar') }}>Cancelar</Boton>
            </>}
          </div>
        )}
      </div>

      {faltan && activo && (
        <Aviso>Sin unidades libres de: <strong>{describirFaltantes(i.pending_requirements)}</strong>. El incidente está en la cola de espera y se atenderá automáticamente cuando se libere una unidad.</Aviso>
      )}

      <div className="grid gap-5 xl:grid-cols-[1fr_400px]">
        <div className="space-y-5">
          {/* Datos y mapa */}
          <Panel titulo="Ubicación y ruta" accion={<SelectorVista vista={vista} onChange={setVistaManual} />}>
            <div className="mb-3 grid gap-3 text-sm sm:grid-cols-3">
              <Dato icono={<MapPin className="size-4" />} titulo={i.location_source === 'gps' ? 'Ubicación (GPS)' : 'Ubicación'}>
                {i.location_label}{i.address && <span className="block text-muted">{i.address}</span>}
              </Dato>
              <Dato icono={<User className="size-4" />} titulo="Reporta">{i.reporter_name || (i.source === 'public' ? 'Ciudadano anónimo' : 'Operador')}</Dato>
              <Dato icono={<Phone className="size-4" />} titulo="Teléfono">
                {i.reporter_phone ? <a className="text-route hover:underline" href={`tel:${i.reporter_phone}`}>{i.reporter_phone}</a> : '—'}
              </Dato>
            </div>
            {i.description && <p className="mb-3 rounded-md bg-paper px-3 py-2 text-sm">{i.description}</p>}
            {red.datos && (
              <MapaRed nodos={red.datos.nodes} vista={vista} aristas={red.datos.edges} ruta={rutaMostrada} centro={i.node} alto="h-[380px] sm:h-[460px]"
                etiquetas="completa"
                incidentes={[{ id: i.id, node: i.node, priority: i.priority, status: i.status, type_label: i.type_label }]} />
            )}
            {rutaMostrada.length > 1 && (
              <p className="mt-2 text-sm text-muted">Ruta más corta (Dijkstra): <strong className="text-ink">{rutaMostrada.map(nombreCorto).join(' → ')}</strong></p>
            )}
          </Panel>

          {/* Unidades */}
          <Panel titulo="Unidades asignadas" sinRelleno>
            {asignaciones.length === 0 ? <p className="px-4 py-6 text-sm text-muted">Todavía no se ha asignado ninguna unidad.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-sm">
                  <thead className="text-left text-xs text-muted">
                    <tr>
                      <th className="px-4 py-2 font-medium">Unidad</th><th className="px-3 py-2 font-medium">Desde</th>
                      <th className="px-3 py-2 text-right font-medium">Distancia</th><th className="px-3 py-2 text-right font-medium">ETA</th>
                      <th className="px-3 py-2 font-medium">Asignación</th><th className="px-4 py-2 font-medium">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {asignaciones.map((a) => (
                      <tr key={a.id} onClick={() => setRutaSel(a.id)}
                        className={`cursor-pointer ${rutaSel === a.id ? 'bg-route-soft' : 'hover:bg-paper'} ${a.active ? '' : 'text-muted'}`}>
                        <td className="px-4 py-2.5"><strong>{a.resource_code}</strong> <span className="text-muted">{a.resource_type_label}</span></td>
                        <td className="px-3 py-2.5">{a.origin_label}</td>
                        <td className="num px-3 py-2.5 text-right">{a.distance_km} km</td>
                        <td className="num px-3 py-2.5 text-right">{a.eta_min} min</td>
                        <td className="px-3 py-2.5">{a.method === 'auto' ? 'Automática' : 'Manual'} · <span className="num">{hora(a.assigned_at)}</span></td>
                        <td className="px-4 py-2.5">{a.active ? 'Activa' : `Liberada ${hora(a.released_at)}`}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {/* Tiempos */}
          <div className="grid gap-px overflow-hidden rounded-lg border border-line bg-line sm:grid-cols-4">
            {[
              ['Reportado', i.reported_at], ['Despachado', i.dispatched_at], ['Llegada', i.arrived_at], ['Cierre', i.resolved_at],
            ].map(([t, v]) => (
              <div key={t} className="bg-surface p-3">
                <p className="text-xs text-muted">{t}</p>
                <p className="num font-semibold">{fechaHora(v)}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-5">
          {activo && gestionar && (
            <Panel titulo="Clasificación">
              <Campo etiqueta="Prioridad" htmlFor="rep" ayuda="Al subirla se piden más unidades automáticamente.">
                <select id="rep" className={claseInput} value={i.priority} disabled={accion === 'prioridad'}
                  onChange={(e) => ejecutar('prioridad', () => api.actualizarIncidente(i.id, { priority: Number(e.target.value) }),
                    (r) => `Prioridad cambiada a ${r.priority} (${r.priority_label}).`)}>
                  {[4, 3, 2, 1].map((p) => <option key={p} value={p}>{p} – {['', 'Bajo', 'Medio', 'Alto', 'Crítico'][p]}</option>)}
                </select>
              </Campo>
            </Panel>
          )}

          {activo && preview.datos && (
            <Panel titulo="Unidades candidatas" accion={<span className="text-xs text-muted">ordenadas por distancia</span>} sinRelleno>
              <div className="divide-y divide-line">
                {(Object.entries(preview.datos.ranking) as [ResourceType, NonNullable<typeof preview.datos.ranking.ambulance>][]).map(([tipo, lista]) => (
                  <div key={tipo} className="px-4 py-3">
                    <p className="mb-2 text-sm font-semibold">{TIPO_RECURSO[tipo]}</p>
                    {lista.length === 0 ? <p className="text-sm text-muted">Ninguna disponible o alcanzable.</p> : (
                      <ul className="space-y-1.5">
                        {lista.slice(0, 4).map((c, idx) => (
                          <li key={c.codigo} className="flex items-center gap-2 text-sm">
                            <span className={`num grid size-5 place-items-center rounded text-[11px] font-bold ${idx === 0 ? 'bg-route text-white' : 'bg-paper text-muted'}`}>{idx + 1}</span>
                            <span className="min-w-0 flex-1" title={nombreNodo(c.nodo_origen)}>
                              <span className="whitespace-nowrap font-semibold">{c.codigo}</span>
                              <span className="block truncate text-xs text-muted">
                                {nombreCorto(c.nodo_origen)} · <span className="num">{c.distancia_km} km · {c.eta_min} min</span>
                              </span>
                            </span>
                            {asignar && <button className="shrink-0 rounded px-2 py-0.5 text-xs font-semibold text-route hover:bg-route-soft disabled:opacity-40"
                              disabled={accion !== null}
                              onClick={() => ejecutar(`manual-${c.codigo}`, () => api.asignarManual(i.id, c.codigo), () => `${c.codigo} asignada manualmente.`)}>
                              Asignar
                            </button>}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </Panel>
          )}

          <Panel titulo="Bitácora" sinRelleno>
            {gestionar && <form className="flex gap-2 border-b border-line p-3"
              onSubmit={(e) => { e.preventDefault(); if (nota.trim()) ejecutar('nota', () => api.nota(i.id, nota.trim()), () => 'Nota agregada.').then(() => setNota('')) }}>
              <label htmlFor="nota" className="sr-only">Agregar nota</label>
              <input id="nota" className={claseInput} placeholder="Agregar nota interna…" value={nota} maxLength={255} onChange={(e) => setNota(e.target.value)} />
              <Boton type="submit" variante="secundario" cargando={accion === 'nota'} aria-label="Guardar nota"><Send className="size-4" /></Boton>
            </form>}
            <ol className="max-h-[420px] space-y-3 overflow-y-auto p-4">
              {[...(i.events ?? [])].reverse().map((e) => (
                <li key={e.id} className="text-sm">
                  <p>{e.detail}</p>
                  <p className="num text-xs text-muted">
                    {fechaHora(e.timestamp)}{e.username ? ` · ${e.username}` : ''}{!e.public ? ' · interno' : ''}
                  </p>
                </li>
              ))}
            </ol>
          </Panel>
        </div>
      </div>

      <Modal abierto={modal !== null} titulo={modal === 'resolver' ? 'Resolver incidente' : 'Cancelar incidente'} onCerrar={() => setModal(null)}>
        <form className="space-y-4" onSubmit={(e) => {
          e.preventDefault()
          const tipo = modal
          setModal(null)
          ejecutar(tipo!, async () => {
            const r = tipo === 'resolver' ? await api.resolver(i.id, texto) : await api.cancelar(i.id, texto)
            if (r.queue_dispatched.length) {
              notificar('alert', `Unidades liberadas reasignadas a: ${r.queue_dispatched.map((q) => q.incidente_id).join(', ')}`)
            }
            return r.incident
          }, () => (tipo === 'resolver' ? 'Incidente resuelto y unidades liberadas.' : 'Incidente cancelado.'))
        }}>
          <p className="text-sm text-muted">
            {modal === 'resolver'
              ? 'Las unidades quedarán disponibles en la zona del incidente y atenderán la cola de espera si hay incidentes pendientes.'
              : 'Use esta opción para falsas alarmas o reportes duplicados.'}
          </p>
          <Campo etiqueta={modal === 'resolver' ? 'Nota de cierre (opcional)' : 'Motivo'} htmlFor="txt">
            <input id="txt" className={claseInput} value={texto} maxLength={200} onChange={(e) => setTexto(e.target.value)} />
          </Campo>
          <div className="flex justify-end gap-2">
            <Boton type="button" variante="secundario" onClick={() => setModal(null)}>Volver</Boton>
            <Boton type="submit" variante={modal === 'resolver' ? 'primario' : 'peligro'}>
              {modal === 'resolver' ? 'Resolver' : 'Cancelar incidente'}
            </Boton>
          </div>
        </form>
      </Modal>
    </div>
  )
}

function Dato({ icono, titulo, children }: { icono: ReactNode; titulo: string; children: ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="mt-0.5 text-muted">{icono}</span>
      <div><p className="text-xs text-muted">{titulo}</p><div className="font-medium">{children}</div></div>
    </div>
  )
}
