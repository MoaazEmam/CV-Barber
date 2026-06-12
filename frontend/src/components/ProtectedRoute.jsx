import { Navigate } from 'react-router-dom'
import useAppStore from '../store/useAppStore'

export default function ProtectedRoute({ children }) {
  const token = useAppStore((s) => s.token)
  const user = useAppStore((s) => s.user)
  const authReady = useAppStore((s) => s.authReady)
  if (!authReady) return null
  if (!token) return <Navigate to="/login" replace />
  // Fresh signups are hard-gated until they verify (flag set by RegisterPage,
  // cleared by VerifyEmailPage). Pre-existing unverified accounts don't have
  // the flag and only see the dismissible modal.
  if (user && !user.is_verified && sessionStorage.getItem('postRegister')) {
    return <Navigate to="/verify-email" replace />
  }
  // First Google sign-in: must pick a username before using the app.
  if (user && user.username == null) {
    return <Navigate to="/choose-username" replace />
  }
  return children
}
