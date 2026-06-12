import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import api from '../lib/axios'
import PasswordInput from '../components/PasswordInput'

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
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
      await api.post('/auth/reset-password', { token, password })
      navigate('/login', { state: { notice: 'Password updated — sign in with your new password.' } })
    } catch (err) {
      const detail = err?.response?.data?.detail
      if (detail === 'RESET_PASSWORD_BAD_TOKEN') {
        setError('This reset link is invalid or has expired. Please request a new one.')
      } else if (detail?.reason) {
        setError(detail.reason)
      } else if (err?.response?.status === 429) {
        setError('Too many attempts. Please wait a minute and try again.')
      } else {
        setError('Could not reset the password. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center">
        <div className="w-full max-w-md bg-[var(--surface)] border border-[var(--border)] rounded-xl p-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Invalid link</h1>
          <p className="text-[var(--text-secondary)] text-sm mt-2">
            This reset link is missing its token.
          </p>
          <p className="text-sm mt-6">
            <Link to="/forgot-password" className="text-[var(--accent)] hover:opacity-80 transition-opacity">
              Request a new reset link
            </Link>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <div className="w-full max-w-md">
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-8">
          <h1 className="text-2xl font-bold tracking-tight">Choose a new password</h1>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <PasswordInput
              label="New password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
            <PasswordInput
              label="Confirm new password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white font-medium h-11 rounded-lg transition-colors"
            >
              {loading ? 'Updating...' : 'Update password'}
            </button>
            {error && <p className="text-red-400 text-sm">{error}</p>}
          </form>
        </div>
      </div>
    </div>
  )
}
