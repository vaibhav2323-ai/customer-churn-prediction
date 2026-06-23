import { useState } from 'react'
import { useForm } from 'react-hook-form'
import toast from 'react-hot-toast'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer,
} from 'recharts'
import { api } from '../utils/api'
import RiskBadge from '../components/RiskBadge'

const DIRECTION_COLOR = { increases: '#ef4444', decreases: '#22c55e' }

function Field({ label, name, register, type = 'text', options, errors, rules = {} }) {
  const err = errors[name]
  return (
    <div>
      <label className="label">{label}</label>
      {options ? (
        <select className="select" {...register(name, rules)}>
          {options.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      ) : (
        <input type={type} className="input" {...register(name, rules)} />
      )}
      {err && <p className="text-red-500 text-xs mt-1">{err.message}</p>}
    </div>
  )
}

const defaultValues = {
  gender: 'Male',
  senior_citizen: '0',
  partner: 'No',
  dependents: 'No',
  tenure: '12',
  phone_service: 'Yes',
  multiple_lines: 'No',
  internet_service: 'DSL',
  online_security: 'No',
  online_backup: 'No',
  device_protection: 'No',
  tech_support: 'No',
  streaming_tv: 'No',
  streaming_movies: 'No',
  contract: 'Month-to-month',
  paperless_billing: 'Yes',
  payment_method: 'Electronic check',
  monthly_charges: '65.00',
  total_charges: '780.00',
}

export default function Predict() {
  const [result, setResult] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ defaultValues })

  const onSubmit = async (values) => {
    setSubmitting(true)
    setResult(null)
    try {
      const payload = {
        ...values,
        senior_citizen: parseInt(values.senior_citizen),
        tenure: parseInt(values.tenure),
        monthly_charges: parseFloat(values.monthly_charges),
        total_charges: parseFloat(values.total_charges),
      }
      const { data } = await api.post('/predictions/predict', payload)
      setResult(data)
      toast.success('Prediction complete!')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Prediction failed')
    } finally {
      setSubmitting(false)
    }
  }

  const riskBg = result
    ? result.risk_level === 'High'
      ? 'border-red-200 bg-red-50'
      : result.risk_level === 'Medium'
      ? 'border-yellow-200 bg-yellow-50'
      : 'border-green-200 bg-green-50'
    : ''

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Single Customer Prediction</h1>
        <p className="text-gray-500 text-sm mt-1">Fill in customer details to get an instant churn prediction with AI explanation.</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} className="card space-y-6">
          <h2 className="text-base font-semibold text-gray-700 border-b pb-3">Customer Information</h2>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Gender" name="gender" register={register} options={['Male', 'Female']} errors={errors} />
            <Field label="Senior Citizen" name="senior_citizen" register={register} options={['0', '1']} errors={errors} />
            <Field label="Partner" name="partner" register={register} options={['Yes', 'No']} errors={errors} />
            <Field label="Dependents" name="dependents" register={register} options={['Yes', 'No']} errors={errors} />
          </div>

          <h2 className="text-base font-semibold text-gray-700 border-b pb-3">Service Details</h2>

          <div className="grid grid-cols-2 gap-4">
            <Field
              label="Tenure (months)"
              name="tenure"
              type="number"
              register={register}
              errors={errors}
              rules={{ required: 'Required', min: { value: 0, message: 'Min 0' }, max: { value: 72, message: 'Max 72' } }}
            />
            <Field label="Phone Service" name="phone_service" register={register} options={['Yes', 'No']} errors={errors} />
            <Field label="Multiple Lines" name="multiple_lines" register={register} options={['Yes', 'No', 'No phone service']} errors={errors} />
            <Field label="Internet Service" name="internet_service" register={register} options={['DSL', 'Fiber optic', 'No']} errors={errors} />
            <Field label="Online Security" name="online_security" register={register} options={['Yes', 'No', 'No internet service']} errors={errors} />
            <Field label="Online Backup" name="online_backup" register={register} options={['Yes', 'No', 'No internet service']} errors={errors} />
            <Field label="Device Protection" name="device_protection" register={register} options={['Yes', 'No', 'No internet service']} errors={errors} />
            <Field label="Tech Support" name="tech_support" register={register} options={['Yes', 'No', 'No internet service']} errors={errors} />
            <Field label="Streaming TV" name="streaming_tv" register={register} options={['Yes', 'No', 'No internet service']} errors={errors} />
            <Field label="Streaming Movies" name="streaming_movies" register={register} options={['Yes', 'No', 'No internet service']} errors={errors} />
          </div>

          <h2 className="text-base font-semibold text-gray-700 border-b pb-3">Billing</h2>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Contract" name="contract" register={register} options={['Month-to-month', 'One year', 'Two year']} errors={errors} />
            <Field label="Paperless Billing" name="paperless_billing" register={register} options={['Yes', 'No']} errors={errors} />
            <div className="col-span-2">
              <Field
                label="Payment Method"
                name="payment_method"
                register={register}
                options={['Electronic check', 'Mailed check', 'Bank transfer (automatic)', 'Credit card (automatic)']}
                errors={errors}
              />
            </div>
            <Field
              label="Monthly Charges ($)"
              name="monthly_charges"
              type="number"
              register={register}
              errors={errors}
              rules={{ required: 'Required', min: { value: 0, message: 'Min 0' } }}
            />
            <Field
              label="Total Charges ($)"
              name="total_charges"
              type="number"
              register={register}
              errors={errors}
              rules={{ required: 'Required', min: { value: 0, message: 'Min 0' } }}
            />
          </div>

          <button type="submit" disabled={submitting} className="btn-primary w-full py-3 text-base">
            {submitting ? (
              <span className="flex items-center gap-2 justify-center">
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Analyzing…
              </span>
            ) : (
              '🔍 Predict Churn'
            )}
          </button>
        </form>

        {/* Results panel */}
        <div className="space-y-6">
          {!result && (
            <div className="card flex flex-col items-center justify-center py-24 text-center text-gray-400">
              <div className="text-5xl mb-4">📊</div>
              <p className="font-medium">Results will appear here</p>
              <p className="text-sm mt-1">Fill in customer details and click Predict</p>
            </div>
          )}

          {result && (
            <>
              {/* Main result card */}
              <div className={`card border-2 ${riskBg}`}>
                <div className="flex items-start justify-between mb-4">
                  <h2 className="text-lg font-semibold text-gray-800">Prediction Result</h2>
                  <RiskBadge level={result.risk_level} size="lg" />
                </div>

                <div className="flex items-center gap-6 mb-4">
                  <div>
                    <p className="text-xs text-gray-500">Churn Probability</p>
                    <p className="text-4xl font-bold text-gray-900">
                      {(result.churn_probability * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500">Likely to Churn?</p>
                    <p className={`text-xl font-bold ${result.churn_prediction ? 'text-red-600' : 'text-green-600'}`}>
                      {result.churn_prediction ? '⚠️ Yes' : '✅ No'}
                    </p>
                  </div>
                </div>

                {/* Probability bar */}
                <div>
                  <div className="flex justify-between text-xs text-gray-500 mb-1">
                    <span>0%</span>
                    <span>50%</span>
                    <span>100%</span>
                  </div>
                  <div className="relative h-3 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-700 ${
                        result.risk_level === 'High'
                          ? 'bg-red-500'
                          : result.risk_level === 'Medium'
                          ? 'bg-yellow-500'
                          : 'bg-green-500'
                      }`}
                      style={{ width: `${result.churn_probability * 100}%` }}
                    />
                    <div className="absolute top-0 left-1/2 w-px h-full bg-gray-400" />
                  </div>
                </div>
              </div>

              {/* SHAP explanation */}
              <div className="card">
                <h3 className="text-base font-semibold text-gray-800 mb-1">Why this prediction?</h3>
                <p className="text-xs text-gray-500 mb-4">SHAP values showing which features push toward or away from churn</p>

                <div className="space-y-2 mb-5">
                  {result.top_reasons.map((r, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <span
                        className={`font-semibold text-xs px-2 py-0.5 rounded ${
                          r.direction === 'increases'
                            ? 'bg-red-100 text-red-700'
                            : 'bg-green-100 text-green-700'
                        }`}
                      >
                        {r.direction === 'increases' ? '▲' : '▼'} {Math.abs(r.impact).toFixed(3)}
                      </span>
                      <span className="text-gray-700 font-medium">{r.feature}</span>
                      <span className="text-gray-400 text-xs">
                        {r.direction} churn risk
                      </span>
                    </div>
                  ))}
                </div>

                <ResponsiveContainer width="100%" height={200}>
                  <BarChart
                    data={result.feature_impacts.map((f) => ({
                      name: f.feature.split(' ').slice(0, 2).join(' '),
                      impact: Math.abs(f.shap_value),
                      direction: f.shap_value > 0 ? 'increases' : 'decreases',
                    }))}
                    layout="vertical"
                    margin={{ left: 10, right: 20, top: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={90} />
                    <Tooltip formatter={(v, n, p) => [`${v.toFixed(4)} (${p.payload.direction} risk)`, 'SHAP Impact']} />
                    <Bar dataKey="impact" radius={[0, 3, 3, 0]}>
                      {result.feature_impacts.map((f, i) => (
                        <Cell key={i} fill={f.shap_value > 0 ? '#ef4444' : '#22c55e'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
