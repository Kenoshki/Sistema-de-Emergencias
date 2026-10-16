import { useMemo, useState } from 'react'
import { COLOR_PRIORIDAD, TIPO_RECURSO } from '../lib/format'
import type { Arista, Nodo, Recurso, ResourceType } from '../lib/types'

/**
 * Mapa esquemático de la red vial: cada punto es un nodo del grafo (zona de la
 * capital o cabecera municipal) y cada línea una conexión. Se dibuja con
 * coordenadas reales, sin depender de mapas externos (funciona sin internet).
 *
 * Dos vistas: "país" (todo Guatemala) y "capital" (zonas + área metropolitana).
 */

export type VistaMapa = 'pais' | 'capital'
export interface IncidenteMapa { id: string; node: number; priority: number; status: string; type_label?: string }

export interface PropsMapa {
  nodos: Nodo[]
  vista?: VistaMapa
  aristas?: Arista[]
  incidentes?: IncidenteMapa[]
  recursos?: Recurso[]
  ruta?: number[]
  ordenVisita?: number[]
  seleccion?: number[]
  onNodo?: (nodo: number) => void
  onArista?: (a: Arista) => void
  onIncidente?: (id: string) => void
  etiquetas?: 'numero' | 'completa'
  /** Solo mapa OSM: dibujar todas las conexiones del grafo (por defecto, si se pueden cerrar vías). */
  mostrarRed?: boolean
  /** Solo mapa OSM: punto en el que centrar el mapa cuando no hay ruta. */
  centro?: number
  /** Solo mapa OSM: clases de altura del contenedor. */
  alto?: string
}

const ANCHO = 760
const MARGEN = 40
const LETRA: Record<ResourceType, string> = { ambulance: 'A', firefighters: 'B', police: 'P', rescue: 'R' }
export const COLOR_ESTADO_RECURSO: Record<string, string> = {
  available: '#23784a', dispatched: '#0d7280', on_scene: '#14213d', maintenance: '#8a94a6',
}
// Radio (en grados) alrededor de la capital que se considera "área metropolitana".
const RADIO_METRO = 0.16

function centroCapital(nodos: Nodo[]) {
  const zonas = nodos.filter((n) => n.kind === 'zona')
  if (!zonas.length) return { lat: 14.62, lon: -90.52 }
  return {
    lat: zonas.reduce((s, n) => s + n.lat, 0) / zonas.length,
    lon: zonas.reduce((s, n) => s + n.lon, 0) / zonas.length,
  }
}

/** Nodos visibles en una vista. */
export function nodosDeVista(nodos: Nodo[], vista: VistaMapa): Nodo[] {
  if (vista === 'pais') return nodos
  const c = centroCapital(nodos)
  return nodos.filter((n) => n.kind === 'zona' || Math.hypot(n.lat - c.lat, n.lon - c.lon) < RADIO_METRO)
}

/** Vista que mejor muestra un conjunto de nodos (p. ej. una ruta). */
export function vistaPara(nodos: Nodo[], ids: number[]): VistaMapa {
  const visibles = new Set(nodosDeVista(nodos, 'capital').map((n) => n.node))
  return ids.length && ids.every((id) => visibles.has(id)) ? 'capital' : 'pais'
}

export function MapaZonas({
  nodos, vista = 'pais', aristas = [], incidentes = [], recursos = [], ruta = [], ordenVisita, seleccion = [],
  onNodo, onArista, onIncidente, etiquetas = 'numero',
}: PropsMapa) {
  const [hover, setHover] = useState<number | null>(null)
  const pais = vista === 'pais'

  const visibles = useMemo(() => nodosDeVista(nodos, vista), [nodos, vista])
  const idsVisibles = useMemo(() => new Set(visibles.map((n) => n.node)), [visibles])

  const { pos, alto } = useMemo(() => {
    const lats = visibles.map((n) => n.lat)
    const lons = visibles.map((n) => n.lon)
    const minLat = Math.min(...lats), maxLat = Math.max(...lats)
    const minLon = Math.min(...lons), maxLon = Math.max(...lons)
    const k = Math.cos(((minLat + maxLat) / 2) * Math.PI / 180)
    const escala = (ANCHO - 2 * MARGEN) / (((maxLon - minLon) * k) || 1)
    const p: Record<number, { x: number; y: number }> = {}
    for (const n of visibles) {
      p[n.node] = { x: MARGEN + (n.lon - minLon) * k * escala, y: MARGEN + (maxLat - n.lat) * escala }
    }
    return { pos: p, alto: (maxLat - minLat) * escala + 2 * MARGEN }
  }, [visibles])

  const enRuta = useMemo(() => {
    const s = new Set<string>()
    for (let i = 0; i < ruta.length - 1; i++) s.add([ruta[i], ruta[i + 1]].sort((a, b) => a - b).join('-'))
    return s
  }, [ruta])

  const ordenDe = useMemo(() => {
    const m: Record<number, number> = {}
    ordenVisita?.forEach((n, i) => { m[n] = i + 1 })
    return m
  }, [ordenVisita])

  const incPorNodo = useMemo(() => agrupar(incidentes.filter((i) => idsVisibles.has(i.node)), (i) => i.node), [incidentes, idsVisibles])
  const recPorNodo = useMemo(() => agrupar(recursos.filter((r) => idsVisibles.has(r.current_node)), (r) => r.current_node), [recursos, idsVisibles])

  if (!visibles.length) return null
  const rutaSet = new Set(ruta)

  return (
    <svg viewBox={`0 0 ${ANCHO} ${alto}`} className="h-auto w-full select-none" role="img"
      aria-label={pais ? 'Mapa esquemático de la red vial de Guatemala' : 'Mapa esquemático de la Ciudad de Guatemala'}>
      {/* Conexiones viales */}
      {aristas.map((a) => {
        const p1 = pos[a.origen], p2 = pos[a.destino]
        if (!p1 || !p2) return null
        const clave = [a.origen, a.destino].sort((x, y) => x - y).join('-')
        const activa = enRuta.has(clave)
        return (
          <g key={clave} className={onArista ? 'cursor-pointer' : ''} onClick={() => onArista?.(a)}>
            {onArista && <line x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y} stroke="transparent" strokeWidth={pais ? 7 : 14} />}
            <line
              x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y}
              stroke={a.cerrada ? '#c81e35' : activa ? '#0d7280' : pais ? '#c9d0da' : '#b9c2ce'}
              strokeWidth={activa ? (pais ? 4 : 6) : a.cerrada ? (pais ? 2 : 3) : (pais ? 0.9 : 2.5)}
              strokeDasharray={a.cerrada ? (pais ? '4 3' : '6 5') : undefined}
              strokeLinecap="round"
            />
            <title>{`${a.origen} ↔ ${a.destino}: ${a.distancia_km} km${a.cerrada ? ' (CERRADA)' : ''}`}</title>
          </g>
        )
      })}

      {/* Nodos */}
      {visibles.map((n) => {
        const p = pos[n.node]
        const sel = seleccion.includes(n.node)
        const enCamino = rutaSet.has(n.node)
        const orden = ordenDe[n.node]
        const destacado = sel || enCamino
        const r = pais
          ? (n.kind === 'zona' ? 1.6 : n.department_head ? 5 : 3) + (sel ? 3 : enCamino ? 1.5 : 0)
          : (n.kind === 'zona' ? 14 : 10) + (sel ? 3 : 0)
        const mostrarNombre = hover === n.node || (etiquetas === 'completa' && destacado)
          || (pais && n.department_head && n.kind === 'municipio')
        return (
          <g key={n.node}
            className={onNodo ? 'cursor-pointer' : ''}
            onClick={() => onNodo?.(n.node)}
            onMouseEnter={() => setHover(n.node)}
            onMouseLeave={() => setHover(null)}
          >
            {onNodo && pais && <circle cx={p.x} cy={p.y} r={8} fill="transparent" />}
            <circle cx={p.x} cy={p.y} r={r}
              fill={sel ? '#14213d' : enCamino ? '#0d7280' : n.department_head && pais ? '#14213d' : '#ffffff'}
              stroke={destacado ? '#ffffff' : '#14213d'} strokeWidth={destacado ? 2 : pais ? 1 : 1.5} />
            {!pais && (
              <text x={p.x} y={p.y + 4} textAnchor="middle" fontSize={n.kind === 'zona' ? 13 : 9} fontWeight={700}
                fill={destacado ? '#ffffff' : '#14213d'} style={{ fontFamily: 'var(--font-display)' }}>
                {n.kind === 'zona' ? n.node : n.name.slice(0, 2)}
              </text>
            )}
            {orden !== undefined && (!pais || enCamino) && (
              <g>
                <rect x={p.x + 8} y={p.y - 24} width={24} height={15} rx={3} fill="#f0a20c" />
                <text x={p.x + 20} y={p.y - 13} textAnchor="middle" fontSize={10} fontWeight={700} fill="#14213d">{orden}º</text>
              </g>
            )}
            {mostrarNombre && (
              <text x={p.x} y={p.y + (pais ? -8 : 28)} textAnchor="middle" fontSize={pais ? 10 : 11}
                fontWeight={hover === n.node || destacado ? 700 : 500}
                fill={hover === n.node || destacado ? '#14213d' : '#5b6779'}
                stroke="#ffffff" strokeWidth={3} paintOrder="stroke">
                {hover === n.node ? n.label : n.name}
              </text>
            )}
            <title>{n.label}</title>
          </g>
        )
      })}

      {/* Unidades */}
      {Object.entries(recPorNodo).map(([nodo, lista]) => {
        const p = pos[Number(nodo)]
        if (!p) return null
        const lado = pais ? 6 : 13
        const paso = lado + 2
        return lista.slice(0, pais ? 4 : 8).map((r, i) => {
          const fila = Math.floor(i / 4), col = i % 4
          const total = Math.min(lista.length, 4)
          const x = p.x - (total * paso) / 2 + col * paso
          const y = p.y + (pais ? 6 : 18) + fila * paso
          return (
            <g key={r.code}>
              <rect x={x} y={y} width={lado} height={lado} rx={pais ? 1.5 : 2.5} fill={COLOR_ESTADO_RECURSO[r.status]} stroke="#fff" strokeWidth={pais ? 0.8 : 1.5} />
              {!pais && <text x={x + lado / 2} y={y + 10} textAnchor="middle" fontSize={9} fontWeight={700} fill="#fff">{LETRA[r.type]}</text>}
              <title>{`${r.code} · ${TIPO_RECURSO[r.type]} · ${r.status_label} · ${r.current_label}`}</title>
            </g>
          )
        })
      })}

      {/* Incidentes */}
      {Object.entries(incPorNodo).map(([nodo, lista]) => {
        const p = pos[Number(nodo)]
        if (!p) return null
        const radio = pais ? 5.5 : 8
        const distancia = pais ? 11 : 24
        return lista.map((inc, i) => {
          const ang = (-90 + (i - (lista.length - 1) / 2) * 38) * Math.PI / 180
          const x = p.x + Math.cos(ang) * distancia
          const y = p.y + Math.sin(ang) * distancia
          const color = COLOR_PRIORIDAD[inc.priority] ?? '#6b7587'
          const critico = inc.priority === 4 && inc.status !== 'resolved' && inc.status !== 'cancelled'
          return (
            <g key={inc.id} className={onIncidente ? 'cursor-pointer' : ''} onClick={(e) => { e.stopPropagation(); onIncidente?.(inc.id) }}>
              {critico && <circle cx={x} cy={y} r={radio + 1} fill={color} className="pulso" />}
              <circle cx={x} cy={y} r={radio} fill={color} stroke="#fff" strokeWidth={2} />
              {inc.status === 'pending' && <circle cx={x} cy={y} r={radio * 0.38} fill="#fff" />}
              <title>{`${inc.id} · ${inc.type_label ?? ''} · Prioridad ${inc.priority}`}</title>
            </g>
          )
        })
      })}
    </svg>
  )
}

function agrupar<T>(lista: T[], clave: (x: T) => number): Record<number, T[]> {
  const r: Record<number, T[]> = {}
  for (const x of lista) (r[clave(x)] ??= []).push(x)
  return r
}

/** Selector "Todo el país / Capital". */
export function SelectorVista({ vista, onChange }: { vista: VistaMapa; onChange: (v: VistaMapa) => void }) {
  return (
    <div className="inline-flex rounded-md border border-line bg-surface p-0.5" role="group" aria-label="Vista del mapa">
      {([['pais', 'Todo el país'], ['capital', 'Capital']] as [VistaMapa, string][]).map(([v, l]) => (
        <button key={v} type="button" onClick={() => onChange(v)} aria-pressed={vista === v}
          className={`rounded px-2.5 py-1 text-xs font-semibold ${vista === v ? 'bg-ink text-white' : 'text-muted hover:text-ink'}`}>
          {l}
        </button>
      ))}
    </div>
  )
}

export function LeyendaMapa({ conRecursos = true, conIncidentes = true }: { conRecursos?: boolean; conIncidentes?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted">
      {conIncidentes && [4, 3, 2, 1].map((p) => (
        <span key={p} className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-full" style={{ background: COLOR_PRIORIDAD[p] }} /> P{p}
        </span>
      ))}
      {conIncidentes && (
        <span className="inline-flex items-center gap-1.5">
          <span className="relative inline-block size-2.5 rounded-full bg-low"><span className="absolute inset-[3px] rounded-full bg-white" /></span>
          Esperando unidades
        </span>
      )}
      {!conIncidentes && (
        <span className="inline-flex items-center gap-1.5"><span className="h-1.5 w-4 rounded bg-route" /> Ruta más corta</span>
      )}
      {conRecursos && (
        <>
          <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: COLOR_ESTADO_RECURSO.available }} /> Unidad libre</span>
          <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: COLOR_ESTADO_RECURSO.dispatched }} /> En camino</span>
          <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-sm" style={{ background: COLOR_ESTADO_RECURSO.on_scene }} /> En escena</span>
        </>
      )}
      <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-ink" /> Cabecera departamental</span>
      <span className="inline-flex items-center gap-1.5"><span className="h-0 w-4 border-t-2 border-dashed border-critical" /> Vía cerrada</span>
    </div>
  )
}
