import { useState, type FormEvent } from 'react'
import { SelectorUbicacion, UBICACION_VACIA, validarUbicacion } from '../../components/SelectorUbicacion'
import { Aviso, Boton, Campo, Cargando, Modal, claseInput } from '../../components/ui'
import { useNotificar } from '../../components/Notificaciones'
import { api, mensajeError } from '../../lib/api'
import { describirFaltantes } from '../../lib/format'
import { useDatos } from '../../lib/hooks'
import type { Incidente, UbicacionForm } from '../../lib/types'

/** Registro de un incidente por un operador (p. ej. al recibir una llamada). */
export function FormIncidente({ abierto, onCerrar, onCreado }: {
  abierto: boolean; onCerrar: () => void; onCreado: (inc: Incidente) => void
}) {
  const { datos: cat } = useDatos(api.catalogos)
  const notificar = useNotificar()
  const [tipo, setTipo] = useState('accident')
  const [prioridad, setPrioridad] = useState(3)
  const [ubicacion, setUbicacion] = useState<UbicacionForm>(UBICACION_VACIA)
  const [intento, setIntento] = useState(false)
  const [direccion, setDireccion] = useState('')
  const [descripcion, setDescripcion] = useState('')
  const [nombre, setNombre] = useState('')
  const [telefono, setTelefono] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setIntento(true)
    if (Object.keys(validarUbicacion(ubicacion, cat)).length) {
      setError('Complete la ubicación: departamento, municipio y zona si aplica.')
      return
    }
    setEnviando(true)
    setError(null)
    try {
      const inc = await api.crearIncidente({
        type: tipo, priority: prioridad,
        department_code: ubicacion.department_code, municipality_code: ubicacion.municipality_code,
        zone: ubicacion.zone, place_id: ubicacion.place_id, place_name: ubicacion.place_name || undefined,
        address: direccion || undefined, description: descripcion || undefined,
        reporter_name: nombre || undefined, reporter_phone: telefono || undefined,
      })
      const faltan = describirFaltantes(inc.pending_requirements)
      notificar(faltan ? 'alert' : 'success',
        `${inc.id} registrado. ${inc.active_units.length ? `Unidades: ${inc.active_units.join(', ')}.` : ''}${faltan ? ` Sin unidades libres: ${faltan}.` : ''}`)
      setDireccion(''); setDescripcion(''); setNombre(''); setTelefono('')
      setUbicacion(UBICACION_VACIA); setIntento(false)
      onCreado(inc)
    } catch (err) {
      setError(mensajeError(err))
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal abierto={abierto} titulo="Registrar incidente" onCerrar={onCerrar}>
      <form onSubmit={enviar} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Tipo" htmlFor="f-tipo">
            <select id="f-tipo" className={claseInput} value={tipo} onChange={(e) => setTipo(e.target.value)}>
              {cat?.incident_types.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Prioridad" htmlFor="f-pri">
            <select id="f-pri" className={claseInput} value={prioridad} onChange={(e) => setPrioridad(Number(e.target.value))}>
              {cat?.priorities.map((p) => <option key={p.value} value={p.value}>{p.value} – {p.label}</option>)}
            </select>
          </Campo>
        </div>
        {cat ? (
          <SelectorUbicacion valor={ubicacion} onChange={setUbicacion} cat={cat} idPrefijo="op"
            errores={intento ? validarUbicacion(ubicacion, cat) : {}} />
        ) : <Cargando />}
        <Campo etiqueta="Dirección o referencia" htmlFor="f-dir">
          <input id="f-dir" className={claseInput} value={direccion} maxLength={200} onChange={(e) => setDireccion(e.target.value)} />
        </Campo>
        <Campo etiqueta="Descripción" htmlFor="f-desc">
          <textarea id="f-desc" rows={3} className={claseInput} value={descripcion} maxLength={1000} onChange={(e) => setDescripcion(e.target.value)} />
        </Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo etiqueta="Quien reporta" htmlFor="f-nom">
            <input id="f-nom" className={claseInput} value={nombre} maxLength={100} onChange={(e) => setNombre(e.target.value)} />
          </Campo>
          <Campo etiqueta="Teléfono" htmlFor="f-tel">
            <input id="f-tel" className={claseInput} value={telefono} maxLength={20} onChange={(e) => setTelefono(e.target.value)} />
          </Campo>
        </div>
        {error && <Aviso>{error}</Aviso>}
        <div className="flex justify-end gap-2">
          <Boton type="button" variante="secundario" onClick={onCerrar}>Cancelar</Boton>
          <Boton type="submit" variante="peligro" cargando={enviando}>Registrar y despachar</Boton>
        </div>
      </form>
    </Modal>
  )
}
