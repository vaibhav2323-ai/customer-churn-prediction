import { useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { api } from '../utils/api'
import RiskBadge from '../components/RiskBadge'

const CSV_TEMPLATE = `gender,senior_citizen,partner,dependents,tenure,phone_service,multiple_lines,internet_service,online_security,online_backup,device_protection,tech_support,streaming_tv,streaming_movies,contract,paperless_billing,payment_method,monthly_charges,total_charges
Male,0,Yes,No,24,Yes,No,DSL,Yes,No,No,No,No,No,One year,Yes,Bank transfer (automatic),59.9,1437.6
Female,1,No,No,2,Yes,No,Fiber optic,No,No,No,No,No,No,Month-to-month,Yes,Electronic check,70.7,141.4
Male,0,Yes,Yes,60,Yes,Yes,DSL,Yes,Yes,Yes,Yes,Yes,Yes,Two year,No,Credit card (automatic),110.0,6600.0`

export default function BatchUpload() {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()

  const handleFile = (f) => {
    if (!f) return
    if (!f.name.endsWith('.csv')) {
      toast.error('Only CSV files are accepted')
      return
    }
    setFile(f)
    setResult(null)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  const handleSubmit = async () => {
    if (!file) return
    setUploading(true)
    const form = new FormData()
    form.append('file', file)
    try {
      const { data } = await api.post('/predictions/batch-predict', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult(data)
      toast.success(`Processed ${data.successful} customers`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Batch prediction failed')
    } finally {
      setUploading(false)
    }
  }

  const downloadCSV = () => {
    if (!result) return
    const headers = ['#', 'Risk Level', 'Churn Probability', 'Churn Prediction', 'Status']
    const rows = result.results.map((r, i) => [
      i + 1,
      r.risk_level || '',
      r.churn_probability != null ? (r.churn_probability * 100).toFixed(2) + '%' : '',
      r.churn_prediction != null ? (r.churn_prediction ? 'Yes' : 'No') : '',
      r.status,
    ])
    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'churn_predictions.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const downloadTemplate = () => {
    const blob = new Blob([CSV_TEMPLATE], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'churn_template.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const riskCounts = result
    ? result.results.reduce(
        (acc, r) => {
          if (r.risk_level) acc[r.risk_level] = (acc[r.risk_level] || 0) + 1
          return acc
        },
        {}
      )
    : {}

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Batch Prediction</h1>
          <p className="text-gray-500 text-sm mt-1">Upload a CSV to predict churn for up to 1,000 customers at once.</p>
        </div>
        <button onClick={downloadTemplate} className="btn-secondary">
          ⬇ Download CSV Template
        </button>
      </div>

      {/* Upload zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`card cursor-pointer border-2 border-dashed transition text-center py-16 ${
          dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-blue-300 hover:bg-gray-50'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => handleFile(e.target.files[0])}
        />
        <div className="text-4xl mb-3">{file ? '📄' : '📁'}</div>
        {file ? (
          <>
            <p className="font-semibold text-gray-800">{file.name}</p>
            <p className="text-sm text-gray-500 mt-1">{(file.size / 1024).toFixed(1)} KB — click to change</p>
          </>
        ) : (
          <>
            <p className="font-semibold text-gray-700">Drop your CSV here or click to browse</p>
            <p className="text-sm text-gray-400 mt-1">Max 1,000 rows · CSV format only</p>
          </>
        )}
      </div>

      {file && (
        <button
          onClick={handleSubmit}
          disabled={uploading}
          className="btn-primary px-8 py-3 text-base"
        >
          {uploading ? (
            <span className="flex items-center gap-2">
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Processing…
            </span>
          ) : (
            '🚀 Run Batch Prediction'
          )}
        </button>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="card text-center">
              <p className="text-xs text-gray-500">Total</p>
              <p className="text-2xl font-bold text-gray-900">{result.total}</p>
            </div>
            <div className="card text-center border-green-200 bg-green-50">
              <p className="text-xs text-gray-500">Successful</p>
              <p className="text-2xl font-bold text-green-700">{result.successful}</p>
            </div>
            {Object.entries(riskCounts).map(([risk, count]) => (
              <div key={risk} className="card text-center">
                <p className="text-xs text-gray-500">{risk} Risk</p>
                <p className="text-2xl font-bold text-gray-900">{count}</p>
              </div>
            ))}
          </div>

          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-gray-800">Results Preview</h2>
            <button onClick={downloadCSV} className="btn-primary">
              ⬇ Download Results
            </button>
          </div>

          <div className="card overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['#', 'Risk', 'Churn Probability', 'Predicted Churn', 'Top Factor'].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {result.results.slice(0, 50).map((r, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition">
                    <td className="px-4 py-3 text-gray-500 font-mono">{i + 1}</td>
                    <td className="px-4 py-3">
                      {r.risk_level ? <RiskBadge level={r.risk_level} /> : <span className="text-red-500 text-xs">Error</span>}
                    </td>
                    <td className="px-4 py-3 font-semibold">
                      {r.churn_probability != null ? `${(r.churn_probability * 100).toFixed(1)}%` : '—'}
                    </td>
                    <td className="px-4 py-3">
                      {r.churn_prediction != null ? (
                        <span className={r.churn_prediction ? 'text-red-600 font-medium' : 'text-green-600 font-medium'}>
                          {r.churn_prediction ? 'Yes' : 'No'}
                        </span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {r.top_reasons?.[0]?.feature || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {result.results.length > 50 && (
              <p className="text-center text-sm text-gray-400 py-4">
                Showing 50 of {result.results.length} rows. Download CSV for full results.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
