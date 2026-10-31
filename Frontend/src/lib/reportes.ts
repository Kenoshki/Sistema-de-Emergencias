import axios from 'axios'
import { api, type NuevoReporte } from './api'
import type { IncidentePublico } from './types'

/**
 * Envío de reportes pensado para mala señal:
 *  - reintenta solo (con espera creciente) ante cortes o errores del servidor,
 *  - si no hay conexión, guarda el reporte en el teléfono y lo envía cuando vuelva la señal,
 *  - cada envío lleva un identificador único, así un reintento nunca duplica el reporte.
 */
const CLAVE_COLA = 'ems_cola_reportes'
export const EVENTO_ENVIADO = 'ems:reporte-enviado'
export const EVENTO_COLA = 'ems:cola-cambio'
const ESPERAS_MS = [1500, 4000]

interface Pendiente { datos: NuevoReporte; creado: number }

export function nuevoIdEnvio(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

function leerCola(): Pendiente[] {
  try { return JSON.parse(localStorage.getItem(CLAVE_COLA) || '[]') as Pendiente[] } catch { return [] }
}
function guardarCola(cola: Pendiente[]) {
  try { localStorage.setItem(CLAVE_COLA, JSON.stringify(cola)) } catch { /* almacenamiento no disponible */ }
  window.dispatchEvent(new Event(EVENTO_COLA))
}

export function pendientes(): number { return leerCola().length }

/** ¿Vale la pena reintentar? Sí ante cortes/tiempo agotado o error del servidor; no ante errores de datos o límites. */
function reintentable(err: unknown): boolean {
  if (!axios.isAxiosError(err)) return false
  if (!err.response) return true
  return err.response.status >= 500
}

const dormir = (ms: number) => new Promise((r) => setTimeout(r, ms))

export type ResultadoEnvio =
  | { estado: 'enviado'; resultado: IncidentePublico }
  | { estado: 'en-cola' }

/** Envía el reporte; si no se puede por falta de conexión lo deja en cola. Los errores de datos se propagan. */
export async function enviarReporte(datos: NuevoReporte): Promise<ResultadoEnvio> {
  const conId: NuevoReporte = { ...datos, client_request_id: datos.client_request_id ?? nuevoIdEnvio() }
  let ultimo: unknown
  for (let i = 0; i <= ESPERAS_MS.length; i++) {
    try {
      const r = await api.reportar(conId)
      return { estado: 'enviado', resultado: r.data }
    } catch (err) {
      ultimo = err
      if (!reintentable(err)) throw err
      if (i < ESPERAS_MS.length) await dormir(ESPERAS_MS[i])
    }
  }
  if (axios.isAxiosError(ultimo) && !ultimo.response) {
    guardarCola([...leerCola(), { datos: conId, creado: Date.now() }])
    iniciarVigilancia()
    return { estado: 'en-cola' }
  }
  throw ultimo
}

let vaciando = false
/** Intenta enviar lo guardado. Se llama sola al volver la conexión y cada 30 s mientras haya pendientes. */
export async function vaciarCola(): Promise<void> {
  if (vaciando) return
  vaciando = true
  try {
    let cola = leerCola()
    while (cola.length) {
      const [primero, ...resto] = cola
      try {
        const r = await api.reportar(primero.datos)
        guardarCola(resto)
        cola = resto
        window.dispatchEvent(new CustomEvent(EVENTO_ENVIADO, { detail: r.data }))
      } catch (err) {
        if (reintentable(err)) break // sigue sin señal: se intenta más tarde
        guardarCola(resto) // el servidor lo rechazó por datos: no tiene sentido reintentar
        cola = resto
      }
    }
  } finally {
    vaciando = false
  }
}

let vigilando = false
export function iniciarVigilancia() {
  if (vigilando || typeof window === 'undefined') return
  vigilando = true
  window.addEventListener('online', () => { void vaciarCola() })
  window.setInterval(() => { if (pendientes() > 0) void vaciarCola() }, 30000)
  if (pendientes() > 0) void vaciarCola()
}
