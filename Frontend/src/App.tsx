import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import { NotificacionesProvider } from './components/Notificaciones'
import { Aviso, Cargando } from './components/ui'
import { AuthProvider, useAuth } from './lib/auth'
import type { Modulo } from './lib/types'
import { MENU } from './pages/admin/menu'
import { coincide, navegar, useRuta } from './lib/router'
import { PortalPublico } from './pages/public/PortalPublico'
import { Seguimiento } from './pages/public/Seguimiento'

// Las pantallas del centro de despacho (con mapas y gráficas) se descargan solo al entrar a ellas:
// el portal ciudadano queda mucho más liviano para quien tiene mala señal.
const AdminLayout = lazy(() => import('./pages/admin/AdminLayout').then((m) => ({ default: m.AdminLayout })))
const Despacho = lazy(() => import('./pages/admin/Despacho').then((m) => ({ default: m.Despacho })))
const Flota = lazy(() => import('./pages/admin/Flota').then((m) => ({ default: m.Flota })))
const IncidenteDetalle = lazy(() => import('./pages/admin/IncidenteDetalle').then((m) => ({ default: m.IncidenteDetalle })))
const Incidentes = lazy(() => import('./pages/admin/Incidentes').then((m) => ({ default: m.Incidentes })))
const Login = lazy(() => import('./pages/admin/Login').then((m) => ({ default: m.Login })))
const Panel = lazy(() => import('./pages/admin/Panel').then((m) => ({ default: m.Panel })))
const RecuperarContrasena = lazy(() => import('./pages/admin/RecuperarContrasena').then((m) => ({ default: m.RecuperarContrasena })))
const RedVial = lazy(() => import('./pages/admin/RedVial').then((m) => ({ default: m.RedVial })))
const Reportes = lazy(() => import('./pages/admin/Reportes').then((m) => ({ default: m.Reportes })))
const Usuarios = lazy(() => import('./pages/admin/Usuarios').then((m) => ({ default: m.Usuarios })))

function Rutas() {
  const ruta = useRuta()
  const { usuario, verificando, puede, esAdmin } = useAuth()
  const limpia = ruta.split('?')[0]
  const restablecer = coincide('/admin/restablecer/:token', ruta)
  const enRecuperacion = limpia === '/admin/recuperar' || restablecer !== null
  const enAdmin = limpia.startsWith('/admin') && limpia !== '/admin/login' && !enRecuperacion

  // Proteger el área administrativa
  useEffect(() => {
    if (!verificando && enAdmin && !usuario) navegar('/admin/login')
    if (!verificando && limpia === '/admin/login' && usuario) navegar('/admin')
  }, [verificando, enAdmin, usuario, limpia])

  // ---- Público
  const seg = coincide('/seguimiento/:codigo', ruta)
  if (seg) return <Seguimiento codigo={seg.codigo} />
  if (enRecuperacion) return <RecuperarContrasena token={restablecer?.token ?? null} />
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
        <Suspense fallback={<Cargando />}>
          <Rutas />
        </Suspense>
      </NotificacionesProvider>
    </AuthProvider>
  )
}
