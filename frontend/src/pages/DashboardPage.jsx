import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSSE } from '@/hooks/useSSE'
import { SeverityBadge } from '@/components/SeverityBadge'
import { StatusBadge } from '@/components/StatusBadge'
import { StatsBar } from '@/components/StatsBar'
import { MTTRChart } from '@/components/MTTRChart'

export default function DashboardPage() {
  const navigate  = useNavigate()
  const { data, connected, error } = useSSE('/api/v1/stream/incidents')
  const [searchQuery, setSearchQuery] = useState('')

  const user = JSON.parse(localStorage.getItem('ims_user') || '{}')

  const handleLogout = () => {
    localStorage.removeItem('ims_token')
    localStorage.removeItem('ims_user')
    navigate('/login')
  }

  const incidents = data?.incidents || []
  const stats     = data?.stats

  // Filter incidents by search query
  const filtered = incidents.filter(inc => {
    const query = searchQuery.toLowerCase().trim()
    if (!query) return true
    return (
      inc.title?.toLowerCase().includes(query) ||
      inc.component_id?.toLowerCase().includes(query) ||
      inc.component_type?.toLowerCase().includes(query) ||
      inc.severity?.toLowerCase().includes(query) ||
      inc.status?.toLowerCase().includes(query)
    )
  })

  // Sort: P0 first, then by created_at desc
  const sorted = [...filtered].sort((a, b) => {
    const sev = { P0: 0, P1: 1, P2: 2, P3: 3 }
    return (sev[a.severity] - sev[b.severity]) || new Date(b.created_at) - new Date(a.created_at)
  })

  return (
    <div className="min-h-screen bg-[#050505] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/20 via-[#050505] to-black text-slate-300 font-sans selection:bg-indigo-500/30">
      {/* Navbar with Glassmorphism */}
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-[#050505]/70 border-b border-white/5 px-8 py-4 flex items-center justify-between shadow-2xl">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <span className="text-xl">⚡</span>
            </div>
            <div>
              <h1 className="font-display font-bold text-white text-lg tracking-wide">MISSION CONTROL</h1>
              <p className="text-xs text-indigo-400 font-medium tracking-widest uppercase">Incident Management</p>
            </div>
          </div>

          {/* Navigation Menu */}
          <div className="hidden md:flex items-center gap-1 bg-white/5 border border-white/10 rounded-xl p-1">
            <button onClick={() => navigate('/')}
              className="px-4 py-1.5 rounded-lg text-xs font-semibold tracking-wider uppercase transition-all duration-200 bg-indigo-500 text-white shadow-lg shadow-indigo-500/20">
              Dashboard
            </button>
            <button onClick={() => navigate('/history')}
              className="px-4 py-1.5 rounded-lg text-xs font-semibold tracking-wider uppercase text-slate-400 hover:text-white hover:bg-white/5 transition-all duration-200">
              Incident History
            </button>
          </div>
        </div>
        <div className="flex items-center gap-6">
          {/* Live indicator */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
            <span className="relative flex h-2.5 w-2.5">
              {connected && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>}
              <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${connected ? 'bg-emerald-400' : 'bg-rose-500'}`}></span>
            </span>
            <span className="text-xs font-medium tracking-wide text-slate-300 uppercase">{connected ? 'Live Feed' : 'Reconnecting'}</span>
          </div>
          <div className="h-6 w-px bg-white/10"></div>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-300 font-bold text-sm">
              {user?.username?.charAt(0)?.toUpperCase() || 'U'}
            </div>
            <button onClick={handleLogout}
              className="text-xs font-medium text-slate-400 hover:text-white transition px-3 py-1.5 rounded-lg border border-transparent hover:bg-white/5 hover:border-white/10">
              Logout
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-8 py-10 space-y-8">
        {/* Stats */}
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-1 shadow-xl">
          <StatsBar stats={stats} />
        </div>

        {/* Error banner */}
        {error && (
          <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 px-6 py-4 rounded-xl flex items-center gap-3 animate-in fade-in slide-in-from-top-2">
            <span className="text-lg">⚠️</span>
            <p className="text-sm font-medium">{error}</p>
          </div>
        )}

        {/* Active Incidents Table */}
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl overflow-hidden shadow-2xl shadow-black/50">
          <div className="px-8 py-6 border-b border-white/5 bg-white/[0.01] flex items-center justify-between flex-wrap gap-4">
            <div>
              <h2 className="font-display text-xl font-semibold text-white">Active Incidents</h2>
              <p className="text-sm text-slate-500 mt-1">Real-time anomaly stream</p>
            </div>
            
            {/* Active Incidents Search Box */}
            <div className="flex-1 max-w-md mx-6 relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">🔍</span>
              <input
                type="text"
                placeholder="Filter incidents by title, component, status..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-black/40 border border-white/10 text-sm rounded-xl pl-9 pr-8 py-2 w-full text-white placeholder-slate-550 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all duration-200"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-white transition-colors"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-semibold tracking-wider">
              {filtered.length} of {incidents.length} OPEN
            </div>
          </div>

          {sorted.length === 0 ? (
            <div className="px-8 py-24 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-emerald-500/10 text-emerald-400 mb-4">
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-white mb-1">System Healthy</h3>
              <p className="text-slate-500">{data ? 'No active incidents requiring attention.' : 'Establishing secure connection...'}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-black/20 text-xs font-medium text-slate-500 uppercase tracking-widest border-b border-white/5">
                    <th className="px-8 py-4 font-medium">Severity</th>
                    <th className="px-8 py-4 font-medium">Component</th>
                    <th className="px-8 py-4 font-medium">Title</th>
                    <th className="px-8 py-4 font-medium">Status</th>
                    <th className="px-8 py-4 font-medium">Signals</th>
                    <th className="px-8 py-4 font-medium">Age</th>
                    <th className="px-8 py-4"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {sorted.map(inc => (
                    <tr key={inc.id}
                      onClick={() => navigate(`/incidents/${inc.id}`)}
                      className="group hover:bg-white/[0.04] cursor-pointer transition-all duration-200">
                      <td className="px-8 py-5"><SeverityBadge severity={inc.severity} short /></td>
                      <td className="px-8 py-5">
                        <div className="font-mono text-sm text-slate-200">{inc.component_id}</div>
                        <div className="text-xs text-slate-500 mt-1 uppercase tracking-wide">{inc.component_type}</div>
                      </td>
                      <td className="px-8 py-5">
                        <div className="text-sm font-medium text-slate-200 max-w-md truncate group-hover:text-white transition-colors">
                          {inc.title}
                        </div>
                      </td>
                      <td className="px-8 py-5"><StatusBadge status={inc.status} /></td>
                      <td className="px-8 py-5">
                        <span className="inline-flex items-center justify-center px-2 py-1 rounded-md bg-white/5 border border-white/10 text-xs font-mono text-slate-300">
                          {inc.signal_count.toLocaleString()}
                        </span>
                      </td>
                      <td className="px-8 py-5 text-sm font-medium text-slate-400">{getAge(inc.created_at)}</td>
                      <td className="px-8 py-5 text-right">
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-400 opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
                          ANALYZE
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
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
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-6 shadow-xl">
          <MTTRChart />
        </div>
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