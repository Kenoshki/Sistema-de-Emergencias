import { useCallback, useEffect, useRef, useState } from 'react'
import { mensajeError } from './api'

/**
 * Carga datos y los vuelve a pedir cada `intervaloMs` (0 = solo una vez).
 * Se pausa mientras la pestaña no está visible.
 */
export function useDatos<T>(cargar: () => Promise<T>, deps: unknown[] = [], intervaloMs = 0) {
  const [datos, setDatos] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cargando, setCargando] = useState(true)
  const cargarRef = useRef(cargar)
  cargarRef.current = cargar

  const recargar = useCallback(async () => {
    try {
      const d = await cargarRef.current()
      setDatos(d)
      setError(null)
    } catch (e) {
      setError(mensajeError(e))
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    setCargando(true)
    recargar()
    if (!intervaloMs) return
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') recargar()
    }, intervaloMs)
    return () => window.clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, intervaloMs])

  return { datos, error, cargando, recargar, setDatos }
}

/** Fuerza un re-render periódico (para relojes y "hace X min"). */
export function useReloj(intervaloMs = 30000) {
  const [, setTick] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), intervaloMs)
    return () => window.clearInterval(id)
  }, [intervaloMs])
}
