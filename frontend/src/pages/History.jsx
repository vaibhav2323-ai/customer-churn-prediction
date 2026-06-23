import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { api } from '../utils/api'
import RiskBadge from '../components/RiskBadge'
import LoadingSpinner from '../components/LoadingSpinner'

const RISK_FILTERS = ['All', 'High', 'Medium', 'Low']

export default function History() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [riskFilter, setRiskFilter] = useState('All')
  const PAGE_SIZE = 20

  const fetchHistory = async (p = 1, risk = riskFilter) => {
    setLoading(true)
    try {
      const params = { page: p, page_size: PAGE_SIZE }
      if (risk !== 'All') params.risk_level = risk
      const { data: res } = await api.get('/predictions/history', { params })
      setData(res)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load history')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHistory(1, riskFilter)
    setPage(1)
  }, [riskFilter])

  const handlePage = (newPage) => {
    setPage(newPage)
    fetchHistory(newPage, riskFilter)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Prediction History</h1>
        <p className="text-gray-500 text-sm mt-1">All past churn predictions, newest first.</p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm text-gray-500 font-medium">Filter by risk:</span>
        {RISK_FILTERS.map((r) => (
          <button
            key={r}
            onClick={() => setRiskFilter(r)}
            className={`px-3 py-1 rounded-full text-sm font-medium border transition ${
              riskFilter === r
                ? 'bg-blue-600 border-blue-600 text-white'
                : 'border-gray-300 text-gray-600 hover:border-blue-400'
            }`}
          >
            {r}
          </button>
        ))}
        {data && (
          <span className="ml-auto text-sm text-gray-400">{data.total.toLocaleString()} total</span>
        )}
      </div>

      {loading ? (
        <LoadingSpinner message="Loading predictions…" />
      ) : !data || data.total === 0 ? (
        <div className="card text-center py-16 text-gray-400">
          <div className="text-4xl mb-3">📭</div>
          <p className="font-medium">No predictions found</p>
          <p className="text-sm mt-1">Make some predictions first</p>
        </div>
      ) : (
        <>
          <div className="card overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['ID', 'Customer', 'Risk', 'Probability', 'Churns?', 'Source', 'Date'].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50 transition">
                    <td className="px-4 py-3 text-gray-400 font-mono text-xs">#{p.id}</td>
                    <td className="px-4 py-3 font-medium text-gray-800">{p.customer_id}</td>
                    <td className="px-4 py-3">
                      <RiskBadge level={p.risk_level} />
                    </td>
                    <td className="px-4 py-3 font-semibold text-gray-900">
                      {(p.churn_probability * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3">
                      <span className={p.churn_prediction ? 'text-red-600 font-medium' : 'text-green-600 font-medium'}>
                        {p.churn_prediction ? 'Yes' : 'No'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        p.source === 'batch' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                      }`}>
                        {p.source}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                      {new Date(p.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Page {page} of {data.total_pages}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => handlePage(page - 1)}
                disabled={page === 1}
                className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40"
              >
                ← Previous
              </button>
              {Array.from({ length: Math.min(5, data.total_pages) }, (_, i) => {
                const pg = Math.max(1, Math.min(page - 2 + i, data.total_pages - 4 + i))
                return (
                  <button
                    key={pg}
                    onClick={() => handlePage(pg)}
                    className={`w-8 h-8 rounded-lg text-xs font-medium ${
                      pg === page ? 'bg-blue-600 text-white' : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {pg}
                  </button>
                )
              })}
              <button
                onClick={() => handlePage(page + 1)}
                disabled={page === data.total_pages}
                className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40"
              >
                Next →
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
