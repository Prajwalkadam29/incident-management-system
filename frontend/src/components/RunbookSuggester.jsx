import { useState } from 'react'
import api from '@/api/client'

export function RunbookSuggester({ incident }) {
  const [runbook, setRunbook]   = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')
  const [expanded, setExpanded] = useState(true)

  const generate = async () => {
    setLoading(true)
    setError('')
    setRunbook(null)

    try {
      const res = await api.post('/ai/runbook', {
        work_item_id:   incident.id,
        component_id:   incident.component_id,
        component_type: incident.component_type,
        error_code:     incident.error_code || 'UNKNOWN',
        severity:       incident.severity,
        message:        incident.title,
        signal_count:   parseInt(incident.signal_count) || 1,
      })
      setRunbook(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to generate runbook')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-gray-900 border border-blue-800/40 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">🤖</span>
          <h2 className="font-semibold text-white">AI Runbook Suggester</h2>
          {runbook && (
            <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
              via {runbook.provider} / {runbook.model}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {runbook && (
            <button onClick={() => setExpanded(e => !e)}
              className="text-xs text-gray-500 hover:text-white transition">
              {expanded ? 'Collapse' : 'Expand'}
            </button>
          )}
          <button
            onClick={generate}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold px-4 py-1.5 rounded-lg transition flex items-center gap-2"
          >
            {loading ? (
              <>
                <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Generating...
              </>
            ) : (
              <>✨ {runbook ? 'Regenerate' : 'Generate Runbook'}</>
            )}
          </button>
        </div>
      </div>

      {/* Content */}
      {!runbook && !loading && !error && (
        <div className="px-6 py-8 text-center text-gray-600 text-sm">
          Click "Generate Runbook" to get AI-powered remediation steps for this incident
        </div>
      )}

      {loading && (
        <div className="px-6 py-8 text-center">
          <div className="inline-flex flex-col items-center gap-3">
            <div className="w-8 h-8 border-2 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
            <p className="text-gray-500 text-sm">Analyzing incident with AI...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="px-6 py-4 text-red-400 text-sm bg-red-900/10">
          ❌ {error}
        </div>
      )}

      {runbook && expanded && (
        <div className="p-6 space-y-5">
          {/* Summary */}
          <div className="bg-blue-950/30 border border-blue-800/30 rounded-lg p-4">
            <p className="text-sm text-blue-300">{runbook.summary}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* Immediate Actions */}
            <Section
              icon="🚨"
              title="Immediate Actions"
              color="red"
              items={runbook.immediate_actions}
            />

            {/* Investigation Steps */}
            <Section
              icon="🔍"
              title="Investigation Steps"
              color="yellow"
              items={runbook.investigation_steps}
            />

            {/* Prevention */}
            <Section
              icon="🛡️"
              title="Prevention"
              color="green"
              items={runbook.prevention}
            />

            {/* Meta */}
            <div className="space-y-3">
              <MetaCard
                icon="⏱️"
                label="Estimated Resolution"
                value={runbook.estimated_resolution_time}
                color="blue"
              />
              <MetaCard
                icon="📞"
                label="Escalation Path"
                value={runbook.escalation_path}
                color="purple"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


function Section({ icon, title, color, items }) {
  const colors = {
    red:    'border-red-800/30 text-red-400',
    yellow: 'border-yellow-800/30 text-yellow-400',
    green:  'border-green-800/30 text-green-400',
    blue:   'border-blue-800/30 text-blue-400',
  }

  return (
    <div className={`border rounded-lg p-4 bg-gray-800/30 ${colors[color]}`}>
      <h3 className="text-xs font-semibold uppercase tracking-wider mb-3 flex items-center gap-1.5">
        <span>{icon}</span> {title}
      </h3>
      <ol className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2 text-sm text-gray-300">
            <span className="text-gray-600 shrink-0 font-mono">{i + 1}.</span>
            <span>{item}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}


function MetaCard({ icon, label, value, color }) {
  const colors = {
    blue:   'border-blue-800/30 text-blue-400',
    purple: 'border-purple-800/30 text-purple-400',
  }

  return (
    <div className={`border rounded-lg p-4 bg-gray-800/30 ${colors[color]}`}>
      <p className="text-xs font-semibold uppercase tracking-wider mb-1 flex items-center gap-1.5">
        <span>{icon}</span> {label}
      </p>
      <p className="text-sm text-gray-300">{value}</p>
    </div>
  )
}