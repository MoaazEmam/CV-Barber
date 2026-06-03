import { Link, Outlet, useNavigate } from 'react-router-dom'
import useAppStore from '../store/useAppStore'
import api from '../lib/axios'

export default function Layout() {
  const navigate = useNavigate()
  const user = useAppStore((s) => s.user)
  const token = useAppStore((s) => s.token)
  const clearAuth = useAppStore((s) => s.clearAuth)

  const handleSignOut = () => {
    api.post('/auth/logout').catch(() => {})
    clearAuth()
    navigate('/login')
  }

  return (
    <div className="bg-[var(--bg)] text-[var(--text-primary)] min-h-screen">
      <nav className="border-b border-[var(--border)] bg-[var(--bg)]">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="hover:opacity-80 transition-opacity">
            <span className="text-[15px] font-semibold tracking-tight">
              <span className="text-[var(--accent)] me-1">CV</span>Barber
            </span>
          </Link>

          <div className="flex items-center gap-6">
            {token && (
              <Link
                to="/history"
                className="text-sm text-[var(--text-secondary)] hover:text-white transition-colors"
              >
                History
              </Link>
            )}
            {token && user && (
              <div className="flex items-center gap-4">
                <span className="hidden sm:block text-sm text-[var(--text-muted)]">{user.username}</span>
                <button
                  onClick={handleSignOut}
                  className="text-sm text-[var(--text-secondary)] hover:text-white transition-colors"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-10">
        <Outlet />
      </main>
    </div>
  )
}
