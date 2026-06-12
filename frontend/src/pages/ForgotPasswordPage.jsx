import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../lib/axios'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // Always 202 — doesn't reveal whether the email has an account.
      await api.post('/auth/forgot-password', { email })
      setSent(true)
    } catch {
      setError('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-8">
          <h1 className="text-2xl font-bold tracking-tight">Forgot password</h1>

          {sent ? (
            <div className="mt-4">
              <p className="text-[var(--text-secondary)] text-sm">
                If an account exists for{' '}
                <span className="text-[var(--text-primary)]">{email}</span>, a reset
                link is on its way. Check your inbox (and spam folder).
              </p>
              <p className="text-sm text-[var(--text-muted)] mt-6 text-center">
                <Link to="/login" className="text-[var(--accent)] hover:opacity-80 transition-opacity">
                  Back to sign in
                </Link>
              </p>
            </div>
          ) : (
            <>
              <p className="text-[var(--text-secondary)] text-sm mt-1">
                Enter your account email and we'll send you a reset link.
              </p>
              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                <input
                  type="email"
                  required
                  autoFocus
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-[var(--bg)] border border-[rgba(255,255,255,0.10)] text-[var(--text-primary)] rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#5E6AD2]/30 focus:border-[#5E6AD2]/60 transition-colors placeholder:text-[var(--text-muted)]"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white font-medium h-11 rounded-lg transition-colors"
                >
                  {loading ? 'Sending...' : 'Send reset link'}
                </button>
                {error && <p className="text-red-400 text-sm">{error}</p>}
              </form>
              <p className="text-sm text-[var(--text-muted)] mt-6 text-center">
                Remembered it?{' '}
                <Link to="/login" className="text-[var(--accent)] hover:opacity-80 transition-opacity">
                  Sign in
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
