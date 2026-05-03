export function StatsBar({ stats }) {
  if (!stats) return null

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <StatCard label="Active Incidents" value={stats.total_active ?? '—'} color="text-white" />
      <StatCard label="P0 Critical" value={stats.p0_count ?? '—'} color="text-red-400" />
      <StatCard label="Avg MTTR" value={stats.avg_mttr ? `${stats.avg_mttr}m` : '—'} color="text-blue-400" />
      <StatCard label="All Time" value={stats.total_all_time ?? '—'} color="text-gray-300" />
    </div>
  )
}

function StatCard({ label, value, color }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
    </div>
  )
}