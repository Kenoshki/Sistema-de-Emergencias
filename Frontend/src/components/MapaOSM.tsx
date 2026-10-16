import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useEffect, useMemo, useRef, useState } from 'react'
import { COLOR_PRIORIDAD, TIPO_RECURSO } from '../lib/format'
import type { ResourceType } from '../lib/types'
import { COLOR_ESTADO_RECURSO, nodosDeVista, type PropsMapa } from './MapaZonas'

/**
 * Mapa de la red sobre OpenStreetMap (Leaflet).
 *
 * Los puntos y líneas son los mismos del grafo que usa Dijkstra; OpenStreetMap
 * solo aporta el fondo (calles, ríos, relieve, nombres). Opcionalmente, la ruta
 * elegida por Dijkstra se puede dibujar siguiendo las carreteras reales con el
 * servidor OSRM (propio o el de demostración), pasando por los mismos puntos en el mismo orden.
 */

// Servidores configurables en Frontend/.env (ver README, "Uso a nivel nacional").
// Por defecto se usan los servidores públicos de demostración, solo aptos para tráfico ligero.
const env = import.meta.env
const TILE_URL: string = env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATRIBUCION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>'
const OSRM_BASE: string = (env.VITE_OSRM_URL || 'https://router.project-osrm.org').replace(/\/+$/, '')
const OSRM_URL = `${OSRM_BASE}/route/v1/driving/`
const OSRM_PROPIO = Boolean(env.VITE_OSRM_URL)
const LIMITES_GT = L.latLngBounds([12.6, -93.6], [18.9, -87.2])
const LETRA: Record<ResourceType, string> = { ambulance: 'A', firefighters: 'B', police: 'P', rescue: 'R' }
const TINTA = '#14213d'
const RUTA = '#0d7280'
const CERRADA = '#c81e35'

interface Trazado { coords: [number, number][]; km: number }
const cacheTrazados = new Map<string, Trazado | 'error'>()

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!))

export function MapaOSM({
  nodos, vista = 'pais', aristas = [], incidentes = [], recursos = [], ruta = [], ordenVisita, seleccion = [],
  onNodo, onArista, onIncidente, etiquetas = 'numero', mostrarRed, centro, alto = 'h-[440px] sm:h-[560px]',
}: PropsMapa) {
  const div = useRef<HTMLDivElement>(null)
  const mapa = useRef<L.Map | null>(null)
  const lienzo = useRef<L.Renderer | undefined>(undefined)
  const primerEncuadre = useRef(true)
  const capas = useRef<{ red: L.LayerGroup; ruta: L.LayerGroup; nodos: L.LayerGroup; extra: L.LayerGroup } | null>(null)
  const [zoom, setZoom] = useState(7)
  const [sinFondo, setSinFondo] = useState(false)
  const [porCarretera, setPorCarretera] = useState(false)
  const [trazado, setTrazado] = useState<Trazado | 'cargando' | 'error' | null>(null)

  // Las funciones de los props cambian en cada render: se leen desde una ref.
  const cb = useRef({ onNodo, onArista, onIncidente })
  cb.current = { onNodo, onArista, onIncidente }

  const verRed = mostrarRed ?? Boolean(onArista)
  const porId = useMemo(() => new Map(nodos.map((n) => [n.node, n])), [nodos])
  const claveRuta = ruta.join('-')

  // ---- Crear el mapa una sola vez
  useEffect(() => {
    if (!div.current) return
    const m = L.map(div.current, {
      preferCanvas: true, minZoom: 6, maxZoom: 18, maxBounds: LIMITES_GT, maxBoundsViscosity: 0.8,
      zoomSnap: 0.5, attributionControl: true,
    })
    m.attributionControl.setPrefix(false)
    let cargadas = 0, errores = 0
    L.tileLayer(TILE_URL, { maxZoom: 19, attribution: ATRIBUCION })
      .on('tileload', () => { cargadas++; setSinFondo(false) })
      .on('tileerror', () => { errores++; if (errores >= 6 && cargadas === 0) setSinFondo(true) })
      .addTo(m)
    lienzo.current = L.canvas({ tolerance: 6 })
    capas.current = {
      red: L.layerGroup().addTo(m),
      ruta: L.layerGroup().addTo(m),
      nodos: L.featureGroup().addTo(m),
      extra: L.layerGroup().addTo(m),
    }
    m.on('zoomend', () => setZoom(m.getZoom()))
    m.fitBounds(L.latLngBounds([13.7, -92.25], [17.85, -88.2]), { animate: false })
    setZoom(m.getZoom())
    mapa.current = m
    // Si el contenedor cambia de tamaño (menú lateral, ventana), Leaflet debe recalcular.
    const ro = new ResizeObserver(() => m.invalidateSize())
    ro.observe(div.current)
    return () => {
      ro.disconnect()
      m.remove()
      // Leaflet deja pendiente un redibujado del lienzo; si se ejecuta con el mapa ya
      // eliminado lanza un error (pasa al cambiar de página o con React StrictMode).
      const lz = lienzo.current as (L.Renderer & { _redrawRequest?: number | null }) | undefined
      if (lz?._redrawRequest) { L.Util.cancelAnimFrame(lz._redrawRequest); lz._redrawRequest = null }
      mapa.current = null; capas.current = null
    }
  }, [])

  // ---- Encuadre: al cambiar la vista, o al aparecer una ruta nueva
  useEffect(() => {
    const m = mapa.current
    if (!m || !nodos.length) return
    const puntos = nodosDeVista(nodos, vista).map((n) => L.latLng(n.lat, n.lon))
    if (puntos.length) m.fitBounds(L.latLngBounds(puntos), { padding: [24, 24], animate: !primerEncuadre.current })
    primerEncuadre.current = false
  }, [vista, nodos])

  // Sin ruta, pero con un punto de interés (p. ej. el lugar del incidente): acercarse a él.
  useEffect(() => {
    const m = mapa.current
    const n = centro !== undefined ? porId.get(centro) : undefined
    if (!m || !n || ruta.length > 1) return
    m.setView([n.lat, n.lon], n.kind === 'zona' ? 13 : 10, { animate: false })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [centro, porId])

  useEffect(() => {
    const m = mapa.current
    if (!m || ruta.length < 2) return
    const puntos = ruta.map((id) => porId.get(id)).filter(Boolean).map((n) => L.latLng(n!.lat, n!.lon))
    // Solo se reencuadra si la ruta no cabe en lo que ya se ve.
    const b = L.latLngBounds(puntos)
    if (!m.getBounds().contains(b)) m.fitBounds(b, { padding: [40, 40], maxZoom: 13 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [claveRuta, porId])

  // ---- Trazado por carretera (OSRM), siguiendo los puntos de la ruta de Dijkstra
  useEffect(() => {
    if (!porCarretera || ruta.length < 2) { setTrazado(null); return }
    const pts = ruta.map((id) => porId.get(id)).filter(Boolean) as { lat: number; lon: number }[]
    const clave = pts.map((p) => `${p.lon.toFixed(5)},${p.lat.toFixed(5)}`).join(';')
    const enCache = cacheTrazados.get(clave)
    if (enCache) { setTrazado(enCache); return }
    let vigente = true
    setTrazado('cargando')
    fetch(`${OSRM_URL}${clave}?overview=full&geometries=geojson`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((j) => {
        const r = j?.routes?.[0]
        if (!r) throw new Error('sin ruta')
        const t: Trazado = { coords: r.geometry.coordinates.map(([lon, lat]: [number, number]) => [lat, lon]), km: r.distance / 1000 }
        cacheTrazados.set(clave, t)
        if (vigente) setTrazado(t)
      })
      .catch(() => { cacheTrazados.set(clave, 'error'); if (vigente) setTrazado('error') })
    return () => { vigente = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [porCarretera, claveRuta, porId])

  // ---- Conexiones del grafo (y vías cerradas, que siempre se muestran)
  useEffect(() => {
    const g = capas.current?.red
    if (!g) return
    g.clearLayers()
    const r = lienzo.current
    for (const a of aristas) {
      if (!verRed && !a.cerrada) continue
      const p = porId.get(a.origen), q = porId.get(a.destino)
      if (!p || !q) continue
      const linea = L.polyline([[p.lat, p.lon], [q.lat, q.lon]], {
        renderer: r,
        color: a.cerrada ? CERRADA : TINTA,
        weight: a.cerrada ? 3.5 : zoom >= 11 ? 2 : 1.2,
        opacity: a.cerrada ? 0.95 : 0.35,
        dashArray: a.cerrada ? '7 6' : undefined,
        interactive: Boolean(cb.current.onArista),
      })
      linea.bindTooltip(`${esc(p.name)} ↔ ${esc(q.name)}: ${a.distancia_km} km${a.cerrada ? ' (CERRADA)' : ''}`, { sticky: true })
      if (cb.current.onArista) linea.on('click', () => cb.current.onArista?.(a))
      linea.addTo(g)
    }
  }, [aristas, porId, verRed, zoom])

  // ---- Ruta más corta (Dijkstra) y su trazado por carretera
  useEffect(() => {
    const g = capas.current?.ruta
    if (!g) return
    g.clearLayers()
    if (ruta.length < 2) return
    const pts = ruta.map((id) => porId.get(id)).filter(Boolean).map((n) => [n!.lat, n!.lon] as [number, number])
    const conCarretera = trazado && typeof trazado === 'object'
    if (conCarretera) {
      L.polyline(trazado.coords, { color: '#ffffff', weight: 9, opacity: 0.9, interactive: false }).addTo(g)
      L.polyline(trazado.coords, { color: RUTA, weight: 5, opacity: 0.95, interactive: false }).addTo(g)
      // El esquema del grafo queda como referencia, punteado.
      L.polyline(pts, { color: TINTA, weight: 2, opacity: 0.55, dashArray: '4 6', interactive: false }).addTo(g)
    } else {
      L.polyline(pts, { color: '#ffffff', weight: 9, opacity: 0.9, interactive: false }).addTo(g)
      L.polyline(pts, { color: RUTA, weight: 5, opacity: 0.95, interactive: false }).addTo(g)
    }
  }, [claveRuta, porId, trazado]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- Puntos del grafo (zonas y cabeceras municipales)
  useEffect(() => {
    const g = capas.current?.nodos
    if (!g) return
    g.clearLayers()
    const r = lienzo.current
    const enRuta = new Set(ruta)
    const sel = new Set(seleccion)
    const cerca = zoom >= 11
    for (const n of nodos) {
      const destacado = sel.has(n.node) || enRuta.has(n.node)
      const base = n.kind === 'zona' ? (cerca ? 10 : 3.5) : n.department_head ? 6 : zoom >= 9 ? 4.5 : 3
      const c = L.circleMarker([n.lat, n.lon], {
        renderer: r,
        radius: base + (sel.has(n.node) ? 3 : enRuta.has(n.node) ? 1.5 : 0),
        color: destacado ? '#ffffff' : TINTA,
        weight: destacado ? 2.5 : 1.3,
        fillColor: sel.has(n.node) ? TINTA : enRuta.has(n.node) ? RUTA : n.department_head ? TINTA : '#ffffff',
        fillOpacity: 1,
      })
      c.bindTooltip(esc(n.label), { direction: 'top', offset: [0, -6] })
      if (cb.current.onNodo) c.on('click', () => cb.current.onNodo?.(n.node))
      c.addTo(g)
    }
  }, [nodos, claveRuta, seleccion.join(','), zoom]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---- Etiquetas, orden de Dijkstra, unidades e incidentes (marcadores HTML)
  useEffect(() => {
    const g = capas.current?.extra
    if (!g) return
    g.clearLayers()
    const enRuta = new Set(ruta)
    const sel = new Set(seleccion)
    const cerca = zoom >= 11

    // Número de zona (OpenStreetMap no rotula las zonas de la capital)
    if (cerca) {
      for (const n of nodos) {
        if (n.kind !== 'zona') continue
        const oscuro = sel.has(n.node) || enRuta.has(n.node) || n.department_head
        L.marker([n.lat, n.lon], {
          interactive: false, keyboard: false,
          icon: L.divIcon({ className: `osm-zona${oscuro ? ' oscuro' : ''}`, html: `<span>${n.node}</span>`, iconSize: [0, 0] }),
        }).addTo(g)
      }
    }

    // Nombres de origen, destino y puntos de la ruta
    if (etiquetas === 'completa') {
      for (const id of new Set([...sel, ...(ruta.length ? [ruta[0], ruta[ruta.length - 1]] : [])])) {
        const n = porId.get(id)
        if (!n) continue
        L.marker([n.lat, n.lon], {
          interactive: false, keyboard: false,
          icon: L.divIcon({ className: 'osm-etiqueta', html: `<span>${esc(n.kind === 'zona' ? n.label.split(',')[0] : n.name)}</span>`, iconSize: [0, 0] }),
        }).addTo(g)
      }
    }

    // Orden en que Dijkstra fijó cada punto
    if (ordenVisita?.length) {
      ordenVisita.forEach((id, i) => {
        if (!enRuta.has(id) && !cerca) return
        const n = porId.get(id)
        if (!n) return
        L.marker([n.lat, n.lon], {
          interactive: false, keyboard: false,
          icon: L.divIcon({ className: 'osm-orden', html: `<span>${i + 1}º</span>`, iconSize: [0, 0] }),
        }).addTo(g)
      })
    }

    // Unidades: cuadros de color por estado, agrupados bajo su punto
    const porNodo = new Map<number, typeof recursos>()
    for (const r of recursos) porNodo.set(r.current_node, [...(porNodo.get(r.current_node) ?? []), r])
    const grande = zoom >= 10
    for (const [id, lista] of porNodo) {
      const n = porId.get(id)
      if (!n) continue
      const visibles = lista.slice(0, grande ? 8 : 4)
      const html = visibles.map((r) =>
        `<i style="background:${COLOR_ESTADO_RECURSO[r.status] ?? '#8a94a6'}" title="${esc(`${r.code} · ${TIPO_RECURSO[r.type]} · ${r.status_label} · ${r.current_label}`)}">${grande ? LETRA[r.type] : ''}</i>`,
      ).join('') + (lista.length > visibles.length ? `<b>+${lista.length - visibles.length}</b>` : '')
      L.marker([n.lat, n.lon], {
        keyboard: false,
        icon: L.divIcon({ className: `osm-unidades${grande ? ' grande' : ''}`, html: `<div>${html}</div>`, iconSize: [0, 0] }),
      }).addTo(g)
    }

    // Incidentes: círculos por prioridad, en abanico sobre su punto
    const incPorNodo = new Map<number, typeof incidentes>()
    for (const i of incidentes) incPorNodo.set(i.node, [...(incPorNodo.get(i.node) ?? []), i])
    for (const [id, lista] of incPorNodo) {
      const n = porId.get(id)
      if (!n) continue
      lista.forEach((inc, k) => {
        const ang = (-90 + (k - (lista.length - 1) / 2) * 40) * Math.PI / 180
        const dx = Math.round(Math.cos(ang) * 16), dy = Math.round(Math.sin(ang) * 16)
        const critico = inc.priority === 4 && inc.status !== 'resolved' && inc.status !== 'cancelled'
        const m = L.marker([n.lat, n.lon], {
          zIndexOffset: 1000 + inc.priority * 10,
          title: `${inc.id} · ${inc.type_label ?? ''} · Prioridad ${inc.priority}`,
          icon: L.divIcon({
            className: 'osm-incidente',
            html: `<span style="--c:${COLOR_PRIORIDAD[inc.priority] ?? '#6b7587'};transform:translate(${dx}px,${dy}px)"${critico ? ' class="critico"' : ''}>${inc.status === 'pending' ? '<i></i>' : ''}</span>`,
            iconSize: [0, 0],
          }),
        })
        if (cb.current.onIncidente) m.on('click', () => cb.current.onIncidente?.(inc.id))
        m.addTo(g)
      })
    }
  }, [nodos, porId, claveRuta, seleccion.join(','), ordenVisita, recursos, incidentes, etiquetas, zoom]) // eslint-disable-line react-hooks/exhaustive-deps

  // Distancia del modelo (suma de pesos del grafo) para compararla con OSRM
  const kmGrafo = useMemo(() => {
    if (ruta.length < 2) return null
    const peso = new Map(aristas.map((a) => [[a.origen, a.destino].sort((x, y) => x - y).join('-'), a.distancia_km]))
    let s = 0
    for (let i = 0; i < ruta.length - 1; i++) {
      const w = peso.get([ruta[i], ruta[i + 1]].sort((x, y) => x - y).join('-'))
      if (w === undefined) return null
      s += w
    }
    return s
  }, [claveRuta, aristas]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="relative">
      <div ref={div} className={`${alto} w-full overflow-hidden rounded-md border border-line bg-paper`}
        role="application" aria-label="Mapa de Guatemala (OpenStreetMap)" />
      {ruta.length > 1 && (
        <div className="absolute bottom-7 left-2 z-[1000] max-w-[calc(100%-1rem)] rounded-md border border-line bg-surface/95 px-3 py-2 text-xs shadow">
          <label className="flex cursor-pointer items-center gap-2 font-semibold">
            <input type="checkbox" checked={porCarretera} onChange={(e) => setPorCarretera(e.target.checked)} />
            Dibujar por carretera (OSRM{OSRM_PROPIO ? '' : ' de demostración'})
          </label>
          {porCarretera && (
            <p className="mt-1 text-muted">
              {trazado === 'cargando' ? 'Consultando OSRM…'
                : trazado === 'error' ? 'OSRM no respondió; se muestra la ruta del grafo.'
                : trazado && typeof trazado === 'object'
                  ? <>Por carretera: <strong className="num text-ink">{trazado.km.toFixed(1)} km</strong>{kmGrafo !== null && <> · modelo: <span className="num">{kmGrafo.toFixed(1)} km</span></>}</>
                  : null}
            </p>
          )}
        </div>
      )}
      {sinFondo && (
        <div className="absolute inset-x-2 top-2 z-[1000] rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-900 shadow">
          No se pudo cargar el mapa de OpenStreetMap (¿sin internet?). Los puntos y rutas siguen funcionando; puede cambiar a <strong>Esquema</strong>.
        </div>
      )}
    </div>
  )
}
