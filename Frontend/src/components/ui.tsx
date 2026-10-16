import { LoaderCircle, X } from 'lucide-react'
import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { ESTADO_INCIDENTE, ESTADO_RECURSO, PRIORIDAD } from '../lib/format'
import type { IncidentStatus, ResourceStatus } from '../lib/types'

type Variante = 'primario' | 'peligro' | 'secundario' | 'fantasma' | 'ruta'

const VARIANTES: Record<Variante, string> = {
  primario: 'bg-ink text-white hover:bg-ink-soft',
  peligro: 'bg-critical text-white hover:brightness-110',
  ruta: 'bg-route text-white hover:brightness-110',
  secundario: 'bg-surface text-ink border border-line hover:border-ink/40',
  fantasma: 'text-ink hover:bg-ink/5',
}

export function Boton({
  variante = 'primario', cargando = false, icono, children, className = '', disabled, ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante; cargando?: boolean; icono?: ReactNode }) {
  return (
    <button
      {...props}
      disabled={disabled || cargando}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTES[variante]} ${className}`}
    >
      {cargando ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : icono}
      {children}
    </button>
  )
}

export function Prioridad({ valor, compacta = false }: { valor: number; compacta?: boolean }) {
  const p = PRIORIDAD[valor] ?? PRIORIDAD[1]
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-semibold ${p.fondo} ${p.texto}`}>
      <span className={`size-2 rounded-full ${p.punto}`} aria-hidden />
      {compacta ? `P${valor}` : `${valor} · ${p.label}`}
    </span>
  )
}

export function EstadoIncidente({ estado }: { estado: IncidentStatus }) {
  const e = ESTADO_INCIDENTE[estado]
  return <span className={`inline-block whitespace-nowrap rounded px-2 py-0.5 text-xs font-semibold ${e.clase}`}>{e.label}</span>
}

export function EstadoRecurso({ estado }: { estado: ResourceStatus }) {
  const e = ESTADO_RECURSO[estado]
  return <span className={`inline-block whitespace-nowrap rounded px-2 py-0.5 text-xs font-semibold ${e.clase}`}>{e.label}</span>
}

export function Cargando({ texto = 'Cargando…' }: { texto?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted" role="status">
      <LoaderCircle className="size-5 animate-spin" aria-hidden /> {texto}
    </div>
  )
}

export function Aviso({ tipo = 'error', children }: { tipo?: 'error' | 'info' | 'ok'; children: ReactNode }) {
  const clase = {
    error: 'border-critical/30 bg-critical/5 text-critical',
    info: 'border-route/30 bg-route-soft text-route',
    ok: 'border-ok/30 bg-ok-soft text-ok',
  }[tipo]
  return <div className={`rounded-md border px-3 py-2 text-sm ${clase}`} role={tipo === 'error' ? 'alert' : 'status'}>{children}</div>
}

export function Vacio({ titulo, children }: { titulo: string; children?: ReactNode }) {
  return (
    <div className="px-4 py-10 text-center">
      <p className="font-semibold">{titulo}</p>
      {children && <div className="mt-1 text-sm text-muted">{children}</div>}
    </div>
  )
}

/** Sección con encabezado (no todo es una tarjeta: se usa para bloques principales). */
export function Panel({ titulo, accion, children, className = '', sinRelleno = false }: {
  titulo?: ReactNode; accion?: ReactNode; children: ReactNode; className?: string; sinRelleno?: boolean
}) {
  return (
    <section className={`rounded-lg border border-line bg-surface ${className}`}>
      {(titulo || accion) && (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
          {titulo && <h2 className="font-display text-lg font-semibold leading-tight">{titulo}</h2>}
          {accion}
        </header>
      )}
      <div className={sinRelleno ? '' : 'p-4'}>{children}</div>
    </section>
  )
}

export function Campo({ etiqueta, ayuda, error, children, htmlFor }: {
  etiqueta: string; ayuda?: string; error?: string; children: ReactNode; htmlFor?: string
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1 block text-sm font-semibold">{etiqueta}</label>
      {children}
      {ayuda && !error && <p className="mt-1 text-xs text-muted">{ayuda}</p>}
      {error && <p className="mt-1 text-xs font-medium text-critical">{error}</p>}
    </div>
  )
}

export const claseInput =
  'w-full rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted/70 focus:border-route focus:outline-none focus:ring-2 focus:ring-route/25'

export function Modal({ abierto, titulo, onCerrar, children, ancho = 'max-w-lg' }: {
  abierto: boolean; titulo: string; onCerrar: () => void; children: ReactNode; ancho?: string
}) {
  const ref = useRef<HTMLDivElement>(null)
  // onCerrar suele ser una función nueva en cada render; se guarda en una ref para que
  // escribir en un campo del modal no vuelva a ejecutar el efecto (y no robe el foco).
  const cerrarRef = useRef(onCerrar)
  cerrarRef.current = onCerrar
  useEffect(() => {
    if (!abierto) return
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && cerrarRef.current()
    window.addEventListener('keydown', esc)
    // Solo al abrir: enfoca el primer campo, o el cuadro si no hay campos.
    const primero = ref.current?.querySelector<HTMLElement>('textarea, input, select')
    ;(primero ?? ref.current)?.focus()
    return () => window.removeEventListener('keydown', esc)
  }, [abierto])
  if (!abierto) return null
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/50 p-4 pt-[8vh]" onMouseDown={onCerrar}>
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        className={`w-full ${ancho} rounded-lg bg-surface shadow-xl outline-none`}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between border-b border-line px-5 py-3">
          <h2 className="font-display text-xl font-semibold">{titulo}</h2>
          <button onClick={onCerrar} className="rounded p-1 text-muted hover:bg-ink/5 hover:text-ink" aria-label="Cerrar">
            <X className="size-5" />
          </button>
        </header>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}
