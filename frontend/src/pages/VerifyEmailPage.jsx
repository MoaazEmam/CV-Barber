import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'

export default function VerifyEmailPage() {
  const navigate = useNavigate()
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(false)
  const [cooldown, setCooldown] = useState(60) // first code was sent on register

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  if (!user) return <Navigate to="/login" replace />
  if (user.is_verified) return <Navigate to="/" replace />

  const handleVerify = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await api.post('/auth/verify-code', { code })
      sessionStorage.removeItem('postRegister')
      setUser(data)
      navigate('/')
    } catch (err) {
      setError(err?.response?.data?.detail || 'Verification failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    setError('')
    setInfo('')
    try {
      await api.post('/auth/request-verify-code')
      setInfo('A new code is on its way to your inbox.')
      setCooldown(60)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not resend the code.')
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-8">
          <h1 className="text-2xl font-bold tracking-tight">Verify your email</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-1">
            We sent a 6-digit code to <span className="text-[var(--text-primary)]">{user.email}</span>
          </p>

          <form onSubmit={handleVerify} className="mt-6 space-y-4">
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              required
              placeholder="123456"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              className="w-full bg-[var(--bg)] border border-[rgba(255,255,255,0.10)] text-[var(--text-primary)] rounded-lg px-3 py-2.5 text-center text-2xl tracking-[0.5em] focus:outline-none focus:ring-2 focus:ring-[#5E6AD2]/30 focus:border-[#5E6AD2]/60 transition-colors placeholder:text-[var(--text-muted)] placeholder:tracking-[0.5em]"
            />
            <button
              type="submit"
              disabled={loading || code.length !== 6}
              className="w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white font-medium h-11 rounded-lg transition-colors"
            >
              {loading ? 'Verifying...' : 'Verify'}
            </button>
            {error && <p className="text-red-400 text-sm">{error}</p>}
            {info && <p className="text-green-400 text-sm">{info}</p>}
          </form>

          <p className="text-sm text-[var(--text-muted)] mt-6 text-center">
            Didn't get it?{' '}
            <button
              onClick={handleResend}
              disabled={cooldown > 0}
              className="text-[var(--accent)] hover:opacity-80 disabled:opacity-40 transition-opacity"
            >
              {cooldown > 0 ? `Resend code (${cooldown}s)` : 'Resend code'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
