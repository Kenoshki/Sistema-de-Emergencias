import { Building, CarFront, Flame, HeartPulse, Mountain, ShieldAlert, type LucideIcon } from 'lucide-react'
import type { IncidentType } from '../lib/types'

export const ICONO_INCIDENTE: Record<IncidentType, LucideIcon> = {
  fire: Flame,
  accident: CarFront,
  collapse: Building,
  landslide: Mountain,
  medical: HeartPulse,
  robbery: ShieldAlert,
}

export const TEXTO_INCIDENTE: Record<IncidentType, { titulo: string; ejemplo: string }> = {
  fire: { titulo: 'Incendio', ejemplo: 'Vivienda, comercio, maleza' },
  accident: { titulo: 'Accidente de tránsito', ejemplo: 'Choque, atropello, motorista' },
  collapse: { titulo: 'Colapso o sismo', ejemplo: 'Muro, techo, edificio dañado' },
  landslide: { titulo: 'Deslave o inundación', ejemplo: 'Tierra en la vía, agua crecida' },
  medical: { titulo: 'Emergencia médica', ejemplo: 'Desmayo, dolor de pecho' },
  robbery: { titulo: 'Robo o asalto', ejemplo: 'Ocurriendo en este momento' },
}

export function IconoIncidente({ tipo, className = 'size-5' }: { tipo: IncidentType; className?: string }) {
  const Icono = ICONO_INCIDENTE[tipo] ?? ShieldAlert
  return <Icono className={className} aria-hidden />
}
