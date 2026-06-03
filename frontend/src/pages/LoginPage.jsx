import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'
import PasswordInput from '../components/PasswordInput'

export default function LoginPage() {
  const navigate = useNavigate()
  const setAuth = useAppStore((s) => s.setAuth)
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const form = new URLSearchParams()
      form.append('username', identifier)
      form.append('password', password)

      const loginRes = await api.post('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      const token = loginRes.data.access_token

      const meRes = await api.get('/users/me', {
        headers: { Authorization: `Bearer ${token}` },
      })
      setAuth(meRes.data, token)
      navigate('/')
    } catch (err) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') setError(detail)
      else setError('Login failed. Check your credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center lg:gap-20">
      {/* Left panel — desktop only */}
      <div className="hidden lg:flex flex-col justify-center flex-1 max-w-xs">
        <p className="text-[var(--accent)] text-sm font-medium tracking-wide uppercase mb-3">CV Barber</p>
        <h2 className="text-[32px] font-bold tracking-tight text-[var(--text-primary)] leading-tight">
          Your CV, tailored for every job.
        </h2>
        <p className="mt-3 text-[var(--text-secondary)] text-[15px]">
          Upload once. Tailored for every role.
        </p>
      </div>

      {/* Right panel — form */}
      <div className="w-full max-w-md">
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-8">
          <h1 className="text-2xl font-bold tracking-tight">Welcome back</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">Sign in to your account</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">Email or username</label>
              <input
                type="text"
                required
                autoComplete="username"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                className="w-full bg-[var(--bg)] border border-[rgba(255,255,255,0.10)] text-[var(--text-primary)] rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#5E6AD2]/30 focus:border-[#5E6AD2]/60 transition-colors placeholder:text-[var(--text-muted)]"
              />
            </div>
            <PasswordInput
              label="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white font-medium h-11 rounded-lg transition-colors mt-1"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>

            {error && <p className="text-red-400 text-sm">{error}</p>}
          </form>

          <p className="text-sm text-[var(--text-muted)] mt-6 text-center">
            Don't have an account?{' '}
            <Link to="/register" className="text-[var(--accent)] hover:opacity-80 transition-opacity">
              Register
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
