import { useEffect, type ReactNode } from 'react'
import { NotificacionesProvider } from './components/Notificaciones'
import { Aviso, Cargando } from './components/ui'
import { AuthProvider, useAuth } from './lib/auth'
import type { Modulo } from './lib/types'
import { coincide, navegar, useRuta } from './lib/router'
import { AdminLayout, MENU } from './pages/admin/AdminLayout'
import { Despacho } from './pages/admin/Despacho'
import { Flota } from './pages/admin/Flota'
import { IncidenteDetalle } from './pages/admin/IncidenteDetalle'
import { Incidentes } from './pages/admin/Incidentes'
import { Login } from './pages/admin/Login'
import { Panel } from './pages/admin/Panel'
import { RedVial } from './pages/admin/RedVial'
import { Reportes } from './pages/admin/Reportes'
import { Usuarios } from './pages/admin/Usuarios'
import { PortalPublico } from './pages/public/PortalPublico'
import { Seguimiento } from './pages/public/Seguimiento'

function Rutas() {
  const ruta = useRuta()
  const { usuario, verificando, puede, esAdmin } = useAuth()
  const limpia = ruta.split('?')[0]
  const enAdmin = limpia.startsWith('/admin') && limpia !== '/admin/login'

  // Proteger el área administrativa
  useEffect(() => {
    if (!verificando && enAdmin && !usuario) navegar('/admin/login')
    if (!verificando && limpia === '/admin/login' && usuario) navegar('/admin')
  }, [verificando, enAdmin, usuario, limpia])

  // ---- Público
  const seg = coincide('/seguimiento/:codigo', ruta)
  if (seg) return <Seguimiento codigo={seg.codigo} />
  if (limpia === '/admin/login') return <Login />
  if (!enAdmin) return <PortalPublico />

  // ---- Administrativo
  if (verificando || !usuario) return <Cargando texto="Verificando sesión…" />

  const sinAcceso = (titulo: string) => (
    <AdminLayout ruta={limpia} titulo={titulo}>
      <Aviso>Su usuario no tiene acceso a este módulo. Si lo necesita, pídale al administrador que le asigne el permiso.</Aviso>
    </AdminLayout>
  )

  const det = coincide('/admin/incidentes/:id', ruta)
  if (det) {
    if (!puede(['incidentes', 'despacho', 'panel'])) return sinAcceso('Detalle del incidente')
    return <AdminLayout ruta={limpia} titulo="Detalle del incidente"><IncidenteDetalle id={det.id} /></AdminLayout>
  }

  // [título, contenido, módulo requerido (null = solo administrador)]
  const paginas: Record<string, [string, ReactNode, Modulo | null]> = {
    '/admin': ['Panel de control', <Panel />, 'panel'],
    '/admin/incidentes': ['Incidentes', <Incidentes ruta={ruta} key={ruta} />, 'incidentes'],
    '/admin/despacho': ['Despacho y cola de espera', <Despacho />, 'despacho'],
    '/admin/flota': ['Flota', <Flota />, 'flota'],
    '/admin/red': ['Red vial y rutas', <RedVial />, 'red'],
    '/admin/reportes': ['Reportes', <Reportes />, 'reportes'],
    '/admin/usuarios': ['Usuarios y permisos', <Usuarios />, null],
  }
  const pagina = paginas[limpia] ?? paginas['/admin']
  const permitida = (modulo: Modulo | null) => (modulo ? puede(modulo) : esAdmin)
  if (!permitida(pagina[2])) {
    // Al entrar sin permiso al panel, se abre el primer módulo que sí tenga.
    const primero = MENU.find((i) => permitida(i.modulo ?? null))
    if ((limpia === '/admin' || !paginas[limpia]) && primero && primero.ruta !== '/admin') {
      window.setTimeout(() => navegar(primero.ruta), 0)
      return <Cargando />
    }
    return sinAcceso(pagina[0])
  }
  return <AdminLayout ruta={limpia} titulo={pagina[0]}>{pagina[1]}</AdminLayout>
}

export default function App() {
  return (
    <AuthProvider>
      <NotificacionesProvider>
        <Rutas />
      </NotificacionesProvider>
    </AuthProvider>
  )
}
