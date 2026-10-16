import { CircleCheck, CircleX, TriangleAlert, X } from 'lucide-react'
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

type Tipo = 'success' | 'error' | 'alert'
interface Notificacion { id: number; tipo: Tipo; mensaje: string }

const Ctx = createContext<(tipo: Tipo, mensaje: string) => void>(() => {})

const ESTILO: Record<Tipo, { clase: string; icono: ReactNode }> = {
  success: { clase: 'border-ok/40', icono: <CircleCheck className="size-5 shrink-0 text-ok" aria-hidden /> },
  error: { clase: 'border-critical/40', icono: <CircleX className="size-5 shrink-0 text-critical" aria-hidden /> },
  alert: { clase: 'border-high-fill/60', icono: <TriangleAlert className="size-5 shrink-0 text-high" aria-hidden /> },
}

/** Avisos flotantes (reemplaza a NotificacionFlotante, ahora con varias a la vez). */
export function NotificacionesProvider({ children }: { children: ReactNode }) {
  const [lista, setLista] = useState<Notificacion[]>([])

  const cerrar = useCallback((id: number) => setLista((l) => l.filter((n) => n.id !== id)), [])
  const notificar = useCallback((tipo: Tipo, mensaje: string) => {
    const id = Date.now() + Math.random()
    setLista((l) => [...l.slice(-3), { id, tipo, mensaje }])
    window.setTimeout(() => cerrar(id), tipo === 'error' ? 8000 : 5000)
  }, [cerrar])

  return (
    <Ctx.Provider value={notificar}>
      {children}
      <aside aria-live="polite" aria-label="Notificaciones" className="pointer-events-none fixed right-4 top-4 z-[60] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2">
        {lista.map((n) => (
          <div key={n.id} className={`pointer-events-auto flex items-start gap-3 rounded-lg border-l-4 bg-surface p-3 shadow-lg ${ESTILO[n.tipo].clase}`}>
            {ESTILO[n.tipo].icono}
            <p className="flex-1 text-sm">{n.mensaje}</p>
            <button onClick={() => cerrar(n.id)} className="text-muted hover:text-ink" aria-label="Cerrar notificación">
              <X className="size-4" />
            </button>
          </div>
        ))}
      </aside>
    </Ctx.Provider>
  )
}

export function useNotificar() {
  return useContext(Ctx)
}
