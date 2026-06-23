import { useEffect, useState } from 'react'
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, LineChart, Line, ResponsiveContainer,
} from 'recharts'
import { api } from '../utils/api'
import LoadingSpinner from '../components/LoadingSpinner'
import { useAuth } from '../context/AuthContext'

const PIE_COLORS = ['#ef4444', '#f59e0b', '#22c55e']
const RISK_COLORS = { High: '#ef4444', Medium: '#f59e0b', Low: '#22c55e' }

function StatCard({ label, value, sub, color = 'blue' }) {
  const colors = {
    blue: 'from-blue-500 to-blue-600',
    red: 'from-red-500 to-red-600',
    green: 'from-green-500 to-green-600',
    amber: 'from-amber-500 to-amber-600',
  }
  return (
    <div className={`rounded-xl bg-gradient-to-br ${colors[color]} p-6 text-white shadow-md`}>
      <p className="text-sm font-medium opacity-80">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs opacity-70 mt-1">{sub}</p>}
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    api
      .get('/dashboard/stats')
      .then(({ data }) => setStats(data))
      .catch((e) => setError(e.response?.data?.detail || 'Failed to load dashboard'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner message="Loading dashboard…" />
  if (error) return (
    <div className="text-center py-20 text-red-600">
      <p className="text-lg font-medium">{error}</p>
    </div>
  )

  const { model_metrics: mm = {} } = stats

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">Welcome back, {user?.full_name} 👋</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Total Predictions"
          value={stats.total_predictions.toLocaleString()}
          sub="all time"
          color="blue"
        />
        <StatCard
          label="High Risk Customers"
          value={stats.high_risk_count.toLocaleString()}
          sub={`${stats.total_predictions ? Math.round((stats.high_risk_count / stats.total_predictions) * 100) : 0}% of total`}
          color="red"
        />
        <StatCard
          label="Overall Churn Rate"
          value={`${(stats.overall_churn_rate * 100).toFixed(1)}%`}
          sub="predicted to churn"
          color="amber"
        />
        <StatCard
          label="Avg Churn Probability"
          value={`${(stats.avg_churn_probability * 100).toFixed(1)}%`}
          sub="across all customers"
          color="green"
        />
      </div>

      {/* Model metrics row */}
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
          Model Performance — {mm.model_type === 'xgboost' ? 'XGBoost' : 'Logistic Regression'}
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
          {[
            ['ROC-AUC', mm.roc_auc],
            ['Accuracy', mm.accuracy],
            ['Precision', mm.precision],
            ['Recall', mm.recall],
            ['F1 Score', mm.f1],
          ].map(([label, val]) => (
            <div key={label} className="text-center p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-500">{label}</p>
              <p className="text-lg font-bold text-blue-700">
                {val != null ? (val * 100).toFixed(1) + '%' : '—'}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Churn pie chart */}
        <div className="card">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Churn Distribution</h2>
          {stats.total_predictions === 0 ? (
            <p className="text-gray-400 text-sm text-center py-12">No predictions yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={[
                    { name: 'High Risk', value: stats.high_risk_count },
                    { name: 'Medium Risk', value: stats.medium_risk_count },
                    { name: 'Low Risk', value: stats.low_risk_count },
                  ]}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {PIE_COLORS.map((color, i) => (
                    <Cell key={i} fill={color} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => v.toLocaleString()} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Risk distribution bar chart */}
        <div className="card">
          <h2 className="text-base font-semibold text-gray-800 mb-4">Risk Distribution</h2>
          {stats.total_predictions === 0 ? (
            <p className="text-gray-400 text-sm text-center py-12">No predictions yet</p>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={stats.risk_distribution} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="risk" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {stats.risk_distribution.map((entry, i) => (
                    <Cell key={i} fill={RISK_COLORS[entry.risk] || '#6b7280'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Monthly trend line chart */}
      <div className="card">
        <h2 className="text-base font-semibold text-gray-800 mb-4">Monthly Churn Probability Trend</h2>
        {stats.monthly_trend.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-12">No trend data available yet</p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={stats.monthly_trend} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                domain={[0, 1]}
                tick={{ fontSize: 11 }}
              />
              <Tooltip
                formatter={(v) => [`${(v * 100).toFixed(1)}%`, 'Avg Probability']}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="avg_probability"
                name="Avg Churn Probability"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ fill: '#3b82f6', r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
