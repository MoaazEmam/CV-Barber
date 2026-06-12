import { useEffect, useState } from 'react'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'

// Dismissible reminder for logged-in users whose email isn't verified yet
// (accounts created before email verification existed). Dismissal lasts for
// the browser session.
export default function VerifyEmailModal() {
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)
  const [dismissed, setDismissed] = useState(
    () => sessionStorage.getItem('verifyModalDismissed') === '1'
  )
  const [sent, setSent] = useState(false)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  // Hide for: logged-out, already verified, post-register flow (the
  // /verify-email page handles that), or dismissed this session.
  if (!user || user.is_verified || dismissed || sessionStorage.getItem('postRegister')) {
    return null
  }

  const dismiss = () => {
    sessionStorage.setItem('verifyModalDismissed', '1')
    setDismissed(true)
  }

  const handleSend = async () => {
    setError('')
    setInfo('')
    try {
      await api.post('/auth/request-verify-code')
      setSent(true)
      setCooldown(60)
      setInfo('Code sent — check your inbox.')
    } catch (err) {
      setError(err?.response?.data?.detail || 'Could not send the code.')
    }
  }

  const handleVerify = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await api.post('/auth/verify-code', { code })
      setUser(data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Verification failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6 relative">
        <button
          onClick={dismiss}
          aria-label="Close"
          className="absolute top-3 right-3 text-[var(--text-muted)] hover:text-white transition-colors text-xl leading-none px-2 py-1"
        >
          &times;
        </button>

        <h2 className="text-lg font-bold tracking-tight">Verify your email</h2>
        <p className="text-[var(--text-secondary)] text-sm mt-1">
          Your email <span className="text-[var(--text-primary)]">{user.email}</span> isn't
          verified yet. Verify it to keep your account secure.
        </p>

        {!sent ? (
          <button
            onClick={handleSend}
            className="mt-5 w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-medium h-10 rounded-lg transition-colors"
          >
            Send verification code
          </button>
        ) : (
          <form onSubmit={handleVerify} className="mt-5 space-y-3">
            <input
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              required
              placeholder="123456"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              className="w-full bg-[var(--bg)] border border-[rgba(255,255,255,0.10)] text-[var(--text-primary)] rounded-lg px-3 py-2 text-center text-xl tracking-[0.5em] focus:outline-none focus:ring-2 focus:ring-[#5E6AD2]/30 focus:border-[#5E6AD2]/60 transition-colors placeholder:text-[var(--text-muted)] placeholder:tracking-[0.5em]"
            />
            <button
              type="submit"
              disabled={loading || code.length !== 6}
              className="w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white font-medium h-10 rounded-lg transition-colors"
            >
              {loading ? 'Verifying...' : 'Verify'}
            </button>
            <p className="text-xs text-[var(--text-muted)] text-center">
              <button
                type="button"
                onClick={handleSend}
                disabled={cooldown > 0}
                className="text-[var(--accent)] hover:opacity-80 disabled:opacity-40 transition-opacity"
              >
                {cooldown > 0 ? `Resend (${cooldown}s)` : 'Resend code'}
              </button>
            </p>
          </form>
        )}

        {error && <p className="text-red-400 text-sm mt-3">{error}</p>}
        {info && !error && <p className="text-green-400 text-sm mt-3">{info}</p>}

        <button
          onClick={dismiss}
          className="mt-4 w-full text-sm text-[var(--text-muted)] hover:text-white transition-colors"
        >
          Maybe later
        </button>
      </div>
    </div>
  )
}
