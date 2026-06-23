const STYLES = {
  High: 'bg-red-100 text-red-700 border-red-200',
  Medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  Low: 'bg-green-100 text-green-700 border-green-200',
}

const ICONS = { High: '🔴', Medium: '🟡', Low: '🟢' }

export default function RiskBadge({ level, size = 'sm' }) {
  const padding = size === 'lg' ? 'px-4 py-1.5 text-sm' : 'px-2.5 py-0.5 text-xs'
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border font-semibold ${padding} ${
        STYLES[level] || 'bg-gray-100 text-gray-600 border-gray-200'
      }`}
    >
      {ICONS[level]} {level}
    </span>
  )
}
