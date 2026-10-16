import type { IncidentStatus, ResourceStatus, ResourceType } from './types'

// Fechas del backend: ISO sin zona horaria = hora local del servidor.
export function fecha(iso: string | null | undefined): Date | null {
  return iso ? new Date(iso) : null
}

export function hora(iso: string | null | undefined): string {
  const d = fecha(iso)
  return d ? d.toLocaleTimeString('es-GT', { hour: '2-digit', minute: '2-digit' }) : '—'
}

export function fechaHora(iso: string | null | undefined): string {
  const d = fecha(iso)
  return d ? d.toLocaleString('es-GT', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'
}

export function hace(iso: string | null | undefined): string {
  const d = fecha(iso)
  if (!d) return '—'
  const min = Math.round((Date.now() - d.getTime()) / 60000)
  if (min < 1) return 'ahora'
  if (min < 60) return `hace ${min} min`
  const h = Math.floor(min / 60)
  if (h < 24) return `hace ${h} h ${min % 60} min`
  return fechaHora(iso)
}

export function minutos(v: number | null | undefined, dec = 1): string {
  return v === null || v === undefined ? '—' : `${v.toFixed(dec)} min`
}

export const PRIORIDAD: Record<number, { label: string; texto: string; fondo: string; punto: string; borde: string }> = {
  4: { label: 'Crítico', texto: 'text-critical', fondo: 'bg-critical/10', punto: 'bg-critical', borde: 'border-critical' },
  3: { label: 'Alto', texto: 'text-high', fondo: 'bg-high-fill/15', punto: 'bg-high-fill', borde: 'border-high-fill' },
  2: { label: 'Medio', texto: 'text-medium', fondo: 'bg-medium/10', punto: 'bg-medium', borde: 'border-medium' },
  1: { label: 'Bajo', texto: 'text-low', fondo: 'bg-low/10', punto: 'bg-low', borde: 'border-low' },
}

// Colores en hexadecimal para usar en SVG (mismos valores que index.css).
export const COLOR_PRIORIDAD: Record<number, string> = {
  4: '#c81e35', 3: '#f0a20c', 2: '#2f62ad', 1: '#6b7587',
}

export const ESTADO_INCIDENTE: Record<IncidentStatus, { label: string; clase: string }> = {
  pending: { label: 'Esperando unidades', clase: 'bg-critical/10 text-critical' },
  dispatched: { label: 'Unidades en camino', clase: 'bg-route-soft text-route' },
  on_scene: { label: 'En escena', clase: 'bg-ink text-white' },
  resolved: { label: 'Resuelto', clase: 'bg-ok-soft text-ok' },
  cancelled: { label: 'Cancelado', clase: 'bg-line text-muted' },
}

export const ESTADO_RECURSO: Record<ResourceStatus, { label: string; clase: string }> = {
  available: { label: 'Disponible', clase: 'bg-ok-soft text-ok' },
  dispatched: { label: 'En camino', clase: 'bg-route-soft text-route' },
  on_scene: { label: 'En escena', clase: 'bg-ink text-white' },
  maintenance: { label: 'Mantenimiento', clase: 'bg-line text-muted' },
}

export const TIPO_RECURSO: Record<ResourceType, string> = {
  ambulance: 'Ambulancia',
  firefighters: 'Bomberos',
  police: 'Policía',
  rescue: 'Rescate',
}

export function describirFaltantes(f: Partial<Record<ResourceType, number>>): string {
  return Object.entries(f).map(([t, n]) => `${n} ${TIPO_RECURSO[t as ResourceType] ?? t}`).join(', ')
}
