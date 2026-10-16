import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import type { Catalogos, Lugar, MunicipioOpcion, UbicacionForm } from '../lib/types'
import { Campo, claseInput } from './ui'

export const UBICACION_VACIA: UbicacionForm = {
  department_code: '', municipality_code: '', zone: null, place_id: null, place_name: '',
}

export type ErroresUbicacion = Partial<Record<'department_code' | 'municipality_code' | 'zone', string>>

/**
 * Reglas obligatorias (las mismas que valida el backend):
 * departamento + municipio, y la zona cuando el municipio se divide en zonas.
 */
export function validarUbicacion(u: UbicacionForm, cat: Catalogos | null): ErroresUbicacion {
  const errores: ErroresUbicacion = {}
  if (!u.department_code) errores.department_code = 'Seleccione el departamento.'
  if (!u.municipality_code) {
    errores.municipality_code = 'Seleccione el municipio.'
    return errores
  }
  const muni = cat?.municipalities.find((m) => m.value === u.municipality_code)
  if (muni?.zones?.length) {
    if (u.zone === null) errores.zone = `${muni.label} se divide en zonas: seleccione la zona.`
    else if (!muni.zones.some((z) => z.value === u.zone)) errores.zone = `Esa zona no existe en ${muni.label}.`
  }
  return errores
}

export function textoUbicacion(u: UbicacionForm, cat: Catalogos | null): string {
  const depto = cat?.departments.find((d) => d.value === u.department_code)?.label
  const muni = cat?.municipalities.find((m) => m.value === u.municipality_code)?.label
  return [u.place_name || null, u.zone !== null ? `Zona ${u.zone}` : null, muni, depto !== muni ? depto : null]
    .filter(Boolean).join(', ')
}

const conError = (e?: string) => (e ? 'border-critical! ring-2 ring-critical/20' : '')

/** Departamento → Municipio → Zona (si aplica) → Aldea, caserío o colonia. */
export function SelectorUbicacion({ valor, onChange, cat, errores = {}, conLugar = true, idPrefijo = 'u' }: {
  valor: UbicacionForm
  onChange: (u: UbicacionForm) => void
  cat: Catalogos
  errores?: ErroresUbicacion
  conLugar?: boolean
  idPrefijo?: string
}) {
  const municipios = useMemo(
    () => cat.municipalities.filter((m) => m.department === valor.department_code),
    [cat, valor.department_code],
  )
  const muni: MunicipioOpcion | undefined = cat.municipalities.find((m) => m.value === valor.municipality_code)

  const cambiarDepto = (d: string) => {
    const delDepto = cat.municipalities.filter((m) => m.department === d)
    onChange({ ...UBICACION_VACIA, department_code: d, municipality_code: delDepto.length === 1 ? delDepto[0].value : '' })
  }
  const cambiarMuni = (m: string) => onChange({ ...valor, municipality_code: m, zone: null, place_id: null, place_name: '' })

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <Campo etiqueta="Departamento *" htmlFor={`${idPrefijo}-depto`} error={errores.department_code}>
          <select id={`${idPrefijo}-depto`} className={`${claseInput} ${conError(errores.department_code)}`}
            value={valor.department_code} onChange={(e) => cambiarDepto(e.target.value)}
            aria-invalid={Boolean(errores.department_code)}>
            <option value="">Seleccione…</option>
            {cat.departments.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
          </select>
        </Campo>
        <Campo etiqueta="Municipio *" htmlFor={`${idPrefijo}-muni`} error={errores.municipality_code}
          ayuda={!valor.department_code ? 'Primero elija el departamento' : undefined}>
          <select id={`${idPrefijo}-muni`} className={`${claseInput} ${conError(errores.municipality_code)}`}
            value={valor.municipality_code} disabled={!valor.department_code}
            onChange={(e) => cambiarMuni(e.target.value)} aria-invalid={Boolean(errores.municipality_code)}>
            <option value="">Seleccione…</option>
            {municipios.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </Campo>
      </div>

      {muni?.zones?.length ? (
        <Campo etiqueta="Zona *" htmlFor={`${idPrefijo}-zona`} error={errores.zone}
          ayuda={`${muni.label} se divide en zonas. Elija la zona donde ocurre la emergencia.`}>
          <select id={`${idPrefijo}-zona`} className={`${claseInput} ${conError(errores.zone)}`}
            value={valor.zone ?? ''} aria-invalid={Boolean(errores.zone)}
            onChange={(e) => onChange({ ...valor, zone: e.target.value ? Number(e.target.value) : null })}>
            <option value="">Seleccione la zona…</option>
            {muni.zones.map((z) => <option key={z.value} value={z.value}>{z.label}</option>)}
          </select>
        </Campo>
      ) : null}

      {conLugar && muni && (
        <SelectorLugar idPrefijo={idPrefijo} municipio={muni} valor={valor} onChange={onChange} />
      )}
    </div>
  )
}

/** Aldea / caserío / colonia: busca en el catálogo importado y permite escribir libremente. */
function SelectorLugar({ municipio, valor, onChange, idPrefijo }: {
  municipio: MunicipioOpcion; valor: UbicacionForm; onChange: (u: UbicacionForm) => void; idPrefijo: string
}) {
  const [sugerencias, setSugerencias] = useState<Lugar[]>([])
  const [abierto, setAbierto] = useState(false)

  useEffect(() => {
    if (!municipio.has_places || !abierto) return
    const t = window.setTimeout(() => {
      api.lugares(municipio.value, valor.place_name).then(setSugerencias).catch(() => setSugerencias([]))
    }, 250)
    return () => window.clearTimeout(t)
  }, [municipio, valor.place_name, abierto])

  const id = `${idPrefijo}-lugar`
  return (
    <Campo etiqueta="Aldea, caserío, colonia o barrio" htmlFor={id}
      ayuda={municipio.has_places ? 'Escriba para buscar en el catálogo o escriba el nombre si no aparece.' : 'Opcional. Escriba el nombre si lo conoce.'}>
      <div className="relative">
        <input id={id} className={claseInput} value={valor.place_name} maxLength={150} autoComplete="off"
          role="combobox" aria-expanded={abierto && sugerencias.length > 0} aria-controls={`${id}-lista`}
          placeholder={municipio.has_places ? `Buscar en ${municipio.label}…` : 'Ej. Aldea San José, Colonia El Mezquital'}
          onFocus={() => setAbierto(true)}
          onBlur={() => window.setTimeout(() => setAbierto(false), 150)}
          onChange={(e) => onChange({ ...valor, place_name: e.target.value, place_id: null })} />
        {valor.place_id !== null && (
          <span className="absolute right-2 top-1/2 -translate-y-1/2 rounded bg-ok-soft px-1.5 py-0.5 text-[11px] font-semibold text-ok">catálogo</span>
        )}
        {abierto && sugerencias.length > 0 && (
          <ul id={`${id}-lista`} role="listbox"
            className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-md border border-line bg-surface shadow-lg">
            {sugerencias.map((l) => (
              <li key={l.id} role="option" aria-selected={valor.place_id === l.id}>
                <button type="button" className="flex w-full items-baseline justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-paper"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => { onChange({ ...valor, place_id: l.id, place_name: l.name }); setAbierto(false) }}>
                  <span>{l.name}</span>
                  {l.category && <span className="text-xs capitalize text-muted">{l.category}</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Campo>
  )
}
