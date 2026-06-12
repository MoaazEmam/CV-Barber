import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'

// One-time screen after the first Google sign-in: the account exists but has
// no username yet (username IS NULL on the backend).
export default function ChooseUsernamePage() {
  const navigate = useNavigate()
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const [username, setUsername] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (!user) return <Navigate to="/login" replace />
  if (user.username != null) return <Navigate to="/" replace />

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    const uname = username.trim()
    if (uname.length < 3) {
      setError('Username must be at least 3 characters long.')
      return
    }
    if (uname.length > 30) {
      setError('Username must be at most 30 characters long.')
      return
    }
    if (!/^[A-Za-z0-9]+$/.test(uname)) {
      setError('Username can only contain letters and numbers.')
      return
    }
    setLoading(true)
    try {
      const { data } = await api.patch('/users/me', { username: uname })
      setUser(data)
      navigate('/')
    } catch (err) {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Could not set the username.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-8">
          <h1 className="text-2xl font-bold tracking-tight">Pick a username</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            One last step — choose how you'll appear in CV Barber.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <input
              type="text"
              required
              autoFocus
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="username"
              className="w-full bg-[var(--bg)] border border-[rgba(255,255,255,0.10)] text-[var(--text-primary)] rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#5E6AD2]/30 focus:border-[#5E6AD2]/60 transition-colors placeholder:text-[var(--text-muted)]"
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white font-medium h-11 rounded-lg transition-colors"
            >
              {loading ? 'Saving...' : 'Continue'}
            </button>
            {error && <p className="text-red-400 text-sm">{error}</p>}
          </form>
        </div>
      </div>
    </div>
  )
}
