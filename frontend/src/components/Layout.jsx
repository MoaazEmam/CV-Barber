import { Link, Outlet, useNavigate } from 'react-router-dom'
import useAppStore from '../store/useAppStore'

export default function Layout() {
  const navigate = useNavigate()
  const user = useAppStore((s) => s.user)
  const token = useAppStore((s) => s.token)
  const clearAuth = useAppStore((s) => s.clearAuth)

  const handleSignOut = () => {
    clearAuth()
    navigate('/login')
  }

  return (
    <div className="bg-slate-950 text-white min-h-screen">
      <nav className="border-b border-slate-800 bg-slate-950">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="text-xl font-bold text-white">
            CV Barber
          </Link>

          <div className="flex items-center gap-4">
            {token && (
              <Link
                to="/history"
                className="text-sm text-slate-300 hover:text-white transition"
              >
                History
              </Link>
            )}
            {token && user && (
              <div className="flex items-center gap-3">
                <span className="text-sm text-slate-300">{user.username}</span>
                <button
                  onClick={handleSignOut}
                  className="text-sm bg-slate-800 hover:bg-slate-700 text-white px-3 py-1.5 rounded-lg transition"
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
