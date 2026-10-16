import { Map as IconoMapa, Waypoints } from 'lucide-react'
import { useState } from 'react'
import { MapaOSM } from './MapaOSM'
import { MapaZonas, type PropsMapa } from './MapaZonas'

export type FondoMapa = 'osm' | 'esquema'
const CLAVE = 'ems.fondoMapa'

function leerFondo(): FondoMapa {
  try { return localStorage.getItem(CLAVE) === 'esquema' ? 'esquema' : 'osm' } catch { return 'osm' }
}

/**
 * Mapa de la red con dos fondos:
 * - "Mapa": OpenStreetMap (necesita internet).
 * - "Esquema": dibujo propio del grafo (funciona sin internet).
 * La elección se recuerda en este navegador.
 */
export function MapaRed(props: PropsMapa) {
  const [fondo, setFondoEstado] = useState<FondoMapa>(leerFondo)
  const setFondo = (f: FondoMapa) => {
    setFondoEstado(f)
    try { localStorage.setItem(CLAVE, f) } catch { /* sin almacenamiento: solo esta sesión */ }
  }
  return (
    <div className="relative">
      <div className="absolute right-2 top-2 z-[1001] inline-flex rounded-md border border-line bg-surface/95 p-0.5 shadow-sm"
        role="group" aria-label="Fondo del mapa">
        {([['osm', 'Mapa', IconoMapa], ['esquema', 'Esquema', Waypoints]] as const).map(([v, l, Icono]) => (
          <button key={v} type="button" onClick={() => setFondo(v)} aria-pressed={fondo === v}
            className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-semibold ${fondo === v ? 'bg-ink text-white' : 'text-muted hover:text-ink'}`}>
            <Icono className="size-3.5" /> {l}
          </button>
        ))}
      </div>
      {fondo === 'osm' ? <MapaOSM {...props} /> : <div className="pt-10"><MapaZonas {...props} /></div>}
    </div>
  )
}
