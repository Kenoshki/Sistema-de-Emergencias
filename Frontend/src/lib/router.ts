import { useEffect, useState } from 'react'

/**
 * Enrutador mínimo basado en el hash de la URL (#/admin/incidentes).
 * No requiere configurar el servidor y funciona al abrir el build directamente.
 */
export function rutaActual(): string {
  const h = window.location.hash.replace(/^#/, '')
  return h.startsWith('/') ? h : '/' + h
}

export function navegar(ruta: string) {
  if (rutaActual() !== ruta) window.location.hash = ruta
}

export function useRuta(): string {
  const [ruta, setRuta] = useState(rutaActual)
  useEffect(() => {
    const alCambiar = () => {
      setRuta(rutaActual())
      window.scrollTo(0, 0)
    }
    window.addEventListener('hashchange', alCambiar)
    return () => window.removeEventListener('hashchange', alCambiar)
  }, [])
  return ruta
}

/** Compara "/admin/incidentes/:id" con la ruta y devuelve los parámetros. */
export function coincide(patron: string, ruta: string): Record<string, string> | null {
  const p = patron.split('/').filter(Boolean)
  const r = ruta.split('?')[0].split('/').filter(Boolean)
  if (p.length !== r.length) return null
  const params: Record<string, string> = {}
  for (let i = 0; i < p.length; i++) {
    if (p[i].startsWith(':')) params[p[i].slice(1)] = decodeURIComponent(r[i])
    else if (p[i] !== r[i]) return null
  }
  return params
}
