import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'

// Landing page for the Google OAuth redirect. The backend puts the access
// token in the URL fragment (never sent to the server / logs); we scrub it,
// exchange it for a refresh cookie, load the user, and route onward.
export default function OAuthCallbackPage() {
  const navigate = useNavigate()
  const setAuth = useAppStore((s) => s.setAuth)
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current) return
    ran.current = true

    const token = new URLSearchParams(window.location.hash.slice(1)).get('token')
    window.history.replaceState(null, '', window.location.pathname)

    if (!token) {
      navigate('/login', { replace: true })
      return
    }

    const auth = { headers: { Authorization: `Bearer ${token}` } }
    ;(async () => {
      try {
        await api.post('/auth/cookie', null, auth)
        const meRes = await api.get('/users/me', auth)
        setAuth(meRes.data, token)
        navigate(meRes.data.username == null ? '/choose-username' : '/', { replace: true })
      } catch {
        navigate('/login', { replace: true })
      }
    })()
  }, [navigate, setAuth])

  return (
    <div className="min-h-[80vh] flex items-center justify-center">
      <p className="text-[var(--text-secondary)]">Signing you in...</p>
    </div>
  )
}
