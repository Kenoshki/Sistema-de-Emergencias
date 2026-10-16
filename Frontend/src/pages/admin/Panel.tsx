import { TrendingDown, TrendingUp } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { BarrasHorizontales, ColumnasHora, Tendencia } from '../../components/Graficas'
import { IconoIncidente } from '../../components/iconos'
import { MapaRed } from '../../components/MapaRed'
import { LeyendaMapa, SelectorVista, type VistaMapa } from '../../components/MapaZonas'
import { Aviso, Cargando, EstadoIncidente, Panel as Seccion, Prioridad, Vacio } from '../../components/ui'
import { api } from '../../lib/api'
import { describirFaltantes, hace, minutos } from '../../lib/format'
import { useDatos } from '../../lib/hooks'
import { navegar } from '../../lib/router'

const VENTANAS = [7, 30, 90]

export function Panel() {
  const [dias, setDias] = useState(30)
  const [vista, setVista] = useState<VistaMapa>('pais')
  const kpis = useDatos(() => api.kpis(dias), [dias], 60000)
  const resumen = useDatos(() => api.resumen(dias), [dias], 120000)
  const activos = useDatos(() => api.incidentes({ status: 'active', limit: 100 }), [], 15000)
  const recursos = useDatos(api.recursos, [], 15000)
  const red = useDatos(api.red)

  const k = kpis.datos
  const listaActivos = [...(activos.datos?.items ?? [])].sort((a, b) => b.priority - a.priority || a.reported_at.localeCompare(b.reported_at))

  return (
    <div className="space-y-6">
      {(kpis.error || activos.error) && <Aviso>{kpis.error || activos.error}</Aviso>}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">Indicadores de los últimos {dias} días comparados con los {dias} días anteriores.</p>
        <div className="inline-flex rounded-md border border-line bg-surface p-0.5" role="group" aria-label="Periodo">
          {VENTANAS.map((v) => (
            <button key={v} onClick={() => setDias(v)} aria-pressed={dias === v}
              className={`rounded px-3 py-1 text-sm font-medium ${dias === v ? 'bg-ink text-white' : 'text-muted hover:text-ink'}`}>
              {v} días
            </button>
          ))}
        </div>
      </div>

      {/* Franja de indicadores */}
      <section className="grid overflow-hidden rounded-lg border border-line bg-surface sm:grid-cols-2 xl:grid-cols-5" aria-label="Indicadores clave">
        {!k ? <div className="col-span-full"><Cargando /></div> : (
          <>
            <Indicador titulo="Tiempo promedio de respuesta" valor={minutos(k.avg_response_time_min)}
              cambio={k.response_time_change_pct} menorEsMejor
              detalle={`P90: ${minutos(k.p90_response_time_min)} · despacho ${minutos(k.avg_dispatch_time_min)}`} />
            <Indicador titulo="Atendidos dentro del objetivo" valor={k.target_compliance_pct === null ? '—' : `${k.target_compliance_pct}%`}
              detalle={`${k.attended_incidents} incidentes con llegada registrada`} />
            <Indicador titulo="Incidentes activos" valor={String(k.active_incidents)}
              detalle={k.critical_active ? `${k.critical_active} críticos · ${k.incidents_today} reportados hoy` : `${k.incidents_today} reportados hoy`}
              alerta={k.critical_active > 0} />
            <Indicador titulo="Flota ocupada" valor={`${k.fleet_utilization_pct}%`}
              detalle={`${k.fleet_busy} de ${k.fleet_total - k.fleet_maintenance} unidades operativas`} />
            <Indicador titulo="Lugar de mayor riesgo" valor={k.highest_risk_label ? k.highest_risk_label.split(',')[0] : '—'}
              detalle={k.highest_risk_label ? k.highest_risk_label.split(',').slice(1).join(',').trim() || ' ' : 'Sin datos en el periodo'} />
          </>
        )}
      </section>

      {/* Mapa en vivo + incidentes activos */}
      <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
        <Seccion titulo="Situación en tiempo real" accion={<SelectorVista vista={vista} onChange={setVista} />}>
          {red.datos ? (
            <>
              <MapaRed
                nodos={red.datos.nodes}
                vista={vista}
                aristas={red.datos.edges}
                incidentes={listaActivos}
                recursos={recursos.datos ?? []}
                onIncidente={(id) => navegar(`/admin/incidentes/${id}`)}
                onNodo={(n) => {
                  const nodo = red.datos?.nodes.find((x) => x.node === n)
                  if (nodo) navegar(`/admin/incidentes?municipio=${nodo.municipality_code}${nodo.kind === 'zona' ? `&zona=${n}` : ''}`)
                }}
              />
              <div className="mt-3"><LeyendaMapa /></div>
            </>
          ) : <Cargando />}
        </Seccion>

        <Seccion titulo={`Activos (${listaActivos.length})`} sinRelleno>
          {activos.cargando && !activos.datos ? <Cargando /> : listaActivos.length === 0 ? (
            <Vacio titulo="No hay incidentes activos">Los nuevos reportes aparecerán aquí.</Vacio>
          ) : (
            <ul className="max-h-[720px] divide-y divide-line overflow-y-auto">
              {listaActivos.map((i) => (
                <li key={i.id}>
                  <a href={`#/admin/incidentes/${i.id}`} className="flex gap-3 px-4 py-3 hover:bg-paper">
                    <IconoIncidente tipo={i.type} className="mt-0.5 size-5 shrink-0 text-muted" />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-semibold">{i.type_label}</span>
                        <Prioridad valor={i.priority} compacta />
                      </div>
                      <p className="text-sm text-muted">{i.location_label} · {hace(i.reported_at)}</p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-2">
                        <EstadoIncidente estado={i.status} />
                        {i.active_units.length > 0 && <span className="text-xs text-muted">{i.active_units.join(', ')}</span>}
                      </div>
                      {Object.keys(i.pending_requirements).length > 0 && (
                        <p className="mt-1 text-xs font-medium text-critical">Falta: {describirFaltantes(i.pending_requirements)}</p>
                      )}
                    </div>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </Seccion>
      </div>

      {/* Analítica */}
      {resumen.datos && (
        <>
          <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
            <Seccion titulo="Incidentes por día">
              <Tendencia datos={resumen.datos.daily_trend} />
            </Seccion>
            <Seccion titulo="Por tipo">
              <BarrasHorizontales datos={resumen.datos.by_type.map((t) => ({ etiqueta: t.label, valor: t.count }))} />
            </Seccion>
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <Seccion titulo="Índice de riesgo">
              <p className="mb-2 text-xs font-semibold text-muted">Por departamento</p>
              <BarrasHorizontales
                datos={resumen.datos.by_department.slice(0, 5).map((d) => ({
                  etiqueta: d.label, valor: d.risk_index, detalle: `${d.count} incidentes, índice ${d.risk_index}`,
                }))} />
              <p className="mb-2 mt-5 text-xs font-semibold text-muted">Por lugar</p>
              <BarrasHorizontales
                datos={resumen.datos.by_location.slice(0, 5).map((z) => ({
                  etiqueta: z.label, valor: z.risk_index, detalle: `${z.count} incidentes, índice ${z.risk_index}`,
                }))} />
              <p className="mt-3 text-xs text-muted">Suma ponderada: crítico 8, alto 4, medio 2, bajo 1.</p>
            </Seccion>
            <Seccion titulo="Hora del reporte">
              <ColumnasHora datos={resumen.datos.by_hour} />
            </Seccion>
            <Seccion titulo="Respuesta por prioridad" sinRelleno>
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr><th className="px-4 py-2 font-medium">Prioridad</th><th className="px-2 py-2 text-right font-medium">Promedio</th><th className="px-4 py-2 text-right font-medium">Objetivo</th></tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {resumen.datos.by_priority.map((p) => {
                    const cumple = p.avg_response_min !== null && p.avg_response_min <= p.target_min
                    return (
                      <tr key={p.priority}>
                        <td className="px-4 py-2.5"><Prioridad valor={p.priority} /></td>
                        <td className={`num px-2 py-2.5 text-right font-semibold ${p.avg_response_min === null ? '' : cumple ? 'text-ok' : 'text-critical'}`}>
                          {minutos(p.avg_response_min)}
                        </td>
                        <td className="num px-4 py-2.5 text-right text-muted">{p.target_min} min</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </Seccion>
          </div>
        </>
      )}
    </div>
  )
}

function Indicador({ titulo, valor, detalle, cambio, menorEsMejor = false, alerta = false }: {
  titulo: string; valor: string; detalle?: ReactNode; cambio?: number | null; menorEsMejor?: boolean; alerta?: boolean
}) {
  const mejora = cambio !== null && cambio !== undefined && (menorEsMejor ? cambio < 0 : cambio > 0)
  return (
    <div className="border-b border-line p-4 last:border-b-0 sm:border-r xl:border-b-0 xl:last:border-r-0">
      <p className="text-sm text-muted">{titulo}</p>
      <p className={`num mt-1 font-display text-4xl font-bold leading-none ${alerta ? 'text-critical' : ''}`}>{valor}</p>
      {cambio !== null && cambio !== undefined && (
        <p className={`mt-1.5 inline-flex items-center gap-1 text-xs font-semibold ${mejora ? 'text-ok' : 'text-critical'}`}>
          {cambio < 0 ? <TrendingDown className="size-3.5" aria-hidden /> : <TrendingUp className="size-3.5" aria-hidden />}
          {cambio > 0 ? '+' : ''}{cambio}% vs. periodo anterior
        </p>
      )}
      {detalle && <p className="mt-1.5 text-xs text-muted">{detalle}</p>}
    </div>
  )
}
