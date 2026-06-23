import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { api } from '../utils/api'
import RiskBadge from '../components/RiskBadge'
import LoadingSpinner from '../components/LoadingSpinner'

const RISK_FILTERS = ['All', 'High', 'Medium', 'Low']

export default function Customers() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [riskFilter, setRiskFilter] = useState('All')
  const [search, setSearch] = useState('')
  const searchTimer = useRef(null)
  const navigate = useNavigate()
  const PAGE_SIZE = 20

  const fetchCustomers = async (p = 1, risk = riskFilter, q = search) => {
    setLoading(true)
    try {
      const params = { page: p, page_size: PAGE_SIZE }
      if (risk !== 'All') params.risk_level = risk
      if (q.trim()) params.search = q.trim()
      const { data: res } = await api.get('/customers', { params })
      setData(res)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load customers')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCustomers(1, riskFilter, search)
    setPage(1)
  }, [riskFilter])

  const handleSearch = (val) => {
    setSearch(val)
    clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => {
      setPage(1)
      fetchCustomers(1, riskFilter, val)
    }, 400)
  }

  const handlePage = (newPage) => {
    setPage(newPage)
    fetchCustomers(newPage, riskFilter, search)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Customers</h1>
        <p className="text-gray-500 text-sm mt-1">Latest churn prediction per customer.</p>
      </div>

      {/* Filters + search */}
      <div className="flex items-center gap-3 flex-wrap">
        <input
          type="text"
          placeholder="Search by customer ID…"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          className="input w-56"
        />
        <div className="flex items-center gap-2">
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
        </div>
        {data && (
          <span className="ml-auto text-sm text-gray-400">{data.total.toLocaleString()} customers</span>
        )}
      </div>

      {loading ? (
        <LoadingSpinner message="Loading customers…" />
      ) : !data || data.total === 0 ? (
        <div className="card text-center py-16 text-gray-400">
          <div className="text-4xl mb-3">👥</div>
          <p className="font-medium">No customers found</p>
          <p className="text-sm mt-1">
            <button onClick={() => navigate('/predict')} className="text-blue-600 hover:underline">
              Make a prediction
            </button>{' '}
            to see customers here.
          </p>
        </div>
      ) : (
        <>
          <div className="card overflow-x-auto p-0">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Customer ID', 'Risk', 'Churn Prob.', 'Contract', 'Tenure', 'Monthly $', 'Internet', 'Last Predicted'].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.customers.map((c) => (
                  <tr key={c.customer_id} className="hover:bg-gray-50 transition cursor-pointer"
                    onClick={() => navigate(`/predict`)}
                  >
                    <td className="px-4 py-3 font-mono text-xs font-medium text-blue-700">{c.customer_id}</td>
                    <td className="px-4 py-3">
                      <RiskBadge level={c.risk_level} />
                    </td>
                    <td className="px-4 py-3 font-semibold">
                      <span className={
                        c.risk_level === 'High' ? 'text-red-700' :
                        c.risk_level === 'Medium' ? 'text-yellow-700' : 'text-green-700'
                      }>
                        {(c.churn_probability * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{c.contract}</td>
                    <td className="px-4 py-3 text-gray-600">
                      {c.tenure !== '—' ? `${c.tenure} mo` : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {c.monthly_charges !== '—' ? `$${Number(c.monthly_charges).toFixed(2)}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{c.internet_service}</td>
                    <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                      {new Date(c.last_predicted).toLocaleDateString()}
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
