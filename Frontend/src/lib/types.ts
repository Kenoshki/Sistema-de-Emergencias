// Tipos de los datos que devuelve el backend.

export type IncidentType = 'fire' | 'accident' | 'collapse' | 'landslide' | 'medical' | 'robbery'
export type IncidentStatus = 'pending' | 'dispatched' | 'on_scene' | 'resolved' | 'cancelled'
export type ResourceType = 'ambulance' | 'firefighters' | 'police' | 'rescue'
export type ResourceStatus = 'available' | 'dispatched' | 'on_scene' | 'maintenance'

export interface Opcion<T = string> {
  value: T
  label: string
}

export interface DepartamentoOpcion extends Opcion<string> {
  lat: number
  lon: number
}

export interface MunicipioOpcion extends Opcion<string> {
  department: string
  lat: number
  lon: number
  zones: Opcion<number>[] | null
  has_places: boolean
}

export interface Catalogos {
  incident_types: Opcion<IncidentType>[]
  resource_types: Opcion<ResourceType>[]
  priorities: Opcion<number>[]
  statuses: Opcion<IncidentStatus>[]
  departments: DepartamentoOpcion[]
  municipalities: MunicipioOpcion[]
}

/** Ubicación elegida en el formulario (departamento → municipio → zona → lugar). */
export interface UbicacionForm {
  department_code: string
  municipality_code: string
  zone: number | null
  place_id: number | null
  place_name: string
}

export interface Lugar {
  id: number
  name: string
  category: string
}

export interface ResultadoUbicar {
  inside: boolean
  department_code?: string
  municipality_code?: string
  zone?: number | null
  label?: string
  distance_km?: number
}

export interface Asignacion {
  id: number
  incident_id: string
  resource_code: string
  resource_type: ResourceType | null
  resource_type_label: string | null
  resource_name: string | null
  resource_status: ResourceStatus | null
  origin_node: number
  origin_label: string
  distance_km: number
  eta_min: number
  route: number[]
  method: 'auto' | 'manual'
  active: boolean
  assigned_at: string
  released_at: string | null
}

export interface Evento {
  id: number
  timestamp: string
  event: string
  detail: string
  username: string | null
  public: boolean
}

export interface Incidente {
  id: string
  type: IncidentType
  type_label: string
  priority: number
  priority_label: string
  department_code: string
  department_name: string
  municipality_code: string
  municipality_name: string
  zone: number | null
  place_id: number | null
  place_name: string | null
  node: number
  location_label: string
  location_source: 'form' | 'gps'
  latitude: number
  longitude: number
  address: string | null
  description: string | null
  reporter_name: string | null
  reporter_phone: string | null
  source: 'public' | 'operator'
  status: IncidentStatus
  status_label: string
  pending_requirements: Partial<Record<ResourceType, number>>
  reported_at: string
  dispatched_at: string | null
  arrived_at: string | null
  resolved_at: string | null
  dispatch_time_min: number | null
  response_time_min: number | null
  active_units: string[]
  assignments?: Asignacion[]
  events?: Evento[]
}

export interface IncidentePublico {
  id: string
  type_label: string
  priority: number
  priority_label: string
  location_label: string
  status: IncidentStatus
  status_label: string
  reported_at: string
  dispatched_at: string | null
  arrived_at: string | null
  resolved_at: string | null
  units: { code: string; type_label: string; eta_min: number; distance_km: number; assigned_at: string }[]
  waiting_for: Record<string, number>
  events: { timestamp: string; detail: string }[]
}

export interface Recurso {
  code: string
  type: ResourceType
  type_label: string
  name: string
  base_node: number
  base_label: string
  base_department_code: string | null
  base_municipality_code: string
  base_zone: number | null
  current_node: number
  current_label: string
  department_code: string | null
  status: ResourceStatus
  status_label: string
  incident_id: string | null
  updated_at: string
}

/** Módulos del centro de despacho. Niveles: 0 sin acceso · 1 ver · 2 editar. */
export type Modulo = 'panel' | 'incidentes' | 'despacho' | 'flota' | 'red' | 'reportes'
export type Nivel = 0 | 1 | 2
export type Permisos = Record<Modulo, Nivel>

export interface Usuario {
  id: number
  username: string
  full_name: string
  role: string   // admin | incidentes | flota | red_vial | operator
  role_label: string
  is_active: boolean
  created_at: string
  permissions: Permisos
  custom_permissions: boolean
}

export interface CatalogoRoles {
  modules: { value: Modulo; label: string; view: string; edit: string; read_only: boolean }[]
  roles: { value: string; label: string; description: string; permissions: Permisos }[]
  levels: { value: Nivel; label: string }[]
}

export interface Kpis {
  window_days: number
  total_incidents: number
  previous_total_incidents: number
  incidents_change_pct: number | null
  active_incidents: number
  critical_active: number
  incidents_today: number
  avg_response_time_min: number | null
  previous_avg_response_time_min: number | null
  response_time_change_pct: number | null
  p90_response_time_min: number | null
  avg_dispatch_time_min: number | null
  target_compliance_pct: number | null
  attended_incidents: number
  highest_risk_node: number | null
  highest_risk_label: string | null
  risk_ranking: { node: number; label: string; incidents: number; critical: number; risk_index: number }[]
  fleet_total: number
  fleet_busy: number
  fleet_available: number
  fleet_maintenance: number
  fleet_utilization_pct: number
}

export interface Resumen {
  window_days: number
  by_type: { type: IncidentType; label: string; count: number }[]
  by_location: { node: number; label: string; count: number; risk_index: number }[]
  by_department: { department_code: string; label: string; count: number; risk_index: number }[]
  daily_trend: { date: string; total: number; high_or_critical: number }[]
  by_priority: { priority: number; label: string; count: number; avg_response_min: number | null; target_min: number }[]
  by_hour: { hour: number; count: number }[]
}

export interface Candidato {
  codigo: string
  tipo: ResourceType
  nodo_origen: number
  distancia_km: number
  eta_min: number
  ruta: number[]
}

export interface VistaPrevia {
  incident_node: number
  ranking: Partial<Record<ResourceType, Candidato[]>>
  would_assign: string[]
  missing: Partial<Record<ResourceType, number>>
}

export interface FilaCola {
  posicion: number
  incidente_id: string
  prioridad: number
  prioridad_efectiva: number
  reportado: string
  tipo: IncidentType
  nodo: number
  ubicacion: string
  estado: IncidentStatus
  faltantes: Partial<Record<ResourceType, number>>
  minutos_espera: number
}

export interface Nodo {
  node: number
  kind: 'zona' | 'municipio'
  name: string
  detail: string
  label: string
  lat: number
  lon: number
  municipality_code: string
  department_code: string
  department_head: boolean
}

export interface Arista {
  origen: number
  destino: number
  distancia_km: number
  cerrada: boolean
}

export interface Cierre {
  id: number
  node_a: number
  node_b: number
  label_a: string
  label_b: string
  reason: string
  created_by: string | null
  created_at: string
}

export interface RedVial {
  nodes: Nodo[]
  edges: Arista[]
  closures: Cierre[]
  connected: boolean
}

export interface ResultadoRuta {
  origen: number
  destino: number
  alcanzable: boolean
  distancia_km: number | null
  camino: number[]
  origen_label: string
  destino_label: string
  tramos: { desde: number; hasta: number; desde_label: string; hasta_label: string; distancia_km: number }[]
  orden_visita: number[]
  distancias_desde_origen: Record<string, number | null>
  verificacion_networkx: { distancia_km: number | null; camino: number[]; coincide: boolean }
}
