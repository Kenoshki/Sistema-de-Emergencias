import { FileSpreadsheet, FileText } from 'lucide-react'
import { useState } from 'react'
import { useNotificar } from '../../components/Notificaciones'
import { Boton, Panel } from '../../components/ui'
import { api, mensajeError } from '../../lib/api'

const PERIODOS = [7, 30, 90, 365]

export function Reportes() {
  const notificar = useNotificar()
  const [dias, setDias] = useState(30)
  const [descargando, setDescargando] = useState<'pdf' | 'csv' | null>(null)

  const descargar = async (formato: 'pdf' | 'csv') => {
    setDescargando(formato)
    try {
      await (formato === 'pdf' ? api.descargarPdf(dias) : api.descargarCsv(dias))
    } catch (e) {
      notificar('error', mensajeError(e, 'No se pudo generar el archivo.'))
    } finally {
      setDescargando(null)
    }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <Panel titulo="Periodo">
        <div className="inline-flex flex-wrap rounded-md border border-line bg-surface p-0.5" role="group" aria-label="Periodo">
          {PERIODOS.map((p) => (
            <button key={p} onClick={() => setDias(p)} aria-pressed={dias === p}
              className={`rounded px-3 py-1.5 text-sm font-medium ${dias === p ? 'bg-ink text-white' : 'text-muted hover:text-ink'}`}>
              {p === 365 ? 'Último año' : `Últimos ${p} días`}
            </button>
          ))}
        </div>
      </Panel>

      <div className="grid gap-6 sm:grid-cols-2">
        <Panel titulo="Reporte ejecutivo">
          <FileText className="mb-3 size-8 text-critical" aria-hidden />
          <p className="mb-4 text-sm text-muted">
            PDF con los indicadores clave, comparación con el periodo anterior, incidentes por tipo, tiempos por prioridad,
            zonas de mayor riesgo, estado de la flota e incidentes recientes.
          </p>
          <Boton onClick={() => descargar('pdf')} cargando={descargando === 'pdf'}>Descargar PDF</Boton>
        </Panel>
        <Panel titulo="Datos de incidentes">
          <FileSpreadsheet className="mb-3 size-8 text-ok" aria-hidden />
          <p className="mb-4 text-sm text-muted">
            Archivo CSV con un incidente por fila: tipo, prioridad, zona, estado, horas y minutos de despacho y respuesta.
            Se abre directamente en Excel.
          </p>
          <Boton variante="secundario" onClick={() => descargar('csv')} cargando={descargando === 'csv'}>Descargar CSV</Boton>
        </Panel>
      </div>
    </div>
  )
}
