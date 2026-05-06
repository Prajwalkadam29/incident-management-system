import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '@/api/client'
import { SparklesIcon, ArrowPathIcon } from '@heroicons/react/24/solid'

const CATEGORIES = [
  'INFRASTRUCTURE', 'APPLICATION', 'NETWORK',
  'DEPENDENCY', 'HUMAN_ERROR', 'UNKNOWN'
]

export default function RCAFormPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [form, setForm] = useState({
    incident_start: '',
    incident_end: '',
    root_cause_category: 'INFRASTRUCTURE',
    fix_applied: '',
    prevention_steps: '',
    affected_users_count: '',
    timeline_notes: '',
    submitted_by: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [incident, setIncident] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    // Fetch incident details to feed into AI
    api.get(`/workitems/${id}`).then(res => setIncident(res.data)).catch(console.error)
  }, [id])

  const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }))

  const handleGenerateRCA = async () => {
    if (!incident) return
    setGenerating(true)
    setError('')
    try {
      // Calculate duration roughly
      const start = new Date(incident.created_at)
      const durationMin = Math.round((Date.now() - start.getTime()) / 60000)

      // Get timeline from signals if possible (mocked for the payload here)
      const res = await api.post(`/ai/rca-draft`, {
        work_item_id: incident.id,
        component_id: incident.component_id,
        component_type: incident.component_type,
        severity: incident.severity,
        title: incident.title,
        total_signals: incident.signal_count,
        duration_minutes: durationMin,
        resolution_notes: "Auto-generating RCA",
        timeline_events: [{"time": new Date().toISOString(), "event": "Incident resolved"}]
      })
      
      const ai = res.data
      setForm(f => ({
        ...f,
        fix_applied: ai.resolution,
        prevention_steps: ai.action_items.join('\n'),
        timeline_notes: `Executive Summary:\n${ai.executive_summary}\n\nRoot Cause:\n${ai.root_cause}\n\nTrigger:\n${ai.trigger}`
      }))
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to generate AI RCA draft')
    } finally {
      setGenerating(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setError('')

    try {
      // Submit RCA
      await api.post(`/workitems/${id}/rca`, {
        ...form,
        incident_start: new Date(form.incident_start).toISOString(),
        incident_end: new Date(form.incident_end).toISOString(),
      })

      // Auto-close the incident
      await api.patch(`/workitems/${id}/status`, { status: 'CLOSED' })

      navigate(`/incidents/${id}`)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to submit RCA')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#050505] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/20 via-[#050505] to-black text-slate-300 font-sans selection:bg-indigo-500/30">
      <nav className="sticky top-0 z-50 backdrop-blur-xl bg-[#050505]/70 border-b border-white/5 px-8 py-4 flex items-center gap-3 shadow-2xl">
        <button onClick={() => navigate(`/incidents/${id}`)}
          className="text-slate-400 hover:text-white transition-colors text-sm font-medium flex items-center gap-1">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Incident
        </button>
        <span className="text-white/20">/</span>
        <span className="text-indigo-400 text-sm font-medium tracking-wide">Root Cause Analysis</span>
      </nav>

      <main className="max-w-3xl mx-auto px-6 py-10">
        <div className="backdrop-blur-md bg-white/[0.02] border border-white/5 rounded-2xl p-8 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none -translate-y-1/2 translate-x-1/3"></div>
          
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-8 relative z-10 gap-4">
            <div>
              <h1 className="font-display text-2xl font-bold text-white tracking-wide">Submit Root Cause Analysis</h1>
              <p className="text-slate-500 text-sm mt-1">
                Complete RCA is required before this incident can be closed.
              </p>
            </div>
            <button 
              type="button" 
              onClick={handleGenerateRCA}
              disabled={generating || !incident}
              className="group relative overflow-hidden flex items-center gap-2 bg-indigo-500/20 text-indigo-300 hover:bg-indigo-500/30 hover:text-indigo-200 border border-indigo-500/40 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all shadow-[0_0_20px_rgba(99,102,241,0.15)] hover:shadow-[0_0_30px_rgba(99,102,241,0.3)] disabled:opacity-50 disabled:pointer-events-none"
            >
              <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/10 to-transparent -translate-x-full group-hover:animate-[shimmer_1.5s_infinite]"></div>
              {generating ? <ArrowPathIcon className="w-4 h-4 animate-spin relative z-10" /> : <SparklesIcon className="w-4 h-4 relative z-10" />}
              <span className="relative z-10">{generating ? 'Drafting with AI...' : 'Auto-Generate Draft'}</span>
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Timeline */}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Incident Start *">
                <input type="datetime-local" required value={form.incident_start}
                  onChange={set('incident_start')} className={inputCls} />
              </Field>
              <Field label="Incident End *">
                <input type="datetime-local" required value={form.incident_end}
                  onChange={set('incident_end')} className={inputCls} />
              </Field>
            </div>

            {/* Category */}
            <Field label="Root Cause Category *">
              <select required value={form.root_cause_category}
                onChange={set('root_cause_category')} className={inputCls}>
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </Field>

            {/* Fix Applied */}
            <Field label="Fix Applied *">
              <textarea required rows={3} value={form.fix_applied}
                onChange={set('fix_applied')} placeholder="Describe the fix that resolved the incident..."
                className={inputCls} />
            </Field>

            {/* Prevention Steps */}
            <Field label="Prevention Steps *">
              <textarea required rows={3} value={form.prevention_steps}
                onChange={set('prevention_steps')} placeholder="How will this be prevented in future?"
                className={inputCls} />
            </Field>

            {/* Optional fields */}
            <div className="grid grid-cols-2 gap-4">
              <Field label="Affected Users">
                <input type="text" value={form.affected_users_count}
                  onChange={set('affected_users_count')} placeholder="e.g. ~5,000"
                  className={inputCls} />
              </Field>
              <Field label="Submitted By">
                <input type="text" value={form.submitted_by}
                  onChange={set('submitted_by')} placeholder="your@email.com"
                  className={inputCls} />
              </Field>
            </div>

            <Field label="Timeline Notes">
              <textarea rows={4} value={form.timeline_notes}
                onChange={set('timeline_notes')} placeholder="Optional — key events during the incident..."
                className={inputCls} />
            </Field>

            {error && (
              <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 px-4 py-3 rounded-xl flex items-center gap-3 animate-in fade-in">
                <span className="text-lg">⚠️</span>
                <p className="text-sm font-medium">{error}</p>
              </div>
            )}

            <div className="flex gap-4 pt-4 relative z-10">
              <button type="button" onClick={() => navigate(`/incidents/${id}`)}
                className="flex-1 bg-white/5 hover:bg-white/10 text-slate-300 font-semibold py-3 rounded-xl transition border border-white/10">
                Cancel
              </button>
              <button type="submit" disabled={submitting}
                className="flex-[2] bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold py-3 rounded-xl transition shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2">
                {submitting ? (
                   <span className="flex items-center gap-2">
                     <span className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin"></span>
                     Submitting...
                   </span>
                ) : 'Submit RCA & Close Incident'}
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div className="flex flex-col gap-2 relative z-10">
      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest">{label}</label>
      {children}
    </div>
  )
}

const inputCls = "w-full bg-[#0a0a0a]/80 border border-white/10 rounded-xl px-4 py-3 text-slate-200 text-sm focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition placeholder:text-slate-600 font-medium"