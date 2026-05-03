import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '@/api/client'

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
  const [error, setError] = useState('')

  const set = (field) => (e) => setForm(f => ({ ...f, [field]: e.target.value }))

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
    <div className="min-h-screen bg-gray-950">
      <nav className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-3">
        <button onClick={() => navigate(`/incidents/${id}`)}
          className="text-gray-500 hover:text-white transition text-sm">
          ← Back to Incident
        </button>
        <span className="text-gray-700">/</span>
        <span className="text-gray-400 text-sm">Root Cause Analysis</span>
      </nav>

      <main className="max-w-2xl mx-auto px-6 py-8">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8">
          <h1 className="text-xl font-bold text-white mb-2">Submit Root Cause Analysis</h1>
          <p className="text-gray-500 text-sm mb-8">
            Complete RCA is required before this incident can be closed.
          </p>

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
              <textarea rows={2} value={form.timeline_notes}
                onChange={set('timeline_notes')} placeholder="Optional — key events during the incident..."
                className={inputCls} />
            </Field>

            {error && (
              <p className="text-red-400 text-sm bg-red-900/20 border border-red-800/50 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <div className="flex gap-3 pt-2">
              <button type="button" onClick={() => navigate(`/incidents/${id}`)}
                className="flex-1 bg-gray-800 hover:bg-gray-700 text-gray-300 font-semibold py-2.5 rounded-lg transition">
                Cancel
              </button>
              <button type="submit" disabled={submitting}
                className="flex-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition">
                {submitting ? 'Submitting...' : 'Submit RCA & Close Incident'}
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
    <div>
      <label className="block text-sm text-gray-400 mb-1.5">{label}</label>
      {children}
    </div>
  )
}

const inputCls = "w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition text-sm"