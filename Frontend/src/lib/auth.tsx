import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from './api'
import { navegar } from './router'
import type { Modulo, Nivel, Usuario } from './types'

interface AuthState {
  usuario: Usuario | null
  verificando: boolean
  iniciarSesion: (username: string, password: string) => Promise<void>
  cerrarSesion: () => void
  /** ¿Tiene al menos `nivel` (1 ver, 2 editar) en alguno de los módulos? */
  puede: (modulos: Modulo | Modulo[], nivel?: Nivel) => boolean
  esAdmin: boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [verificando, setVerificando] = useState(true)

  const cerrarSesion = useCallback(() => {
    setToken(null)
    setUsuario(null)
    navegar('/admin/login')
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(cerrarSesion)
    if (!getToken()) {
      setVerificando(false)
      return
    }
    api.yo()
      .then(setUsuario)
      .catch(() => setToken(null))
      .finally(() => setVerificando(false))
    return () => setUnauthorizedHandler(null)
  }, [cerrarSesion])

  const iniciarSesion = useCallback(async (username: string, password: string) => {
    const r = await api.login(username, password)
    setToken(r.access_token)
    setUsuario(r.user)
  }, [])

  // Si el administrador cambia los permisos, se aplican al volver a esta pestaña.
  useEffect(() => {
    if (!usuario) return
    const refrescar = () => { if (document.visibilityState === 'visible') api.yo().then(setUsuario).catch(() => {}) }
    document.addEventListener('visibilitychange', refrescar)
    return () => document.removeEventListener('visibilitychange', refrescar)
  }, [usuario?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const puede = useCallback((modulos: Modulo | Modulo[], nivel: Nivel = 1) => {
    if (!usuario) return false
    return (Array.isArray(modulos) ? modulos : [modulos]).some((m) => (usuario.permissions?.[m] ?? 0) >= nivel)
  }, [usuario])
  const esAdmin = usuario?.role === 'admin'

  return (
    <AuthContext.Provider value={{ usuario, verificando, iniciarSesion, cerrarSesion, puede, esAdmin }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return ctx
}
