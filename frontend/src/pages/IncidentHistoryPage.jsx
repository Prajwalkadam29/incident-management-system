import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api/client'
import { SeverityBadge } from '@/components/SeverityBadge'
import { StatusBadge } from '@/components/StatusBadge'

export default function IncidentHistoryPage() {
  const navigate = useNavigate()
  
  // State for List Data
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(10)
  const [loading, setLoading] = useState(true)
  
  // State for Stats
  const [stats, setStats] = useState(null)
  const [loadingStats, setLoadingStats] = useState(true)

  // State for Filters
  const [severity, setSeverity] = useState('')
  const [componentId, setComponentId] = useState('')
  const [queryStr, setQueryStr] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  const user = JSON.parse(localStorage.getItem('ims_user') || '{}')

  const handleLogout = () => {
    localStorage.removeItem('ims_token')
    localStorage.removeItem('ims_user')
    navigate('/login')
  }

  // Fetch Stats
  const fetchStats = async () => {
    setLoadingStats(true)
    try {
      const res = await api.get('/workitems/history/stats')
      setStats(res.data)
    } catch (err) {
      console.error('Failed to load stats', err)
    } finally {
      setLoadingStats(false)
    }
  }

  // Fetch List
  const fetchHistory = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        page,
        page_size: pageSize,
      }
      if (severity) params.severity = severity
      if (componentId) params.component_id = componentId.trim()
      if (queryStr) params.query_str = queryStr.trim()
      if (startDate) params.start_date = new Date(startDate).toISOString()
      if (endDate) params.end_date = new Date(endDate).toISOString()

      const res = await api.get('/workitems/history', { params })
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch (err) {
      console.error('Failed to load history', err)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, severity, componentId, queryStr, startDate, endDate])

  useEffect(() => {
    fetchStats()
  }, [])

  useEffect(() => {
    fetchHistory()
  }, [fetchHistory])

  const handleResetFilters = () => {
    setSeverity('')
    setComponentId('')
    setQueryStr('')
    setStartDate('')
    setEndDate('')
    setPage(1)
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="min-h-screen bg-[#050505] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900/40 via-[#050505] to-black text-slate-300 font-sans selection:bg-indigo-500/30">
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
              className="px-4 py-1.5 rounded-lg text-xs font-semibold tracking-wider uppercase text-slate-400 hover:text-white hover:bg-white/5 transition-all duration-200">
              Dashboard
            </button>
            <button onClick={() => navigate('/history')}
              className="px-4 py-1.5 rounded-lg text-xs font-semibold tracking-wider uppercase transition-all duration-200 bg-indigo-500 text-white shadow-lg shadow-indigo-500/20">
              Incident History
            </button>
          </div>
        </div>
        
        <div className="flex items-center gap-6">
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
        
        {/* Header Block */}
        <div>
          <h2 className="font-display text-2xl font-bold text-white tracking-wide">INCIDENT HISTORY ARCHIVE</h2>
          <p className="text-sm text-slate-500 mt-1">Enterprise-grade post-incident knowledge base and telemetry records</p>
        </div>

        {/* Aggregate Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-6 shadow-xl relative overflow-hidden">
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Total Closed Incidents</p>
            {loadingStats ? (
              <div className="h-8 w-24 bg-white/5 rounded animate-pulse mt-2"></div>
            ) : (
              <p className="text-3xl font-display font-semibold text-white mt-1">{stats?.total_closed || 0}</p>
            )}
            <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/5 rounded-full blur-2xl pointer-events-none"></div>
          </div>

          <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-6 shadow-xl relative overflow-hidden">
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Avg Time to Repair (MTTR)</p>
            {loadingStats ? (
              <div className="h-8 w-24 bg-white/5 rounded animate-pulse mt-2"></div>
            ) : (
              <p className="text-3xl font-display font-semibold text-emerald-400 mt-1">
                {stats?.avg_mttr_minutes ? `${stats.avg_mttr_minutes}m` : '0m'}
              </p>
            )}
            <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-2xl pointer-events-none"></div>
          </div>

          <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-6 shadow-xl relative overflow-hidden md:col-span-2">
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">Severity Distribution</p>
            {loadingStats ? (
              <div className="h-8 w-full bg-white/5 rounded animate-pulse mt-2"></div>
            ) : (
              <div className="flex items-center gap-4 mt-3">
                {['P0', 'P1', 'P2', 'P3'].map((s) => {
                  const count = stats?.severity_distribution?.[s] || 0
                  const total = Object.values(stats?.severity_distribution || {}).reduce((a, b) => a + b, 0) || 1
                  const width = `${Math.max((count / total) * 100, 5)}%`
                  const colors = {
                    P0: 'bg-rose-500',
                    P1: 'bg-amber-500',
                    P2: 'bg-indigo-500',
                    P3: 'bg-slate-500',
                  }
                  return (
                    <div key={s} className="flex-1">
                      <div className="flex justify-between text-xs font-mono text-slate-400 mb-1">
                        <span>{s}</span>
                        <span>{count}</span>
                      </div>
                      <div className="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
                        <div className={`h-full rounded-full ${colors[s]}`} style={{ width }}></div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Filters Card */}
        <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center gap-2 border-b border-white/5 pb-3">
            <span className="text-indigo-400 text-sm">🎛️</span>
            <h3 className="text-sm font-semibold text-white uppercase tracking-wider">Historical Filters</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            
            {/* Keyword Search */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Keyword Search</label>
              <input
                type="text"
                placeholder="Title / description..."
                value={queryStr}
                onChange={(e) => setQueryStr(e.target.value)}
                className="bg-black/40 border border-white/10 text-xs rounded-xl px-3 py-2 w-full text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-all"
              />
            </div>

            {/* Severity */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Severity</label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
                className="bg-black/40 border border-white/10 text-xs rounded-xl px-3 py-2 w-full text-white focus:outline-none focus:border-indigo-500 transition-all cursor-pointer"
              >
                <option value="" className="bg-[#0f0f0f]">All Severities</option>
                <option value="P0" className="bg-[#0f0f0f]">P0 (Critical)</option>
                <option value="P1" className="bg-[#0f0f0f]">P1 (Major)</option>
                <option value="P2" className="bg-[#0f0f0f]">P2 (Medium)</option>
                <option value="P3" className="bg-[#0f0f0f]">P3 (Minor)</option>
              </select>
            </div>

            {/* Component ID */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Component ID</label>
              <input
                type="text"
                placeholder="e.g. AUTH_SERVICE..."
                value={componentId}
                onChange={(e) => setComponentId(e.target.value)}
                className="bg-black/40 border border-white/10 text-xs rounded-xl px-3 py-2 w-full text-white placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-all"
              />
            </div>

            {/* Start Date */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Closed After</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="bg-black/40 border border-white/10 text-xs rounded-xl px-3 py-2 w-full text-white focus:outline-none focus:border-indigo-500 transition-all cursor-pointer"
              />
            </div>

            {/* End Date */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Closed Before</label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="bg-black/40 border border-white/10 text-xs rounded-xl px-3 py-2 w-full text-white focus:outline-none focus:border-indigo-500 transition-all cursor-pointer"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              onClick={handleResetFilters}
              className="text-xs font-semibold text-slate-400 hover:text-white border border-white/10 hover:bg-white/5 px-4 py-2 rounded-xl transition"
            >
              Reset Filters
            </button>
          </div>
        </div>

        {/* History List Table */}
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl overflow-hidden shadow-2xl">
          {loading ? (
            <div className="divide-y divide-white/5">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="p-8 space-y-3 animate-pulse">
                  <div className="flex justify-between">
                    <div className="h-4 w-1/4 bg-white/5 rounded"></div>
                    <div className="h-4 w-1/6 bg-white/5 rounded"></div>
                  </div>
                  <div className="h-4 w-1/2 bg-white/5 rounded"></div>
                </div>
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="px-8 py-24 text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-white/5 text-slate-500 mb-4">
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 10-8 0v4h8z" />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-white mb-1">No Historical Records Found</h3>
              <p className="text-slate-500 text-sm">Try adjusting your filters or search keywords.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-black/20 text-xs font-medium text-slate-500 uppercase tracking-widest border-b border-white/5">
                    <th className="px-8 py-4 font-medium">Severity</th>
                    <th className="px-8 py-4 font-medium">Component</th>
                    <th className="px-8 py-4 font-medium">Title</th>
                    <th className="px-8 py-4 font-medium">RCA Summary</th>
                    <th className="px-8 py-4 font-medium">Closed By / Date</th>
                    <th className="px-8 py-4 font-medium">MTTR</th>
                    <th className="px-8 py-4"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {items.map(inc => (
                    <tr key={inc.id}
                      onClick={() => navigate(`/incidents/${inc.id}`)}
                      className="group hover:bg-white/[0.04] cursor-pointer transition-all duration-200">
                      <td className="px-8 py-5"><SeverityBadge severity={inc.severity} short /></td>
                      <td className="px-8 py-5">
                        <div className="font-mono text-sm text-slate-200">{inc.component_id}</div>
                        <div className="text-xs text-slate-500 mt-1 uppercase tracking-wide">{inc.component_type}</div>
                      </td>
                      <td className="px-8 py-5">
                        <div className="text-sm font-medium text-slate-200 max-w-xs truncate group-hover:text-white transition-colors">
                          {inc.title}
                        </div>
                      </td>
                      <td className="px-8 py-5">
                        {inc.rca ? (
                          <div>
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase">
                              {inc.rca.root_cause_category}
                            </span>
                            <div className="text-xs text-slate-500 mt-1 max-w-xs truncate">{inc.rca.fix_applied}</div>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-600">No RCA submitted</span>
                        )}
                      </td>
                      <td className="px-8 py-5 text-xs font-mono">
                        <div className="text-slate-300 font-semibold">{inc.closed_by || 'system'}</div>
                        <div className="text-slate-500 mt-1">{new Date(inc.closed_at).toLocaleDateString()}</div>
                      </td>
                      <td className="px-8 py-5">
                        <span className="inline-flex items-center justify-center px-2 py-1 rounded-md bg-white/5 border border-white/10 text-xs font-mono text-slate-300">
                          {inc.mttr_minutes ? `${inc.mttr_minutes}m` : '—'}
                        </span>
                      </td>
                      <td className="px-8 py-5 text-right">
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-400 opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-300">
                          VIEW RCA
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

        {/* Pagination controls */}
        {totalPages > 1 && (
          <div className="flex justify-between items-center bg-white/[0.01] border border-white/5 p-4 rounded-2xl">
            <span className="text-xs text-slate-500 font-mono">
              Showing page {page} of {totalPages} ({total} entries)
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(p => Math.max(p - 1, 1))}
                disabled={page === 1}
                className="text-xs font-semibold px-4 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 disabled:opacity-30 transition"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => Math.min(p + 1, totalPages))}
                disabled={page === totalPages}
                className="text-xs font-semibold px-4 py-2 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 disabled:opacity-30 transition"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
