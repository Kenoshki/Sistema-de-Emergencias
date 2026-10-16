import { CircleCheck, LocateFixed, MapPin, Phone, Search, Send, Siren } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { IconoIncidente, TEXTO_INCIDENTE } from '../../components/iconos'
import {
  SelectorUbicacion, UBICACION_VACIA, textoUbicacion, validarUbicacion, type ErroresUbicacion,
} from '../../components/SelectorUbicacion'
import { Aviso, Boton, Campo, Cargando, claseInput } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'
import { useDatos } from '../../lib/hooks'
import { navegar } from '../../lib/router'
import type { IncidentePublico, IncidentType, UbicacionForm } from '../../lib/types'

const URGENCIAS = [
  { valor: 4, titulo: 'Crítico', texto: 'Hay vidas en peligro ahora mismo' },
  { valor: 3, titulo: 'Alto', texto: 'Hay heridos o el daño crece rápido' },
  { valor: 2, titulo: 'Medio', texto: 'Necesita atención pronto' },
  { valor: 1, titulo: 'Bajo', texto: 'Sin heridos ni riesgo inmediato' },
]

const CLASE_URGENCIA: Record<number, string> = {
  4: 'border-critical bg-critical text-white',
  3: 'border-high-fill bg-high-fill text-ink',
  2: 'border-medium bg-medium text-white',
  1: 'border-low bg-low text-white',
}

export function PortalPublico() {
  const { datos: cat, error: errorCat, cargando } = useDatos(api.catalogos)

  const [tipo, setTipo] = useState<IncidentType | null>(null)
  const [ubicacion, setUbicacion] = useState<UbicacionForm>(UBICACION_VACIA)
  const [coords, setCoords] = useState<{ lat: number; lon: number; municipio: string } | null>(null)
  const [detectado, setDetectado] = useState<string | null>(null)
  const [ubicando, setUbicando] = useState(false)
  const [intento, setIntento] = useState(false)
  const refUbicacion = useRef<HTMLFieldSetElement>(null)
  const [prioridad, setPrioridad] = useState<number | null>(null)
  const [descripcion, setDescripcion] = useState('')
  const [direccion, setDireccion] = useState('')
  const [nombre, setNombre] = useState('')
  const [telefono, setTelefono] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resultado, setResultado] = useState<IncidentePublico | null>(null)
  const [codigo, setCodigo] = useState('')

  const erroresUbicacion: ErroresUbicacion = intento ? validarUbicacion(ubicacion, cat) : {}

  const cambiarUbicacion = (u: UbicacionForm) => {
    // Si la persona corrige el municipio, el GPS ya no describe el lugar elegido.
    if (coords && u.municipality_code !== coords.municipio) {
      setCoords(null)
      setDetectado(null)
    }
    setUbicacion(u)
  }

  const usarUbicacion = () => {
    if (!navigator.geolocation) {
      setError('Su navegador no permite obtener la ubicación. Elija departamento y municipio en la lista.')
      return
    }
    setUbicando(true)
    navigator.geolocation.getCurrentPosition(
      async (p) => {
        try {
          const r = await api.ubicar(p.coords.latitude, p.coords.longitude)
          if (!r.inside || !r.municipality_code || !r.department_code) {
            setError('Su ubicación parece estar fuera de Guatemala. Elija departamento y municipio en la lista.')
            return
          }
          setUbicacion({ ...UBICACION_VACIA, department_code: r.department_code, municipality_code: r.municipality_code, zone: r.zone ?? null })
          setCoords({ lat: p.coords.latitude, lon: p.coords.longitude, municipio: r.municipality_code })
          setDetectado(r.label ?? null)
          setError(null)
        } catch (err) {
          setError(mensajeError(err, 'No se pudo identificar su ubicación. Elíjala en la lista.'))
        } finally {
          setUbicando(false)
        }
      },
      () => {
        setUbicando(false)
        setError('No se pudo obtener su ubicación. Elija departamento y municipio en la lista.')
      },
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setIntento(true)
    const erroresUbic = validarUbicacion(ubicacion, cat)
    const faltantes = [
      !tipo && 'el tipo de emergencia',
      Object.keys(erroresUbic).length > 0 && 'la ubicación completa',
      !prioridad && 'la urgencia',
    ].filter(Boolean)
    if (faltantes.length) {
      setError(`Falta indicar ${faltantes.join(', ')}.`)
      if (Object.keys(erroresUbic).length) refUbicacion.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      return
    }
    setEnviando(true)
    setError(null)
    try {
      const r = await api.reportar({
        type: tipo!,
        priority: prioridad!,
        department_code: ubicacion.department_code,
        municipality_code: ubicacion.municipality_code,
        zone: ubicacion.zone,
        place_id: ubicacion.place_id,
        place_name: ubicacion.place_name || undefined,
        latitude: coords?.lat ?? null,
        longitude: coords?.lon ?? null,
        address: direccion || undefined,
        description: descripcion || undefined,
        reporter_name: nombre || undefined,
        reporter_phone: telefono || undefined,
      })
      setResultado(r.data)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      setError(mensajeError(err, 'No se pudo enviar el reporte. Intente de nuevo o llame a los números de emergencia.'))
    } finally {
      setEnviando(false)
    }
  }

  const nuevoReporte = () => {
    setResultado(null)
    setTipo(null)
    setPrioridad(null)
    setDescripcion('')
    setDireccion('')
    setIntento(false)
  }

  return (
    <div className="min-h-screen bg-paper">
      <header className="bg-ink text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <a href="#/" className="flex items-center gap-2.5">
            <span className="grid size-9 place-items-center rounded-md bg-critical"><Siren className="size-5" aria-hidden /></span>
            <span className="font-display text-lg font-semibold leading-none sm:text-xl">Emergencias Guatemala</span>
          </a>
          <a href="#/admin/login" className="whitespace-nowrap rounded-md px-3 py-1.5 text-sm text-white/80 hover:bg-white/10 hover:text-white">
            Centro de despacho
          </a>
        </div>
      </header>

      <div className="border-b border-critical/20 bg-critical/5">
        <p className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 text-sm">
          <Phone className="size-4 text-critical" aria-hidden />
          <span>Si alguien corre peligro, llame también:</span>
          <span><a href="tel:122" className="font-bold underline-offset-2 hover:underline">122</a> Bomberos Voluntarios</span>
          <span><a href="tel:123" className="font-bold underline-offset-2 hover:underline">123</a> Bomberos Municipales</span>
          <span><a href="tel:110" className="font-bold underline-offset-2 hover:underline">110</a> Policía Nacional Civil</span>
          <span><a href="tel:125" className="font-bold underline-offset-2 hover:underline">125</a> Cruz Roja</span>
        </p>
      </div>

      <main className="mx-auto grid max-w-6xl gap-8 px-4 py-8 lg:grid-cols-[1fr_300px]">
        {resultado ? (
          <Confirmacion resultado={resultado} onNuevo={nuevoReporte} />
        ) : (
          <form onSubmit={enviar} className="space-y-8" noValidate>
            <div>
              <h1 className="font-display text-4xl font-bold leading-[1.05] sm:text-5xl">Reportar una emergencia</h1>
              <p className="mt-2 max-w-xl text-muted">
                Su reporte llega directo al centro de despacho. El sistema envía la unidad disponible más cercana en segundos.
              </p>
            </div>

            {cargando && <Cargando texto="Conectando con el centro de despacho…" />}
            {errorCat && <Aviso>{errorCat}</Aviso>}

            {cat && (
              <>
                <fieldset>
                  <legend className="mb-3 font-display text-2xl font-semibold"><span className="text-muted">1.</span> ¿Qué está pasando?</legend>
                  <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                    {cat.incident_types.map((t) => {
                      const activo = tipo === t.value
                      return (
                        <button type="button" key={t.value} onClick={() => setTipo(t.value)} aria-pressed={activo}
                          className={`flex min-h-24 flex-col items-start justify-between gap-3 rounded-lg border-2 p-3.5 text-left transition-colors ${
                            activo ? 'border-ink bg-ink text-white' : 'border-line bg-surface hover:border-ink/40'}`}>
                          <IconoIncidente tipo={t.value} className={`size-7 ${activo ? 'text-white' : 'text-critical'}`} />
                          <span>
                            <span className="block font-semibold leading-tight">{TEXTO_INCIDENTE[t.value].titulo}</span>
                            <span className={`block text-xs ${activo ? 'text-white/70' : 'text-muted'}`}>{TEXTO_INCIDENTE[t.value].ejemplo}</span>
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </fieldset>

                <fieldset ref={refUbicacion}>
                  <legend className="mb-3 font-display text-2xl font-semibold"><span className="text-muted">2.</span> ¿Dónde?</legend>
                  <div className="mb-4 flex flex-wrap items-center gap-3">
                    <Boton type="button" variante="ruta" onClick={usarUbicacion} cargando={ubicando}
                      icono={<LocateFixed className="size-4" />} className="py-2.5">
                      Usar mi ubicación
                    </Boton>
                    <span className="text-sm text-muted">o elija el lugar en la lista</span>
                  </div>
                  {detectado && (
                    <div className="mb-4 flex items-start gap-2 rounded-md border border-route/30 bg-route-soft px-3 py-2 text-sm text-route">
                      <MapPin className="mt-0.5 size-4 shrink-0" aria-hidden />
                      <span>Detectamos que está cerca de <strong>{detectado}</strong>. Revise que sea correcto y corríjalo si no lo es.</span>
                    </div>
                  )}
                  <SelectorUbicacion valor={ubicacion} onChange={cambiarUbicacion} cat={cat} errores={erroresUbicacion} idPrefijo="portal" />
                  {ubicacion.municipality_code && Object.keys(validarUbicacion(ubicacion, cat)).length === 0 && (
                    <p className="mt-2 flex items-center gap-1.5 text-sm font-medium text-ok">
                      <CircleCheck className="size-4" aria-hidden /> {textoUbicacion(ubicacion, cat)}
                    </p>
                  )}
                  <div className="mt-3">
                    <Campo etiqueta="Dirección o referencia (opcional)" htmlFor="dir">
                      <input id="dir" className={claseInput} value={direccion} maxLength={200}
                        onChange={(e) => setDireccion(e.target.value)} placeholder="Ej. 6a avenida y 12 calle, frente al parque" />
                    </Campo>
                  </div>
                </fieldset>

                <fieldset>
                  <legend className="mb-3 font-display text-2xl font-semibold"><span className="text-muted">3.</span> ¿Qué tan urgente es?</legend>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {URGENCIAS.map((u) => {
                      const activo = prioridad === u.valor
                      return (
                        <button type="button" key={u.valor} onClick={() => setPrioridad(u.valor)} aria-pressed={activo}
                          className={`rounded-lg border-2 px-4 py-3 text-left transition-colors ${
                            activo ? CLASE_URGENCIA[u.valor] : 'border-line bg-surface hover:border-ink/40'}`}>
                          <span className="block font-semibold">{u.titulo}</span>
                          <span className={`block text-sm ${activo ? 'opacity-85' : 'text-muted'}`}>{u.texto}</span>
                        </button>
                      )
                    })}
                  </div>
                </fieldset>

                <fieldset className="space-y-3">
                  <legend className="mb-3 font-display text-2xl font-semibold"><span className="text-muted">4.</span> Detalles <span className="text-base font-normal text-muted">(opcional)</span></legend>
                  <Campo etiqueta="Describa lo que ve" htmlFor="desc">
                    <textarea id="desc" rows={3} className={claseInput} value={descripcion} maxLength={1000}
                      onChange={(e) => setDescripcion(e.target.value)} placeholder="Cuántas personas, si hay heridos, qué tan grande es…" />
                  </Campo>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Campo etiqueta="Su nombre" htmlFor="nom">
                      <input id="nom" className={claseInput} value={nombre} maxLength={100} onChange={(e) => setNombre(e.target.value)} />
                    </Campo>
                    <Campo etiqueta="Teléfono" htmlFor="tel" ayuda="Para que la unidad pueda llamarle">
                      <input id="tel" type="tel" inputMode="tel" className={claseInput} value={telefono} maxLength={20}
                        onChange={(e) => setTelefono(e.target.value)} placeholder="5555 1234" />
                    </Campo>
                  </div>
                </fieldset>

                {error && <Aviso>{error}</Aviso>}

                <Boton type="submit" variante="peligro" cargando={enviando} icono={<Send className="size-5" />}
                  className="w-full py-4 text-lg sm:w-auto sm:px-10">
                  Enviar reporte
                </Boton>
              </>
            )}
          </form>
        )}

        <aside className="space-y-4 lg:pt-2">
          <form
            onSubmit={(e) => { e.preventDefault(); if (codigo.trim()) navegar(`/seguimiento/${codigo.trim().toUpperCase()}`) }}
            className="rounded-lg border border-line bg-surface p-4"
          >
            <h2 className="font-display text-xl font-semibold">Seguir un reporte</h2>
            <p className="mb-3 mt-1 text-sm text-muted">Escriba el código que recibió al reportar.</p>
            <label htmlFor="codigo" className="sr-only">Código de reporte</label>
            <div className="flex gap-2">
              <input id="codigo" className={`${claseInput} uppercase`} value={codigo}
                onChange={(e) => setCodigo(e.target.value)} placeholder="INC-20261014-0001" />
              <Boton type="submit" variante="secundario" aria-label="Buscar reporte"><Search className="size-4" /></Boton>
            </div>
          </form>
          <div className="rounded-lg border border-line bg-surface p-4 text-sm">
            <h2 className="font-display text-xl font-semibold">Qué pasa después</h2>
            <ol className="mt-2 space-y-2 text-muted">
              <li><strong className="text-ink">Se asignan unidades.</strong> El sistema calcula la ruta más corta y envía las más cercanas.</li>
              <li><strong className="text-ink">Recibe un código.</strong> Con él ve en qué estado está su emergencia.</li>
              <li><strong className="text-ink">Si no hay unidades libres,</strong> su reporte queda en cola según su urgencia.</li>
            </ol>
          </div>
        </aside>
      </main>

      <footer className="border-t border-line py-6 text-center text-xs text-muted">
        DWG EMS-05 REV A · Sistema Inteligente de Gestión de Emergencias
      </footer>
    </div>
  )
}

function Confirmacion({ resultado, onNuevo }: { resultado: IncidentePublico; onNuevo: () => void }) {
  const esperando = Object.entries(resultado.waiting_for)
  return (
    <section className="space-y-6">
      <div className="rounded-lg border-2 border-ok bg-surface p-6">
        <p className="flex items-center gap-2 font-semibold text-ok"><CircleCheck className="size-5" aria-hidden /> Reporte recibido</p>
        <p className="mt-4 text-sm text-muted">Su código de seguimiento</p>
        <p className="num font-display text-4xl font-bold tracking-wide sm:text-5xl">{resultado.id}</p>
        <p className="mt-2 text-sm text-muted">Guárdelo o tome una captura de pantalla.</p>
      </div>

      {resultado.units.length > 0 && (
        <div className="rounded-lg border border-line bg-surface">
          <h2 className="border-b border-line px-5 py-3 font-display text-xl font-semibold">Unidades en camino</h2>
          <ul className="divide-y divide-line">
            {resultado.units.map((u) => (
              <li key={u.code} className="flex items-center justify-between gap-4 px-5 py-3">
                <span><strong>{u.type_label}</strong> <span className="text-muted">{u.code}</span></span>
                <span className="num text-right"><strong className="text-lg">~{Math.round(u.eta_min)} min</strong>
                  <span className="block text-xs text-muted">{u.distance_km} km</span></span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {esperando.length > 0 && (
        <Aviso tipo="info">
          En este momento no hay unidades libres de: {esperando.map(([t, n]) => `${n} ${t}`).join(', ')}.
          Su reporte está en cola y se atenderá según su urgencia.
        </Aviso>
      )}

      <div className="flex flex-wrap gap-3">
        <Boton onClick={() => navegar(`/seguimiento/${resultado.id}`)}>Ver seguimiento</Boton>
        <Boton variante="secundario" onClick={onNuevo}>Hacer otro reporte</Boton>
      </div>
    </section>
  )
}
