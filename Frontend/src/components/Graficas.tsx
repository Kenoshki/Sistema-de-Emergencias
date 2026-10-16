import { useState } from 'react'

/**
 * Gráficas propias en SVG/HTML (sin librerías externas).
 * Cada una muestra una sola serie, con tooltip al pasar el cursor.
 */

const SERIE = '#2b3a5c'
const SERIE_RESALTE = '#0d7280'

/** Barras horizontales: comparar magnitudes entre categorías. */
export function BarrasHorizontales({ datos, unidad = '', formato }: {
  datos: { etiqueta: string; valor: number; detalle?: string }[]
  unidad?: string
  formato?: (v: number) => string
}) {
  const max = Math.max(1, ...datos.map((d) => d.valor))
  const fmt = formato ?? ((v: number) => `${v}${unidad}`)
  return (
    <ul className="space-y-2.5">
      {datos.map((d) => (
        <li key={d.etiqueta} className="group" title={d.detalle ?? `${d.etiqueta}: ${fmt(d.valor)}`}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate">{d.etiqueta}</span>
            <span className="num shrink-0 font-semibold">{fmt(d.valor)}</span>
          </div>
          <div className="h-2 rounded-full bg-paper">
            <div className="h-2 rounded-full transition-[width] group-hover:brightness-125"
              style={{ width: `${(d.valor / max) * 100}%`, background: SERIE, minWidth: d.valor ? 4 : 0 }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

/** Línea de tendencia diaria con área suave y cursor de lectura. */
export function Tendencia({ datos }: { datos: { date: string; total: number }[] }) {
  const [activo, setActivo] = useState<number | null>(null)
  if (!datos.length) return null
  const W = 640, H = 190, mI = 30, mD = 8, mS = 12, mB = 26
  const max = Math.max(2, ...datos.map((d) => d.total))
  const paso = (W - mI - mD) / Math.max(1, datos.length - 1)
  const x = (i: number) => mI + i * paso
  const y = (v: number) => mS + (1 - v / max) * (H - mS - mB)
  const linea = datos.map((d, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(d.total).toFixed(1)}`).join(' ')
  const area = `${linea} L${x(datos.length - 1)},${H - mB} L${x(0)},${H - mB} Z`
  const marcas = [0, Math.round(max / 2), max]
  const etiquetaFecha = (s: string) => {
    const [, m, d] = s.split('-')
    return `${Number(d)}/${Number(m)}`
  }
  const a = activo !== null ? datos[activo] : null

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Incidentes por día"
        onMouseLeave={() => setActivo(null)}>
        {marcas.map((m) => (
          <g key={m}>
            <line x1={mI} x2={W - mD} y1={y(m)} y2={y(m)} stroke="#e4e8ee" />
            <text x={mI - 6} y={y(m) + 4} textAnchor="end" fontSize={10} fill="#5b6779">{m}</text>
          </g>
        ))}
        <path d={area} fill={SERIE} opacity={0.08} />
        <path d={linea} fill="none" stroke={SERIE} strokeWidth={2} strokeLinejoin="round" />
        {datos.map((d, i) => {
          const cada = Math.ceil(datos.length / 8)
          const ultimo = i === datos.length - 1
          return (ultimo || (i % cada === 0 && datos.length - 1 - i >= cada / 2)) && (
            <text key={d.date} x={x(i)} y={H - 8} textAnchor={ultimo ? 'end' : 'middle'} fontSize={10} fill="#5b6779">{etiquetaFecha(d.date)}</text>
          )
        })}
        {a && activo !== null && (
          <g>
            <line x1={x(activo)} x2={x(activo)} y1={mS} y2={H - mB} stroke="#14213d" strokeDasharray="3 3" />
            <circle cx={x(activo)} cy={y(a.total)} r={4.5} fill={SERIE_RESALTE} stroke="#fff" strokeWidth={2} />
          </g>
        )}
        {datos.map((d, i) => (
          <rect key={d.date} x={x(i) - paso / 2} y={0} width={paso} height={H} fill="transparent"
            onMouseEnter={() => setActivo(i)} />
        ))}
      </svg>
      {a && activo !== null && (
        <div className="pointer-events-none absolute top-0 rounded bg-ink px-2 py-1 text-xs text-white shadow"
          style={{ left: `${(x(activo) / W) * 100}%`, transform: `translateX(${activo > datos.length / 2 ? '-105%' : '5%'})` }}>
          {etiquetaFecha(a.date)}: <strong className="num">{a.total}</strong> incidentes
        </div>
      )}
    </div>
  )
}

/** Columnas por hora del día (0–23). */
export function ColumnasHora({ datos }: { datos: { hour: number; count: number }[] }) {
  const [activo, setActivo] = useState<number | null>(null)
  const max = Math.max(1, ...datos.map((d) => d.count))
  const pico = datos.reduce((a, b) => (b.count > a.count ? b : a), datos[0])
  return (
    <div>
      <div className="relative flex h-28 items-end gap-[2px]" onMouseLeave={() => setActivo(null)}>
        {datos.map((d) => (
          <div key={d.hour} className="flex h-full flex-1 items-end" onMouseEnter={() => setActivo(d.hour)}>
            <div className="w-full rounded-t-[3px]"
              style={{ height: `${(d.count / max) * 100}%`, minHeight: d.count ? 3 : 0,
                background: activo === d.hour || (activo === null && d.hour === pico?.hour) ? SERIE_RESALTE : SERIE }} />
          </div>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-muted num">
        <span>0 h</span><span>6 h</span><span>12 h</span><span>18 h</span><span>23 h</span>
      </div>
      <p className="mt-2 text-xs text-muted">
        {activo !== null
          ? <>A las <strong className="text-ink">{activo}:00</strong>: <strong className="num text-ink">{datos[activo]?.count}</strong> incidentes</>
          : pico && pico.count > 0 ? <>Hora con más reportes: <strong className="text-ink">{pico.hour}:00</strong> ({pico.count})</> : 'Sin datos'}
      </p>
    </div>
  )
}
