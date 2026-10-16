import { Check, Construction, RotateCcw, X } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { MapaRed } from '../../components/MapaRed'
import { LeyendaMapa, SelectorVista, type VistaMapa } from '../../components/MapaZonas'
import { useNotificar } from '../../components/Notificaciones'
import { Aviso, Boton, Campo, Cargando, Modal, Panel, claseInput } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { fechaHora } from '../../lib/format'
import { useDatos } from '../../lib/hooks'
import type { Arista, Nodo, ResultadoRuta } from '../../lib/types'

/** Red vial: calculadora de rutas (Dijkstra) y cierre de vías. */
export function RedVial() {
  const notificar = useNotificar()
  const editar = useAuth().puede('red', 2)
  const red = useDatos(api.red)
  const [origen, setOrigen] = useState<number | null>(null)
  const [destino, setDestino] = useState<number | null>(null)
  const [resultado, setResultado] = useState<ResultadoRuta | null>(null)
  const [calculando, setCalculando] = useState(false)
  const [cerrando, setCerrando] = useState<Arista | null>(null)
  const [motivo, setMotivo] = useState('')
  const [verPasos, setVerPasos] = useState(false)
  const [vista, setVista] = useState<VistaMapa>('pais')
  const { datos: cat } = useDatos(api.catalogos)

  // Nodos agrupados por departamento para los selectores de origen y destino.
  const grupos = useMemo(() => {
    if (!red.datos || !cat) return []
    return cat.departments.map((d) => ({
      depto: d.label,
      nodos: red.datos!.nodes.filter((n) => n.department_code === d.value)
        .sort((a, b) => (a.kind === b.kind ? (a.kind === 'zona' ? a.node - b.node : a.name.localeCompare(b.name)) : a.kind === 'zona' ? -1 : 1)),
    }))
  }, [red.datos, cat])

  const calcular = async (o: number, d: number) => {
    setCalculando(true)
    try { setResultado(await api.ruta(o, d)) }
    catch (e) { notificar('error', mensajeError(e)) }
    finally { setCalculando(false) }
  }

  const elegir = (o: number | null, d: number | null) => {
    setOrigen(o); setDestino(d); setResultado(null)
    if (o !== null && d !== null && o !== d) calcular(o, d)
  }

  const alElegirNodo = (z: number) => {
    if (origen === null || (origen !== null && destino !== null)) {
      setOrigen(z); setDestino(null); setResultado(null)
    } else if (z !== origen) {
      setDestino(z); calcular(origen, z)
    }
  }

  const limpiar = () => { setOrigen(null); setDestino(null); setResultado(null) }

  const cerrarVia = async (e: FormEvent) => {
    e.preventDefault()
    if (!cerrando) return
    try {
      await api.cerrarVia(cerrando.origen, cerrando.destino, motivo)
      notificar('alert', `Vía ${nombre(cerrando.origen)} ↔ ${nombre(cerrando.destino)} cerrada. Las rutas nuevas la evitarán.`)
      setCerrando(null); setMotivo('')
      await red.recargar()
      if (origen !== null && destino !== null) calcular(origen, destino)
    } catch (err) { notificar('error', mensajeError(err)) }
  }

  const reabrir = async (id: number) => {
    try {
      await api.reabrirVia(id)
      notificar('success', 'Vía reabierta.')
      await red.recargar()
      if (origen !== null && destino !== null) calcular(origen, destino)
    } catch (err) { notificar('error', mensajeError(err)) }
  }

  const nombre = (z: number) => red.datos?.nodes.find((n) => n.node === z)?.label ?? String(z)

  if (red.cargando && !red.datos) return <Cargando />
  if (red.error && !red.datos) return <Aviso>{red.error}</Aviso>
  const datos = red.datos!

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
      <Panel titulo="Mapa de la red vial" accion={<SelectorVista vista={vista} onChange={setVista} />}>
        <p className="mb-3 text-sm text-muted">
          <span className="num">{datos.nodes.length}</span> puntos (22 zonas de la capital y 339 municipios) y <span className="num">{datos.edges.length}</span> conexiones.
          Toque un punto para elegir el <strong className="text-ink">origen</strong> y otro para el <strong className="text-ink">destino</strong>,
          o use las listas.{editar && <> Toque una línea para cerrar esa vía.</>}
        </p>
        <MapaRed
          nodos={datos.nodes}
          vista={vista}
          aristas={datos.edges}
          ruta={resultado?.camino ?? []}
          seleccion={[origen, destino].filter((z): z is number => z !== null)}
          ordenVisita={verPasos ? resultado?.orden_visita : undefined}
          onNodo={alElegirNodo}
          onArista={editar ? (a) => (a.cerrada ? notificar('alert', 'Esa vía ya está cerrada. Reábrala desde la lista.') : setCerrando(a)) : undefined}
          mostrarRed
          etiquetas="completa"
        />
        <div className="mt-3"><LeyendaMapa conRecursos={false} conIncidentes={false} /></div>
        {!datos.connected && <div className="mt-3"><Aviso>Hay lugares aislados: no existe ruta hacia ellos con las vías cerradas actuales.</Aviso></div>}
      </Panel>

      <div className="space-y-6">
        <Panel titulo="Ruta más corta" accion={(origen !== null) && <Boton variante="fantasma" onClick={limpiar} icono={<RotateCcw className="size-4" />}>Limpiar</Boton>}>
          <div className="mb-4 grid gap-3">
            <SelectorNodo id="r-origen" etiqueta="Origen" grupos={grupos} valor={origen} onChange={(v) => elegir(v, destino)} />
            <SelectorNodo id="r-destino" etiqueta="Destino" grupos={grupos} valor={destino} onChange={(v) => elegir(origen, v)} />
          </div>
          {origen === null ? (
            <p className="text-sm text-muted">Elija el origen en la lista o en el mapa.</p>
          ) : destino === null ? (
            <p className="text-sm">Ahora elija el destino.</p>
          ) : calculando ? <Cargando texto="Ejecutando Dijkstra…" /> : resultado && (
            <div className="space-y-4">
              {resultado.alcanzable ? (
                <>
                  <div>
                    <p className="text-sm text-muted">{resultado.origen_label} → {resultado.destino_label}</p>
                    <p className="num font-display text-4xl font-bold">{resultado.distancia_km} km</p>
                  </div>
                  <ol className="max-h-64 space-y-1.5 overflow-y-auto text-sm">
                    {resultado.tramos.map((t, idx) => (
                      <li key={idx} className="flex justify-between gap-2">
                        <span>{corto(t.desde_label)} → {corto(t.hasta_label)}</span>
                        <span className="num shrink-0 whitespace-nowrap text-muted">{t.distancia_km} km</span>
                      </li>
                    ))}
                  </ol>
                  <p className={`flex items-center gap-1.5 text-sm font-medium ${resultado.verificacion_networkx.coincide ? 'text-ok' : 'text-critical'}`}>
                    {resultado.verificacion_networkx.coincide ? <Check className="size-4" /> : <X className="size-4" />}
                    {resultado.verificacion_networkx.coincide
                      ? `NetworkX obtiene la misma distancia (${resultado.verificacion_networkx.distancia_km} km)`
                      : 'NetworkX obtuvo una distancia distinta'}
                  </p>
                </>
              ) : <Aviso>No hay ruta: el destino está aislado por vías cerradas.</Aviso>}

              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={verPasos} onChange={(e) => setVerPasos(e.target.checked)} className="size-4 accent-[#0d7280]" />
                Mostrar el orden en que Dijkstra fijó cada punto
              </label>
              {verPasos && (
                <div className="max-h-56 overflow-y-auto rounded-md border border-line">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-paper text-left text-xs text-muted">
                      <tr><th className="px-3 py-1.5 font-medium">Paso</th><th className="px-3 py-1.5 font-medium">Lugar</th><th className="px-3 py-1.5 text-right font-medium">Distancia desde origen</th></tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {resultado.orden_visita.slice(0, 120).map((z, idx) => (
                        <tr key={z} className={resultado.camino.includes(z) ? 'bg-route-soft' : ''}>
                          <td className="num px-3 py-1.5">{idx + 1}</td>
                          <td className="px-3 py-1.5">{nombre(z)}</td>
                          <td className="num px-3 py-1.5 text-right">{resultado.distancias_desde_origen[String(z)] ?? '∞'} km</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </Panel>

        <Panel titulo={<span className="inline-flex items-center gap-2"><Construction className="size-5" aria-hidden /> Vías cerradas</span>} sinRelleno>
          {datos.closures.length === 0 ? (
            <p className="px-4 py-5 text-sm text-muted">Todas las vías están habilitadas. {editar ? 'Para simular un deslave o bloqueo, toque una conexión en el mapa.' : ''}</p>
          ) : (
            <ul className="divide-y divide-line">
              {datos.closures.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                  <div>
                    <p className="font-semibold">{c.label_a} ↔ {c.label_b}</p>
                    <p className="text-xs text-muted">{c.reason || 'Sin motivo'} · {fechaHora(c.created_at)}{c.created_by ? ` · ${c.created_by}` : ''}</p>
                  </div>
                  {editar && <Boton variante="secundario" onClick={() => reabrir(c.id)}>Reabrir</Boton>}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Modal abierto={cerrando !== null} titulo="Cerrar vía" onCerrar={() => setCerrando(null)}>
        {cerrando && (
          <form onSubmit={cerrarVia} className="space-y-4">
            <p className="text-sm">
              Conexión <strong>{nombre(cerrando.origen)}</strong> ↔ <strong>{nombre(cerrando.destino)}</strong> ({cerrando.distancia_km} km).
              Las unidades nuevas tomarán rutas alternas.
            </p>
            <Campo etiqueta="Motivo" htmlFor="motivo">
              <input id="motivo" className={claseInput} value={motivo} maxLength={200} onChange={(e) => setMotivo(e.target.value)}
                placeholder="Deslave, inundación, manifestación…" autoFocus />
            </Campo>
            <div className="flex justify-end gap-2">
              <Boton type="button" variante="secundario" onClick={() => setCerrando(null)}>Volver</Boton>
              <Boton type="submit" variante="peligro">Cerrar vía</Boton>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}

function corto(etiqueta: string) {
  return etiqueta.replace(', Ciudad de Guatemala', '')
}

function SelectorNodo({ id, etiqueta, grupos, valor, onChange }: {
  id: string; etiqueta: string; grupos: { depto: string; nodos: Nodo[] }[]; valor: number | null; onChange: (v: number | null) => void
}) {
  return (
    <Campo etiqueta={etiqueta} htmlFor={id}>
      <select id={id} className={claseInput} value={valor ?? ''} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">Seleccione…</option>
        {grupos.map((g) => (
          <optgroup key={g.depto} label={g.depto}>
            {g.nodos.map((n) => <option key={n.node} value={n.node}>{n.kind === 'zona' ? `${n.name} (capital)` : n.name}</option>)}
          </optgroup>
        ))}
      </select>
    </Campo>
  )
}
