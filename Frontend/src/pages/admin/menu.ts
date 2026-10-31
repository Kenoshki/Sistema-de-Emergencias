import { FileDown, LayoutDashboard, Radio, Siren, Truck, Users, Waypoints, type LucideIcon } from 'lucide-react'
import type { Modulo } from '../../lib/types'

export interface Item { ruta: string; titulo: string; icono: LucideIcon; modulo?: Modulo }

/** Menú del centro de despacho. Cada opción aparece solo si el usuario puede ver su módulo. */
export const MENU: Item[] = [
  { ruta: '/admin', titulo: 'Panel', icono: LayoutDashboard, modulo: 'panel' },
  { ruta: '/admin/incidentes', titulo: 'Incidentes', icono: Siren, modulo: 'incidentes' },
  { ruta: '/admin/despacho', titulo: 'Despacho', icono: Radio, modulo: 'despacho' },
  { ruta: '/admin/flota', titulo: 'Flota', icono: Truck, modulo: 'flota' },
  { ruta: '/admin/red', titulo: 'Red vial', icono: Waypoints, modulo: 'red' },
  { ruta: '/admin/reportes', titulo: 'Reportes', icono: FileDown, modulo: 'reportes' },
  { ruta: '/admin/usuarios', titulo: 'Usuarios y permisos', icono: Users },  // solo administrador
]
