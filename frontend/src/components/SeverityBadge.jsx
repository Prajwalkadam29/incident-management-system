const SEVERITY_STYLES = {
  P0: 'bg-red-500/20 text-red-400 border border-red-500/30',
  P1: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
  P2: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
  P3: 'bg-blue-500/20 text-blue-400 border border-blue-500/30',
}

const SEVERITY_LABELS = {
  P0: '🔴 P0 Critical',
  P1: '🟠 P1 High',
  P2: '🟡 P2 Medium',
  P3: '🔵 P3 Low',
}

export function SeverityBadge({ severity, short = false }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${SEVERITY_STYLES[severity] || 'bg-gray-700 text-gray-300'}`}>
      {short ? severity : (SEVERITY_LABELS[severity] || severity)}
    </span>
  )
}