import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '@/api/client'
import { SeverityBadge } from '@/components/SeverityBadge'
import { StatusBadge } from '@/components/StatusBadge'
import { RunbookSuggester } from '@/components/RunbookSuggester'
import { IncidentTimeline } from '@/components/IncidentTimeline'

const STATUS_FLOW = ['OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED']

export default function IncidentDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [incident, setIncident]   = useState(null)
  const [signals, setSignals]     = useState([])
  const [loading, setLoading]     = useState(true)
  const [transitioning, setTrans] = useState(false)
  const [error, setError]         = useState('')

  const fetchIncident = async () => {
    try {
      const [incRes, sigRes] = await Promise.all([
        api.get(`/workitems/${id}`),
        api.get('/signals/', { params: { work_item_id: id, limit: 100 } }),
      ])
      setIncident(incRes.data)
      setSignals(sigRes.data.signals || [])
    } catch {
      setError('Failed to load incident')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchIncident() }, [id])

  const handleTransition = async (newStatus) => {
    setTrans(true)
    setError('')
    try {
      await api.patch(`/workitems/${id}/status`, { status: newStatus })
      await fetchIncident()
    } catch (e) {
      setError(e.response?.data?.detail || 'Transition failed')
    } finally {
      setTrans(false)
    }
  }

  if (loading) return <LoadingScreen />
  if (!incident) return <div className="p-8 text-red-400">{error}</div>

  const currentIdx = STATUS_FLOW.indexOf(incident.status)
  const nextStatus = STATUS_FLOW[currentIdx + 1]
  const canTransition = nextStatus && incident.status !== 'CLOSED'
  const needsRCA = nextStatus === 'CLOSED' && !incident.rca

  return (
    <div className="min-h-screen bg-[#050505] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/20 via-[#050505] to-black text-slate-300 font-sans selection:bg-indigo-500/30">
      {/* Navbar with Glassmorphism */}
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-[#050505]/70 border-b border-white/5 px-8 py-4 flex items-center gap-3 shadow-2xl">
        <button onClick={() => navigate('/')}
          className="text-slate-400 hover:text-white transition-colors text-sm font-medium flex items-center gap-1">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Dashboard
        </button>
        <span className="text-white/20">/</span>
        <span className="text-indigo-400 text-sm font-mono tracking-wider truncate">{incident.component_id}</span>
      </nav>

      <main className="max-w-5xl mx-auto px-8 py-8 space-y-8">
        {/* Header Card */}
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-8 shadow-2xl shadow-black/50 relative overflow-hidden">
          {/* Decorative glow */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none -translate-y-1/2 translate-x-1/3"></div>
          
          <div className="flex items-start justify-between gap-6 flex-wrap relative z-10">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <SeverityBadge severity={incident.severity} />
                <StatusBadge status={incident.status} />
              </div>
              <h1 className="font-display text-2xl font-bold text-white tracking-wide">{incident.title}</h1>
              <p className="text-slate-400 text-sm mt-2 font-mono tracking-wider uppercase">{incident.component_id} <span className="text-white/20 px-2">•</span> {incident.component_type}</p>
            </div>

            {/* Transition Button */}
            {canTransition && (
              <div className="flex flex-col items-end gap-3 mt-4 md:mt-0">
                {needsRCA ? (
                  <button onClick={() => navigate(`/incidents/${id}/rca`)}
                    className="relative group overflow-hidden bg-indigo-500/20 hover:bg-indigo-500/30 border border-indigo-500/50 text-indigo-300 text-sm font-semibold px-6 py-2.5 rounded-xl transition-all duration-300 shadow-[0_0_20px_rgba(99,102,241,0.2)]">
                    <span className="relative z-10 flex items-center gap-2">
                      Submit RCA to Close
                      <svg className="w-4 h-4 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                    </span>
                  </button>
                ) : (
                  <button
                    onClick={() => handleTransition(nextStatus)}
                    disabled={transitioning}
                    className="bg-white/10 hover:bg-white/20 disabled:opacity-50 border border-white/10 text-white text-sm font-medium px-5 py-2.5 rounded-xl transition-all shadow-lg flex items-center gap-2 group">
                    {transitioning ? (
                       <span className="flex items-center gap-2">
                         <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin"></span>
                         Updating...
                       </span>
                    ) : (
                       <span className="flex items-center gap-2">
                         Move to <span className="font-bold tracking-wider">{nextStatus}</span>
                         <svg className="w-4 h-4 group-hover:translate-x-1 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                         </svg>
                       </span>
                    )}
                  </button>
                )}
              </div>
            )}
          </div>

          {error && (
            <p className="mt-3 text-red-400 text-sm bg-red-900/20 border border-red-800/50 rounded px-3 py-2">
              {error}
            </p>
          )}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-8 pt-8 border-t border-white/5 relative z-10">
            <MetaItem label="Signals Captured" value={incident.signal_count.toLocaleString()} />
            <MetaItem label="First Seen" value={fmt(incident.created_at)} />
            <MetaItem label="Resolved" value={fmt(incident.resolved_at)} />
            <MetaItem label="Time to Repair" value={incident.mttr_minutes ? `${incident.mttr_minutes}m` : '—'} />
          </div>
        </div>

        {/* RCA Block (if exists) */}
        {incident.rca && (
          <div className="backdrop-blur-md bg-emerald-500/5 border border-emerald-500/20 rounded-2xl p-8 shadow-xl relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none -translate-y-1/2 translate-x-1/3"></div>
            <h2 className="font-display text-xl font-semibold text-emerald-400 mb-6 flex items-center gap-3">
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Root Cause Analysis
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8 text-sm relative z-10">
              <RCAField label="Category" value={incident.rca.root_cause_category} />
              <RCAField label="Submitted by" value={incident.rca.submitted_by || '—'} />
              <RCAField label="Fix Applied" value={incident.rca.fix_applied} />
              <RCAField label="Prevention Steps" value={incident.rca.prevention_steps} />
            </div>
          </div>
        )}

        {/* Incident Timeline */}
        <IncidentTimeline workItemId={id} />

          {/* AI Runbook */}
        <RunbookSuggester incident={incident} />

        {/* Raw Signals */}
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl overflow-hidden shadow-2xl">
          <div className="px-8 py-5 border-b border-white/5 bg-white/[0.01]">
            <h2 className="font-display font-semibold text-white">Raw Signal Stream <span className="text-slate-500 ml-2 font-mono text-sm px-2 py-0.5 rounded-full bg-white/5 border border-white/10">{signals.length} captured</span></h2>
          </div>
          <div className="overflow-x-auto">
            {signals.length === 0 ? (
              <p className="px-6 py-8 text-center text-gray-600">No signals loaded yet</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-black/20 text-xs font-medium text-slate-500 uppercase tracking-widest border-b border-white/5">
                    <th className="px-8 py-4 text-left">Time</th>
                    <th className="px-8 py-4 text-left">Error Code</th>
                    <th className="px-8 py-4 text-left">Message</th>
                    <th className="px-8 py-4 text-left">Severity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {signals.map((s, i) => (
                    <tr key={i} className="hover:bg-white/[0.04] transition-colors">
                      <td className="px-8 py-4 text-slate-500 font-mono whitespace-nowrap text-xs">
                        {new Date(s.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="px-8 py-4 font-mono text-xs font-semibold text-rose-400/80">{s.error_code}</td>
                      <td className="px-8 py-4 text-sm text-slate-300 max-w-sm truncate">{s.message}</td>
                      <td className="px-8 py-4"><SeverityBadge severity={s.severity} short /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

function MetaItem({ label, value }) {
  return (
    <div>
      <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">{label}</p>
      <p className="text-sm font-medium text-slate-200">{value || '—'}</p>
    </div>
  )
}

function RCAField({ label, value }) {
  return (
    <div className="bg-white/5 border border-white/10 rounded-xl p-5">
      <p className="text-[10px] font-bold text-emerald-500/70 uppercase tracking-widest mb-2">{label}</p>
      <div className="text-slate-200 leading-relaxed font-medium whitespace-pre-wrap">{value}</div>
    </div>
  )
}

function LoadingScreen() {
  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center flex-col gap-4">
      <div className="w-12 h-12 rounded-xl bg-indigo-500/20 border-2 border-indigo-500/50 border-t-indigo-400 animate-spin"></div>
      <p className="text-indigo-400 font-display tracking-widest animate-pulse font-semibold">INITIALIZING</p>
    </div>
  )
}

function fmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}