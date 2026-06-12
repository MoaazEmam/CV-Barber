import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import api from '../lib/axios'
import { authErrorMessage } from '../lib/authErrors'
import useAppStore from '../store/useAppStore'
import PasswordInput from '../components/PasswordInput'
import GoogleButton from '../components/GoogleButton'

export default function RegisterPage() {
  const navigate = useNavigate()
  const setAuth = useAppStore((s) => s.setAuth)
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

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
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }
    if (password !== confirmPassword) {
      setError("Passwords don't match.")
      return
    }
    setLoading(true)
    try {
      await api.post(
        '/auth/register',
        { email, username: uname, password },
        { headers: { 'Content-Type': 'application/json' } },
      )

      const form = new URLSearchParams()
      form.append('username', email)
      form.append('password', password)
      const loginRes = await api.post('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      const token = loginRes.data.access_token
      const meRes = await api.get('/users/me', {
        headers: { Authorization: `Bearer ${token}` },
      })
      setAuth(meRes.data, token)
      // Hard-gate fresh signups behind email verification (flag read by
      // ProtectedRoute, cleared by VerifyEmailPage on success).
      sessionStorage.setItem('postRegister', '1')
      navigate('/verify-email')
    } catch (err) {
      setError(authErrorMessage(err, 'register'))
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
          <h1 className="text-2xl font-bold tracking-tight">Create account</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">Start tailoring your CV</p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-[var(--bg)] border border-[rgba(255,255,255,0.10)] text-[var(--text-primary)] rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#5E6AD2]/30 focus:border-[#5E6AD2]/60 transition-colors placeholder:text-[var(--text-muted)]"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1.5">Username</label>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-[var(--bg)] border border-[rgba(255,255,255,0.10)] text-[var(--text-primary)] rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#5E6AD2]/30 focus:border-[#5E6AD2]/60 transition-colors placeholder:text-[var(--text-muted)]"
              />
            </div>
            <PasswordInput
              label="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
            <PasswordInput
              label="Confirm Password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
            />

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white font-medium h-11 rounded-lg transition-colors mt-1"
            >
              {loading ? 'Creating account...' : 'Create account'}
            </button>

            {error && <p className="text-red-400 text-sm">{error}</p>}
          </form>

          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-[var(--border)]" />
            <span className="text-xs text-[var(--text-muted)]">or</span>
            <div className="flex-1 h-px bg-[var(--border)]" />
          </div>
          <GoogleButton onError={setError} />

          <p className="text-sm text-[var(--text-muted)] mt-6 text-center">
            Already have an account?{' '}
            <Link to="/login" className="text-[var(--accent)] hover:opacity-80 transition-opacity">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
