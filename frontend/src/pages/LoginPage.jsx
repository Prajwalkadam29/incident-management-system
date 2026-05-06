import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '@/api/client'

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const navigate = useNavigate()

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await api.post('/auth/login', { username, password })
      localStorage.setItem('ims_token', res.data.access_token)
      localStorage.setItem('ims_user', JSON.stringify({ username: res.data.username, role: res.data.role }))
      navigate('/')
    } catch {
      setError('Invalid username or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#050505] bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-900/20 via-[#050505] to-black text-slate-300 font-sans selection:bg-indigo-500/30 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Decorative background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-500/10 rounded-full blur-[100px] pointer-events-none"></div>

      <div className="w-full max-w-md relative z-10">
        {/* Logo / Header */}
        <div className="text-center mb-10">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-[0_0_40px_rgba(99,102,241,0.3)] mb-6">
            <span className="text-3xl">⚡</span>
          </div>
          <h1 className="text-2xl font-display font-bold text-white tracking-wide">MISSION CONTROL</h1>
          <p className="text-indigo-400 text-xs font-semibold uppercase tracking-widest mt-2">Secure Access Portal</p>
        </div>

        {/* Card */}
        <div className="backdrop-blur-xl bg-white/[0.02] border border-white/5 rounded-2xl p-8 shadow-2xl">
          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Operator ID</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="Enter username"
                required
                className="w-full bg-[#0a0a0a]/80 border border-white/10 rounded-xl px-4 py-3 text-slate-200 text-sm focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition placeholder:text-slate-600 font-medium"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Passcode</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full bg-[#0a0a0a]/80 border border-white/10 rounded-xl px-4 py-3 text-slate-200 text-sm focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/50 transition placeholder:text-slate-600 font-medium"
              />
            </div>

            {error && (
              <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 px-4 py-3 rounded-xl flex items-center gap-3 animate-in fade-in">
                <span className="text-lg">⚠️</span>
                <p className="text-sm font-medium">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full relative group overflow-hidden bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold tracking-wide py-3.5 rounded-xl transition-all shadow-[0_0_20px_rgba(99,102,241,0.2)] mt-2"
            >
              <div className="absolute inset-0 w-full h-full bg-gradient-to-r from-transparent via-white/20 to-transparent -translate-x-full group-hover:animate-[shimmer_1.5s_infinite]"></div>
              <span className="relative z-10 flex items-center justify-center gap-2">
                {loading ? (
                   <>
                     <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                     AUTHENTICATING...
                   </>
                ) : 'AUTHENTICATE'}
              </span>
            </button>
          </form>

          <div className="mt-8 pt-8 border-t border-white/5">
            <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest text-center mb-4">Authorized Profiles</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3 text-center hover:bg-white/[0.04] transition-colors cursor-pointer" onClick={() => {setUsername('admin'); setPassword('Admin@IMS2026!')}}>
                <p className="text-xs font-bold text-indigo-400 mb-1 tracking-wider uppercase">Commander</p>
                <p className="text-[10px] text-slate-500 font-mono">admin</p>
              </div>
              <div className="bg-white/[0.02] border border-white/5 rounded-xl p-3 text-center hover:bg-white/[0.04] transition-colors cursor-pointer" onClick={() => {setUsername('viewer'); setPassword('Viewer@IMS2026!')}}>
                <p className="text-xs font-bold text-emerald-400 mb-1 tracking-wider uppercase">Observer</p>
                <p className="text-[10px] text-slate-500 font-mono">viewer</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}