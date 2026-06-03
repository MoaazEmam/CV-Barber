import { Navigate } from 'react-router-dom'
import useAppStore from '../store/useAppStore'

export default function ProtectedRoute({ children }) {
  const token = useAppStore((s) => s.token)
  const authReady = useAppStore((s) => s.authReady)
  if (!authReady) return null
  if (!token) return <Navigate to="/login" replace />
  return children
}
