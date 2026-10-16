import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { IconoIncidente } from '../../components/iconos'
import { Aviso, Cargando, EstadoIncidente, Prioridad, Vacio, claseInput } from '../../components/ui'
import { api } from '../../lib/api'
import { describirFaltantes, fechaHora, minutos } from '../../lib/format'
import { useDatos } from '../../lib/hooks'
import { navegar } from '../../lib/router'

const POR_PAGINA = 25

function parametrosIniciales(ruta: string) {
  const q = new URLSearchParams(ruta.split('?')[1] ?? '')
  return { municipio: q.get('municipio') ?? '', zona: q.get('zona') ?? '', estado: q.get('estado') ?? 'active' }
}

export function Incidentes({ ruta }: { ruta: string }) {
  const inicial = parametrosIniciales(ruta)
  const [estado, setEstado] = useState(inicial.estado)
  const [tipo, setTipo] = useState('')
  const [departamento, setDepartamento] = useState(inicial.municipio ? inicial.municipio.slice(0, 2) : '')
  const [municipio, setMunicipio] = useState(inicial.municipio)
  const [zona, setZona] = useState(inicial.zona)
  const [prioridad, setPrioridad] = useState('')
  const [texto, setTexto] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [pagina, setPagina] = useState(0)

  useEffect(() => {
    const t = window.setTimeout(() => setBusqueda(texto), 350)
    return () => window.clearTimeout(t)
  }, [texto])
  useEffect(() => setPagina(0), [estado, tipo, departamento, municipio, zona, prioridad, busqueda])

  const { datos: cat } = useDatos(api.catalogos)
  const municipios = cat?.municipalities.filter((m) => m.department === departamento) ?? []
  const zonas = cat?.municipalities.find((m) => m.value === municipio)?.zones ?? null
  const { datos, error, cargando } = useDatos(
    () => api.incidentes({
      status: estado || undefined, type: tipo || undefined, department: departamento || undefined,
      municipality: municipio || undefined, zone: zona || undefined,
      priority: prioridad || undefined, q: busqueda || undefined, limit: POR_PAGINA, offset: pagina * POR_PAGINA,
    }),
    [estado, tipo, departamento, municipio, zona, prioridad, busqueda, pagina],
    20000,
  )
  const total = datos?.total ?? 0
  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA))

  return (
    <div className="space-y-4">
      <div className="grid gap-3 rounded-lg border border-line bg-surface p-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="relative">
          <span className="sr-only">Buscar</span>
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <input className={`${claseInput} pl-9`} placeholder="Buscar código, descripción o dirección"
            value={texto} onChange={(e) => setTexto(e.target.value)} />
        </label>
        <select aria-label="Estado" className={claseInput} value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="active">Activos</option>
          <option value="">Todos los estados</option>
          {cat?.statuses.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
        <select aria-label="Tipo" className={claseInput} value={tipo} onChange={(e) => setTipo(e.target.value)}>
          <option value="">Todos los tipos</option>
          {cat?.incident_types.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <select aria-label="Departamento" className={claseInput} value={departamento}
          onChange={(e) => { setDepartamento(e.target.value); setMunicipio(''); setZona('') }}>
          <option value="">Todos los departamentos</option>
          {cat?.departments.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>
        <select aria-label="Municipio" className={claseInput} value={municipio} disabled={!departamento}
          onChange={(e) => { setMunicipio(e.target.value); setZona('') }}>
          <option value="">{departamento ? 'Todos los municipios' : 'Municipio (elija departamento)'}</option>
          {municipios.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
        <select aria-label="Zona" className={claseInput} value={zona} disabled={!zonas} onChange={(e) => setZona(e.target.value)}>
          <option value="">{zonas ? 'Todas las zonas' : 'Zona (no aplica)'}</option>
          {zonas?.map((z) => <option key={z.value} value={z.value}>{z.label}</option>)}
        </select>
        <select aria-label="Prioridad" className={claseInput} value={prioridad} onChange={(e) => setPrioridad(e.target.value)}>
          <option value="">Todas las prioridades</option>
          {cat?.priorities.map((p) => <option key={p.value} value={p.value}>{p.value} – {p.label}</option>)}
        </select>
      </div>

      {error && <Aviso>{error}</Aviso>}

      <div className="overflow-hidden rounded-lg border border-line bg-surface">
        {cargando && !datos ? <Cargando /> : !datos?.items.length ? (
          <Vacio titulo="No hay incidentes con estos filtros">Cambie los filtros o elija "Todos los estados".</Vacio>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-sm">
              <thead className="border-b border-line bg-paper/60 text-left text-xs text-muted">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Código</th>
                  <th className="px-3 py-2.5 font-medium">Tipo</th>
                  <th className="px-3 py-2.5 font-medium">Prioridad</th>
                  <th className="px-3 py-2.5 font-medium">Ubicación</th>
                  <th className="px-3 py-2.5 font-medium">Estado</th>
                  <th className="px-3 py-2.5 font-medium">Unidades</th>
                  <th className="px-3 py-2.5 font-medium">Reportado</th>
                  <th className="px-4 py-2.5 text-right font-medium">Respuesta</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {datos.items.map((i) => (
                  <tr key={i.id} className="cursor-pointer hover:bg-paper" onClick={() => navegar(`/admin/incidentes/${i.id}`)}>
                    <td className="num whitespace-nowrap px-4 py-2.5 font-semibold">
                      <a href={`#/admin/incidentes/${i.id}`} onClick={(e) => e.stopPropagation()} className="hover:underline">{i.id}</a>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-2"><IconoIncidente tipo={i.type} className="size-4 text-muted" />{i.type_label}</span>
                    </td>
                    <td className="px-3 py-2.5"><Prioridad valor={i.priority} /></td>
                    <td className="max-w-[220px] px-3 py-2.5">{i.location_label}</td>
                    <td className="px-3 py-2.5"><EstadoIncidente estado={i.status} /></td>
                    <td className="px-3 py-2.5 text-xs">
                      {i.active_units.join(', ') || <span className="text-muted">—</span>}
                      {Object.keys(i.pending_requirements).length > 0 && (
                        <span className="block font-medium text-critical">Falta {describirFaltantes(i.pending_requirements)}</span>
                      )}
                    </td>
                    <td className="num whitespace-nowrap px-3 py-2.5 text-muted">{fechaHora(i.reported_at)}</td>
                    <td className="num px-4 py-2.5 text-right">{minutos(i.response_time_min)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {total > 0 && (
          <div className="flex items-center justify-between border-t border-line px-4 py-2.5 text-sm text-muted">
            <span className="num">{total} incidentes · página {pagina + 1} de {paginas}</span>
            <div className="flex gap-1">
              <button className="rounded p-1.5 hover:bg-paper disabled:opacity-40" disabled={pagina === 0} onClick={() => setPagina(pagina - 1)} aria-label="Página anterior"><ChevronLeft className="size-4" /></button>
              <button className="rounded p-1.5 hover:bg-paper disabled:opacity-40" disabled={pagina + 1 >= paginas} onClick={() => setPagina(pagina + 1)} aria-label="Página siguiente"><ChevronRight className="size-4" /></button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
