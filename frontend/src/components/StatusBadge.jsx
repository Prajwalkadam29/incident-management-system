const STATUS_STYLES = {
  OPEN:          'bg-red-900/40 text-red-300 border border-red-700/50',
  INVESTIGATING: 'bg-yellow-900/40 text-yellow-300 border border-yellow-700/50',
  RESOLVED:      'bg-blue-900/40 text-blue-300 border border-blue-700/50',
  CLOSED:        'bg-green-900/40 text-green-300 border border-green-700/50',
}

const STATUS_ICONS = {
  OPEN: '🔥',
  INVESTIGATING: '🔍',
  RESOLVED: '✅',
  CLOSED: '🔒',
}

export function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${STATUS_STYLES[status] || 'bg-gray-700 text-gray-300'}`}>
      {STATUS_ICONS[status]} {status}
    </span>
  )
}