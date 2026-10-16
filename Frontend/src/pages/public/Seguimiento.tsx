import { ArrowLeft, Check, RefreshCw, Siren } from 'lucide-react'
import { Aviso, Boton, Cargando, Prioridad } from '../../components/ui'
import { api } from '../../lib/api'
import { hace, hora } from '../../lib/format'
import { useDatos, useReloj } from '../../lib/hooks'
import { navegar } from '../../lib/router'
import type { IncidentePublico } from '../../lib/types'

const PASOS = [
  { clave: 'reported_at', titulo: 'Reporte recibido' },
  { clave: 'dispatched_at', titulo: 'Unidades en camino' },
  { clave: 'arrived_at', titulo: 'Unidades en el lugar' },
  { clave: 'resolved_at', titulo: 'Emergencia atendida' },
] as const

function minutosRestantes(asignado: string, eta: number): number {
  const transcurrido = (Date.now() - new Date(asignado).getTime()) / 60000
  return Math.max(0, Math.round(eta - transcurrido))
}

export function Seguimiento({ codigo }: { codigo: string }) {
  useReloj(20000)
  const { datos, error, cargando, recargar } = useDatos<IncidentePublico>(() => api.seguimiento(codigo), [codigo], 15000)

  return (
    <div className="min-h-screen bg-paper">
      <header className="bg-ink text-white">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3">
          <a href="#/" className="flex items-center gap-2.5">
            <span className="grid size-9 place-items-center rounded-md bg-critical"><Siren className="size-5" aria-hidden /></span>
            <span className="font-display text-xl font-semibold">Emergencias Guatemala</span>
          </a>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-8">
        <button onClick={() => navegar('/')} className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">
          <ArrowLeft className="size-4" /> Volver a reportar
        </button>

        {cargando && !datos && <Cargando />}
        {error && !datos && <Aviso>{error}</Aviso>}

        {datos && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <p className="text-sm text-muted">Reporte</p>
                <h1 className="num font-display text-3xl font-bold sm:text-4xl">{datos.id}</h1>
                <p className="mt-1 flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-semibold">{datos.type_label}</span>
                  <span className="text-muted">{datos.location_label}</span>
                  <Prioridad valor={datos.priority} />
                </p>
              </div>
              <Boton variante="secundario" onClick={recargar} icono={<RefreshCw className="size-4" />}>Actualizar</Boton>
            </div>

            {datos.status === 'cancelled' ? (
              <Aviso tipo="info">Este reporte fue cancelado por el centro de despacho.</Aviso>
            ) : (
              <ol className="grid gap-0 rounded-lg border border-line bg-surface sm:grid-cols-4">
                {PASOS.map((p, i) => {
                  const cuando = datos[p.clave]
                  const hecho = Boolean(cuando)
                  const actual = hecho && !datos[PASOS[i + 1]?.clave as keyof IncidentePublico]
                  return (
                    <li key={p.clave} className={`flex items-center gap-3 border-line p-4 sm:flex-col sm:items-start sm:gap-2 ${i ? 'border-t sm:border-l sm:border-t-0' : ''}`}>
                      <span className={`grid size-8 shrink-0 place-items-center rounded-full text-sm font-bold ${
                        hecho ? (actual && datos.status !== 'resolved' ? 'bg-route text-white' : 'bg-ok text-white') : 'border-2 border-line text-muted'}`}>
                        {hecho ? <Check className="size-4" /> : i + 1}
                      </span>
                      <span>
                        <span className={`block text-sm font-semibold ${hecho ? '' : 'text-muted'}`}>{p.titulo}</span>
                        <span className="num block text-xs text-muted">{hecho ? hora(cuando) : 'Pendiente'}</span>
                      </span>
                    </li>
                  )
                })}
              </ol>
            )}

            {datos.units.length > 0 && (
              <section className="rounded-lg border border-line bg-surface">
                <h2 className="border-b border-line px-5 py-3 font-display text-xl font-semibold">Unidades asignadas</h2>
                <ul className="divide-y divide-line">
                  {datos.units.map((u) => {
                    const resta = minutosRestantes(u.assigned_at, u.eta_min)
                    return (
                      <li key={u.code} className="flex items-center justify-between px-5 py-3">
                        <span><strong>{u.type_label}</strong> <span className="text-muted">{u.code}</span></span>
                        <span className="num text-right text-sm">
                          {datos.status === 'on_scene' ? <strong className="text-ok">En el lugar</strong>
                            : resta > 0 ? <><strong className="text-lg">~{resta} min</strong><span className="block text-xs text-muted">{u.distance_km} km</span></>
                              : <strong>Llegando</strong>}
                        </span>
                      </li>
                    )
                  })}
                </ul>
              </section>
            )}

            {Object.keys(datos.waiting_for).length > 0 && (
              <Aviso tipo="info">
                Esperando unidades libres: {Object.entries(datos.waiting_for).map(([t, n]) => `${n} ${t}`).join(', ')}.
                Se asignarán automáticamente en cuanto se libere una.
              </Aviso>
            )}

            <section>
              <h2 className="mb-3 font-display text-xl font-semibold">Historial</h2>
              <ol className="relative space-y-4 border-l-2 border-line pl-5">
                {[...datos.events].reverse().map((e, i) => (
                  <li key={i} className="relative">
                    <span className="absolute -left-[27px] top-1.5 size-3 rounded-full border-2 border-paper bg-ink" aria-hidden />
                    <p className="text-sm">{e.detail}</p>
                    <p className="num text-xs text-muted">{hora(e.timestamp)} · {hace(e.timestamp)}</p>
                  </li>
                ))}
              </ol>
            </section>
            <p className="text-xs text-muted">Esta página se actualiza sola cada 15 segundos.</p>
          </div>
        )}
      </main>
    </div>
  )
}
