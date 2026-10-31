import { LogOut, Menu, Plus, Siren, X } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { Boton } from '../../components/ui'
import { useAuth } from '../../lib/auth'
import { useReloj } from '../../lib/hooks'
import { navegar } from '../../lib/router'
import type { Incidente } from '../../lib/types'
import { FormIncidente } from './FormIncidente'
import { MENU, type Item } from './menu'

export function AdminLayout({ ruta, titulo, children, onIncidenteCreado }: {
  ruta: string; titulo: string; children: ReactNode; onIncidenteCreado?: (inc: Incidente) => void
}) {
  const { usuario, cerrarSesion, puede, esAdmin } = useAuth()
  const [menuAbierto, setMenuAbierto] = useState(false)
  const [formAbierto, setFormAbierto] = useState(false)
  useReloj(30000)

  useEffect(() => setMenuAbierto(false), [ruta])

  const activo = (item: Item) =>
    item.ruta === '/admin' ? ruta === '/admin' : ruta === item.ruta || ruta.startsWith(item.ruta + '/')

  const items = MENU.filter((i) => (i.modulo ? puede(i.modulo) : esAdmin))

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[220px_1fr]">
      {/* Barra lateral */}
      <aside className={`fixed inset-y-0 left-0 z-40 w-64 bg-ink text-white transition-transform lg:static lg:w-auto lg:translate-x-0 ${menuAbierto ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between px-4 py-4">
            <a href="#/admin" className="flex items-center gap-2">
              <span className="grid size-8 place-items-center rounded bg-critical"><Siren className="size-4" aria-hidden /></span>
              <span className="font-display text-lg font-semibold leading-none">Despacho<br /><span className="text-xs font-medium text-white/60">DWG EMS-05</span></span>
            </a>
            <button className="lg:hidden" onClick={() => setMenuAbierto(false)} aria-label="Cerrar menú"><X className="size-5" /></button>
          </div>
          <nav className="flex-1 space-y-0.5 px-2 py-2" aria-label="Secciones">
            {items.map((item) => {
              const Icono = item.icono
              const sel = activo(item)
              return (
                <a key={item.ruta} href={`#${item.ruta}`} aria-current={sel ? 'page' : undefined}
                  className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    sel ? 'bg-white text-ink' : 'text-white/75 hover:bg-white/10 hover:text-white'}`}>
                  <Icono className="size-4" aria-hidden /> {item.titulo}
                </a>
              )
            })}
          </nav>
          <div className="border-t border-white/10 p-3">
            <p className="truncate text-sm font-semibold">{usuario?.full_name || usuario?.username}</p>
            <p className="text-xs text-white/60">{usuario?.role_label}</p>
            <button onClick={cerrarSesion} className="mt-2 flex items-center gap-2 text-sm text-white/75 hover:text-white">
              <LogOut className="size-4" /> Cerrar sesión
            </button>
          </div>
        </div>
      </aside>
      {menuAbierto && <div className="fixed inset-0 z-30 bg-ink/40 lg:hidden" onClick={() => setMenuAbierto(false)} />}

      {/* Contenido */}
      <div className="min-w-0">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-paper/95 px-4 py-3 backdrop-blur sm:px-6">
          <button className="lg:hidden" onClick={() => setMenuAbierto(true)} aria-label="Abrir menú"><Menu className="size-5" /></button>
          <h1 className="font-display text-2xl font-bold leading-none">{titulo}</h1>
          <span className="num ml-auto hidden text-sm text-muted sm:block">
            {new Date().toLocaleString('es-GT', { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}
          </span>
          {puede('incidentes', 2) && (
            <Boton variante="peligro" onClick={() => setFormAbierto(true)} icono={<Plus className="size-4" />} className="ml-auto sm:ml-0" aria-label="Nuevo incidente">
              <span className="hidden sm:inline">Nuevo incidente</span>
            </Boton>
          )}
        </header>
        <main className="px-4 py-6 sm:px-6">{children}</main>
      </div>

      <FormIncidente
        abierto={formAbierto}
        onCerrar={() => setFormAbierto(false)}
        onCreado={(inc) => {
          setFormAbierto(false)
          if (onIncidenteCreado) onIncidenteCreado(inc)
          else navegar(`/admin/incidentes/${inc.id}`)
        }}
      />
    </div>
  )
}
