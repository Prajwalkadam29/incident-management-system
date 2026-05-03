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
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo / Header */}
        <div className="text-center mb-8">
          <div className="text-4xl mb-3">🚨</div>
          <h1 className="text-2xl font-bold text-white">Incident Management System</h1>
          <p className="text-gray-500 text-sm mt-1">SRE Operations Platform</p>
        </div>

        {/* Card */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8">
          <h2 className="text-lg font-semibold text-white mb-6">Sign in</h2>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="admin"
                required
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition"
              />
            </div>

            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition"
              />
            </div>

            {error && (
              <p className="text-red-400 text-sm bg-red-900/20 border border-red-800/50 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </form>

          <div className="mt-6 pt-6 border-t border-gray-800">
            <p className="text-xs text-gray-600 text-center">Default credentials</p>
            <div className="flex gap-3 mt-2">
              <div className="flex-1 bg-gray-800/50 rounded-lg p-2 text-center">
                <p className="text-xs text-gray-500">Admin</p>
                <p className="text-xs text-gray-400 font-mono">admin / admin123</p>
              </div>
              <div className="flex-1 bg-gray-800/50 rounded-lg p-2 text-center">
                <p className="text-xs text-gray-500">Viewer</p>
                <p className="text-xs text-gray-400 font-mono">viewer / viewer123</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}