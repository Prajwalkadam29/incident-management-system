import { useNavigate } from 'react-router-dom'
import { useSSE } from '@/hooks/useSSE'
import { SeverityBadge } from '@/components/SeverityBadge'
import { StatusBadge } from '@/components/StatusBadge'
import { StatsBar } from '@/components/StatsBar'
import { MTTRChart } from '@/components/MTTRChart'

export default function DashboardPage() {
  const navigate  = useNavigate()
  const { data, connected, error } = useSSE('/api/v1/stream/incidents')

  const user = JSON.parse(localStorage.getItem('ims_user') || '{}')

  const handleLogout = () => {
    localStorage.removeItem('ims_token')
    localStorage.removeItem('ims_user')
    navigate('/login')
  }

  const incidents = data?.incidents || []
  const stats     = data?.stats

  // Sort: P0 first, then by created_at desc
  const sorted = [...incidents].sort((a, b) => {
    const sev = { P0: 0, P1: 1, P2: 2, P3: 3 }
    return (sev[a.severity] - sev[b.severity]) || new Date(b.created_at) - new Date(a.created_at)
  })

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Navbar */}
      <nav className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl">🚨</span>
          <span className="font-bold text-white">IMS</span>
          <span className="text-gray-600">|</span>
          <span className="text-gray-400 text-sm">Operations Dashboard</span>
        </div>
        <div className="flex items-center gap-4">
          {/* Live indicator */}
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
            <span className="text-xs text-gray-500">{connected ? 'Live' : 'Reconnecting'}</span>
          </div>
          <span className="text-sm text-gray-400">{user.username}</span>
          <button onClick={handleLogout}
            className="text-xs text-gray-500 hover:text-white transition px-2 py-1 rounded border border-gray-700 hover:border-gray-500">
            Logout
          </button>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Stats */}
        <StatsBar stats={stats} />

        {/* Error banner */}
        {error && (
          <div className="mb-4 bg-yellow-900/20 border border-yellow-700/50 text-yellow-400 text-sm px-4 py-2 rounded-lg">
            ⚠️ {error}
          </div>
        )}

        {/* Active Incidents Table */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl mb-6">
          <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
            <h2 className="font-semibold text-white">Active Incidents</h2>
            <span className="text-xs text-gray-500">
              {incidents.length} active · updates every 3s
            </span>
          </div>

          {sorted.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-600">
              {data ? '✅ No active incidents' : 'Connecting to live feed...'}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-xs text-gray-500 uppercase tracking-wider">
                    <th className="px-6 py-3 text-left">Severity</th>
                    <th className="px-6 py-3 text-left">Component</th>
                    <th className="px-6 py-3 text-left">Title</th>
                    <th className="px-6 py-3 text-left">Status</th>
                    <th className="px-6 py-3 text-left">Signals</th>
                    <th className="px-6 py-3 text-left">Age</th>
                    <th className="px-6 py-3 text-left"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {sorted.map(inc => (
                    <tr key={inc.id}
                      onClick={() => navigate(`/incidents/${inc.id}`)}
                      className="hover:bg-gray-800/50 cursor-pointer transition group">
                      <td className="px-6 py-4"><SeverityBadge severity={inc.severity} short /></td>
                      <td className="px-6 py-4">
                        <span className="font-mono text-sm text-gray-300">{inc.component_id}</span>
                        <span className="ml-2 text-xs text-gray-600">{inc.component_type}</span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-300 max-w-xs truncate">{inc.title}</td>
                      <td className="px-6 py-4"><StatusBadge status={inc.status} /></td>
                      <td className="px-6 py-4 text-sm text-gray-400">{inc.signal_count}</td>
                      <td className="px-6 py-4 text-sm text-gray-500">{getAge(inc.created_at)}</td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-xs text-blue-500 opacity-0 group-hover:opacity-100 transition">
                          View →
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* MTTR Chart */}
        <MTTRChart />
      </main>
    </div>
  )
}

function getAge(isoString) {
  const diff = Date.now() - new Date(isoString)
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h`
  return `${Math.floor(hrs / 24)}d`
}