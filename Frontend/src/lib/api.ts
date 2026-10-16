import axios, { AxiosError } from 'axios'
import type {
  Catalogos, Cierre, FilaCola, Incidente, IncidentePublico, Kpis, Lugar, RedVial, Recurso,
  ResultadoRuta, ResultadoUbicar, Resumen, Usuario, VistaPrevia, CatalogoRoles, Permisos,
} from './types'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'
const TOKEN_KEY = 'ems_token'

export const http = axios.create({ baseURL: API_URL, timeout: 20000 })

// ---- Token de sesión ---------------------------------------------------
export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
}
export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* almacenamiento no disponible */ }
}

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Si el backend responde 401 en una ruta privada, la sesión terminó.
let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: (() => void) | null) { onUnauthorized = fn }

http.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    const url = error.config?.url ?? ''
    if (error.response?.status === 401 && !url.includes('/auth/login') && onUnauthorized) onUnauthorized()
    return Promise.reject(error)
  },
)

/** Mensaje legible a partir de un error de axios. */
export function mensajeError(error: unknown, porDefecto = 'Ocurrió un error inesperado.'): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return 'No hay conexión con el servidor. Verifique que el backend esté encendido.'
    const detail = (error.response.data as { detail?: unknown })?.detail
    if (typeof detail === 'string') return detail
  }
  return porDefecto
}

async function descargar(ruta: string, nombre: string) {
  const r = await http.get(ruta, { responseType: 'blob' })
  const url = URL.createObjectURL(r.data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = nombre
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

// ---- Catálogos (se piden una sola vez y se reutilizan) -------------------
let catalogosCache: Promise<Catalogos> | null = null
function cargarCatalogos(): Promise<Catalogos> {
  if (!catalogosCache) {
    catalogosCache = http.get<Catalogos>('/public/catalogs').then((r) => r.data)
    catalogosCache.catch(() => { catalogosCache = null })
  }
  return catalogosCache
}

export interface BaseUnidad {
  base_department_code: string
  base_municipality_code: string
  base_zone: number | null
}

// ---- Público -------------------------------------------------------------
export interface NuevoReporte {
  type: string
  priority: number
  department_code?: string
  municipality_code?: string
  zone?: number | null
  place_id?: number | null
  place_name?: string
  latitude?: number | null
  longitude?: number | null
  address?: string
  description?: string
  reporter_name?: string
  reporter_phone?: string
}

export const api = {
  catalogos: () => cargarCatalogos(),
  ubicar: (lat: number, lon: number) =>
    http.get<ResultadoUbicar>('/public/locate', { params: { lat, lon } }).then((r) => r.data),
  lugares: (municipality: string, q: string) =>
    http.get<Lugar[]>('/public/places', { params: { municipality, q } }).then((r) => r.data),
  reportar: (datos: NuevoReporte) =>
    http.post<{ message: string; data: IncidentePublico }>('/public/incidents', datos).then((r) => r.data),
  seguimiento: (id: string) => http.get<IncidentePublico>(`/public/incidents/${encodeURIComponent(id)}`).then((r) => r.data),

  // ---- Autenticación
  login: (username: string, password: string) =>
    http.post<{ access_token: string; user: Usuario }>('/auth/login', { username, password }).then((r) => r.data),
  yo: () => http.get<Usuario>('/auth/me').then((r) => r.data),

  // ---- Incidentes
  incidentes: (params: Record<string, string | number | undefined>) =>
    http.get<{ total: number; items: Incidente[] }>('/admin/incidents', { params }).then((r) => r.data),
  incidente: (id: string) => http.get<Incidente>(`/admin/incidents/${id}`).then((r) => r.data),
  crearIncidente: (datos: NuevoReporte) => http.post<Incidente>('/admin/incidents', datos).then((r) => r.data),
  actualizarIncidente: (id: string, datos: { priority?: number; type?: string; description?: string }) =>
    http.patch<Incidente>(`/admin/incidents/${id}`, datos).then((r) => r.data),
  nota: (id: string, detalle: string) => http.post<Incidente>(`/admin/incidents/${id}/notes`, { detalle }).then((r) => r.data),
  despachar: (id: string) =>
    http.post<{ assigned: unknown[]; missing: Record<string, number>; incident: Incidente }>(`/admin/incidents/${id}/dispatch`).then((r) => r.data),
  vistaPrevia: (id: string) => http.get<VistaPrevia>(`/admin/incidents/${id}/dispatch-preview`).then((r) => r.data),
  llegada: (id: string) => http.post<Incidente>(`/admin/incidents/${id}/arrive`).then((r) => r.data),
  resolver: (id: string, nota?: string) =>
    http.post<{ incident: Incidente; queue_dispatched: { incidente_id: string; asignadas: string[] }[] }>(
      `/admin/incidents/${id}/resolve`, { nota: nota || null }).then((r) => r.data),
  cancelar: (id: string, motivo?: string) =>
    http.post<{ incident: Incidente; queue_dispatched: { incidente_id: string; asignadas: string[] }[] }>(
      `/admin/incidents/${id}/cancel`, { motivo: motivo || null }).then((r) => r.data),

  // ---- Despacho
  cola: () => http.get<FilaCola[]>('/admin/dispatch/queue').then((r) => r.data),
  procesarCola: () =>
    http.post<{ dispatched: { incidente_id: string; asignadas: string[] }[]; remaining: FilaCola[] }>('/admin/dispatch/process-queue').then((r) => r.data),
  asignarManual: (incident_id: string, resource_code: string) =>
    http.post<Incidente>('/admin/dispatch/manual', { incident_id, resource_code }).then((r) => r.data),

  // ---- Recursos
  recursos: () => http.get<Recurso[]>('/admin/resources').then((r) => r.data),
  crearRecurso: (datos: { code: string; type: string; name: string } & BaseUnidad) =>
    http.post<Recurso>('/admin/resources', datos).then((r) => r.data),
  actualizarRecurso: (code: string, datos: { name?: string; status?: string } & Partial<BaseUnidad>) =>
    http.patch<Recurso>(`/admin/resources/${code}`, datos).then((r) => r.data),
  retornarBase: (code: string) => http.post<Recurso>(`/admin/resources/${code}/return-base`).then((r) => r.data),
  eliminarRecurso: (code: string) => http.delete(`/admin/resources/${code}`),

  // ---- Red vial
  red: () => http.get<RedVial>('/admin/network').then((r) => r.data),
  ruta: (origen: number, destino: number) =>
    http.get<ResultadoRuta>('/admin/network/route', { params: { origen, destino } }).then((r) => r.data),
  cerrarVia: (node_a: number, node_b: number, reason: string) =>
    http.post<Cierre>('/admin/network/closures', { node_a, node_b, reason }).then((r) => r.data),
  reabrirVia: (id: number) => http.delete(`/admin/network/closures/${id}`),

  // ---- Analítica y reportes
  kpis: (dias = 30) => http.get<Kpis>('/admin/analytics/kpis', { params: { dias } }).then((r) => r.data),
  resumen: (dias = 30) => http.get<Resumen>('/admin/analytics/summary', { params: { dias } }).then((r) => r.data),
  descargarPdf: (dias: number) => descargar(`/admin/reports/pdf?dias=${dias}`, `reporte_emergencias_${dias}d.pdf`),
  descargarCsv: (dias: number) => descargar(`/admin/reports/csv?dias=${dias}`, `incidentes_${dias}d.csv`),

  // ---- Usuarios
  usuarios: () => http.get<Usuario[]>('/admin/users').then((r) => r.data),
  rolesUsuarios: () => http.get<CatalogoRoles>('/admin/users/roles').then((r) => r.data),
  crearUsuario: (datos: { username: string; password: string; full_name: string; role: string; permissions?: Partial<Permisos> }) =>
    http.post<Usuario>('/admin/users', datos).then((r) => r.data),
  actualizarUsuario: (id: number, datos: {
    full_name?: string; role?: string; is_active?: boolean; password?: string
    permissions?: Partial<Permisos>; reset_permissions?: boolean
  }) => http.patch<Usuario>(`/admin/users/${id}`, datos).then((r) => r.data),
}
