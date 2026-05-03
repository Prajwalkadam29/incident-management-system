import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '@/api/client'
import { SeverityBadge } from '@/components/SeverityBadge'
import { StatusBadge } from '@/components/StatusBadge'

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
    <div className="min-h-screen bg-gray-950">
      {/* Navbar */}
      <nav className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-3">
        <button onClick={() => navigate('/')}
          className="text-gray-500 hover:text-white transition text-sm">
          ← Dashboard
        </button>
        <span className="text-gray-700">/</span>
        <span className="text-gray-400 text-sm font-mono truncate">{incident.component_id}</span>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-6 space-y-6">
        {/* Header */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <SeverityBadge severity={incident.severity} />
                <StatusBadge status={incident.status} />
              </div>
              <h1 className="text-xl font-bold text-white">{incident.title}</h1>
              <p className="text-gray-500 text-sm mt-1 font-mono">{incident.component_id} · {incident.component_type}</p>
            </div>

            {/* Transition Button */}
            {canTransition && (
              <div className="flex flex-col items-end gap-2">
                {needsRCA ? (
                  <button onClick={() => navigate(`/incidents/${id}/rca`)}
                    className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold px-4 py-2 rounded-lg transition">
                    Submit RCA to Close →
                  </button>
                ) : (
                  <button
                    onClick={() => handleTransition(nextStatus)}
                    disabled={transitioning}
                    className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2 rounded-lg transition">
                    {transitioning ? 'Updating...' : `Move to ${nextStatus} →`}
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

          {/* Metadata grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-6 border-t border-gray-800">
            <MetaItem label="Signal Count" value={incident.signal_count} />
            <MetaItem label="Created" value={fmt(incident.created_at)} />
            <MetaItem label="Resolved" value={fmt(incident.resolved_at)} />
            <MetaItem label="MTTR" value={incident.mttr_minutes ? `${incident.mttr_minutes}m` : '—'} />
          </div>
        </div>

        {/* RCA Block (if exists) */}
        {incident.rca && (
          <div className="bg-gray-900 border border-green-800/40 rounded-xl p-6">
            <h2 className="font-semibold text-green-400 mb-4">✅ Root Cause Analysis</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <RCAField label="Category" value={incident.rca.root_cause_category} />
              <RCAField label="Submitted by" value={incident.rca.submitted_by || '—'} />
              <RCAField label="Fix Applied" value={incident.rca.fix_applied} />
              <RCAField label="Prevention Steps" value={incident.rca.prevention_steps} />
            </div>
          </div>
        )}

        {/* Raw Signals */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl">
          <div className="px-6 py-4 border-b border-gray-800">
            <h2 className="font-semibold text-white">Raw Signals <span className="text-gray-500 font-normal text-sm">({signals.length})</span></h2>
          </div>
          <div className="overflow-x-auto">
            {signals.length === 0 ? (
              <p className="px-6 py-8 text-center text-gray-600">No signals loaded yet</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-gray-500 uppercase tracking-wider">
                    <th className="px-6 py-3 text-left">Time</th>
                    <th className="px-6 py-3 text-left">Error Code</th>
                    <th className="px-6 py-3 text-left">Message</th>
                    <th className="px-6 py-3 text-left">Severity</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/50">
                  {signals.map((s, i) => (
                    <tr key={i} className="hover:bg-gray-800/30">
                      <td className="px-6 py-3 text-gray-500 font-mono whitespace-nowrap">
                        {new Date(s.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="px-6 py-3 font-mono text-orange-400">{s.error_code}</td>
                      <td className="px-6 py-3 text-gray-300 max-w-sm truncate">{s.message}</td>
                      <td className="px-6 py-3"><SeverityBadge severity={s.severity} short /></td>
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
      <p className="text-xs text-gray-500 uppercase tracking-wider">{label}</p>
      <p className="text-sm text-gray-300 mt-0.5">{value || '—'}</p>
    </div>
  )
}

function RCAField({ label, value }) {
  return (
    <div>
      <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-gray-300">{value}</p>
    </div>
  )
}

function LoadingScreen() {
  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <p className="text-gray-500 animate-pulse">Loading incident...</p>
    </div>
  )
}

function fmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}