import { Hourglass, ListOrdered, Shuffle } from 'lucide-react'
import { useState } from 'react'
import { IconoIncidente } from '../../components/iconos'
import { useNotificar } from '../../components/Notificaciones'
import { Aviso, Boton, Cargando, EstadoRecurso, Panel, Prioridad, Vacio } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { TIPO_RECURSO, describirFaltantes } from '../../lib/format'
import { useDatos } from '../../lib/hooks'
import type { IncidentType, Recurso, ResourceType } from '../../lib/types'

const TIPOS: IncidentType[] = ['fire', 'accident', 'collapse', 'landslide', 'medical', 'robbery']
const azar = <T,>(l: T[]) => l[Math.floor(Math.random() * l.length)]

/** Módulo de despacho: cola de prioridad y tablero de la flota. */
export function Despacho() {
  const { puede } = useAuth()
  const editar = puede(['despacho', 'incidentes'], 2)
  const notificar = useNotificar()
  const cola = useDatos(api.cola, [], 10000)
  const { datos: cat } = useDatos(api.catalogos)
  const [depto, setDepto] = useState('')
  const recursos = useDatos(api.recursos, [], 10000)
  const [procesando, setProcesando] = useState(false)
  const [simulando, setSimulando] = useState(false)

  const procesar = async () => {
    setProcesando(true)
    try {
      const r = await api.procesarCola()
      notificar(r.dispatched.length ? 'success' : 'alert',
        r.dispatched.length ? `Se asignaron unidades a ${r.dispatched.length} incidente(s).` : 'No hay unidades libres para la cola por ahora.')
      cola.recargar(); recursos.recargar()
    } catch (e) { notificar('error', mensajeError(e)) } finally { setProcesando(false) }
  }

  const simular = async () => {
    setSimulando(true)
    try {
      if (!cat) return
      const prioridad = azar([2, 3, 3, 4])
      // La mitad de los simulacros ocurre en la capital; el resto en cualquier municipio del país.
      const muni = Math.random() < 0.5 ? cat.municipalities.find((m) => m.value === '0101')! : azar(cat.municipalities)
      const zona = muni.zones ? azar(muni.zones).value : null
      const inc = await api.crearIncidente({
        type: azar(TIPOS), priority: prioridad, department_code: muni.department, municipality_code: muni.value, zone: zona,
        description: 'Simulacro generado desde el módulo de despacho',
      })
      const faltan = describirFaltantes(inc.pending_requirements)
      notificar(faltan ? 'alert' : 'success',
        `Simulacro ${inc.id} (${inc.type_label}, ${inc.location_label}). ${inc.active_units.length ? `Asignadas: ${inc.active_units.join(', ')}.` : ''}${faltan ? ` En cola, falta: ${faltan}.` : ''}`)
      cola.recargar(); recursos.recargar()
    } catch (e) { notificar('error', mensajeError(e)) } finally { setSimulando(false) }
  }

  const porTipo: Record<string, Recurso[]> = {}
  for (const r of recursos.datos ?? []) if (!depto || r.department_code === depto) (porTipo[r.type] ??= []).push(r)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-muted">
          Cada reporte se despacha solo: el sistema calcula con Dijkstra la distancia de todas las unidades libres y envía las más cercanas.
          Si faltan unidades, el incidente entra a la cola de prioridad.
        </p>
        {editar && <Boton variante="secundario" icono={<Shuffle className="size-4" />} cargando={simulando} disabled={!cat} onClick={simular}>Generar simulacro</Boton>}
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
        <Panel
          titulo={<span className="inline-flex items-center gap-2"><ListOrdered className="size-5" aria-hidden /> Cola de espera</span>}
          accion={editar && <Boton variante="ruta" onClick={procesar} cargando={procesando} disabled={!cola.datos?.length}>Procesar cola</Boton>}
          sinRelleno
        >
          {cola.error && <div className="p-4"><Aviso>{cola.error}</Aviso></div>}
          {cola.cargando && !cola.datos ? <Cargando /> : !cola.datos?.length ? (
            <Vacio titulo="Nadie está esperando">Todos los incidentes activos tienen sus unidades asignadas.</Vacio>
          ) : (
            <ol className="divide-y divide-line">
              {cola.datos.map((c) => (
                <li key={c.incidente_id}>
                  <a href={`#/admin/incidentes/${c.incidente_id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-paper">
                    <span className="num grid size-8 shrink-0 place-items-center rounded-md bg-ink font-display text-lg font-bold text-white">{c.posicion}</span>
                    <IconoIncidente tipo={c.tipo} className="size-5 shrink-0 text-muted" />
                    <div className="min-w-0 flex-1">
                      <p className="num truncate text-sm font-semibold">{c.incidente_id}</p>
                      <p className="text-xs text-muted">{c.ubicacion} · falta {describirFaltantes(c.faltantes)}</p>
                    </div>
                    <div className="text-right">
                      <Prioridad valor={c.prioridad} compacta />
                      <p className="num mt-1 text-xs text-muted" title="Prioridad + bono por tiempo de espera (máx. +1)">
                        efectiva {c.prioridad_efectiva.toFixed(2)}
                      </p>
                    </div>
                    <span className="num hidden w-16 shrink-0 items-center justify-end gap-1 text-xs text-muted sm:flex">
                      <Hourglass className="size-3.5" aria-hidden />{Math.round(c.minutos_espera)} min
                    </span>
                  </a>
                </li>
              ))}
            </ol>
          )}
          <p className="border-t border-line px-4 py-3 text-xs text-muted">
            Orden: mayor prioridad efectiva primero (montículo binario). Cada 30 minutos de espera suman 1 punto, hasta un máximo de 1, para que ningún incidente espere indefinidamente.
          </p>
        </Panel>

        <Panel titulo="Tablero de flota" sinRelleno accion={
          <select aria-label="Departamento" className="rounded-md border border-line bg-surface px-2 py-1 text-sm" value={depto} onChange={(e) => setDepto(e.target.value)}>
            <option value="">Todo el país</option>
            {cat?.departments.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
          </select>
        }>
          {recursos.cargando && !recursos.datos ? <Cargando /> : (
            <div className="grid sm:grid-cols-2">
              {(Object.keys(TIPO_RECURSO) as ResourceType[]).map((tipo) => {
                const lista = porTipo[tipo] ?? []
                const libres = lista.filter((r) => r.status === 'available').length
                return (
                  <div key={tipo} className="border-b border-line p-4 sm:odd:border-r">
                    <div className="mb-2 flex items-baseline justify-between">
                      <h3 className="font-display text-lg font-semibold">{TIPO_RECURSO[tipo]}</h3>
                      <span className={`num text-sm font-semibold ${libres ? 'text-ok' : 'text-critical'}`}>{libres}/{lista.length} libres</span>
                    </div>
                    <ul className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
                      {lista.map((r) => (
                        <li key={r.code} className="flex items-center justify-between gap-2 text-sm">
                          <span className="min-w-0 truncate" title={r.current_label}><strong>{r.code}</strong> <span className="text-muted">{r.current_label.replace(', Ciudad de Guatemala', '')}</span></span>
                          {r.incident_id
                            ? <a href={`#/admin/incidentes/${r.incident_id}`} className="hover:underline"><EstadoRecurso estado={r.status} /></a>
                            : <EstadoRecurso estado={r.status} />}
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              })}
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
