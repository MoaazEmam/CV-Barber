import axios from 'axios'
import useAppStore from '../store/useAppStore'

// withCredentials so the httpOnly refresh_token cookie is sent on /auth/* and
// stored from the /auth/login response.
const api = axios.create({ withCredentials: true })

api.interceptors.request.use((config) => {
  const token = useAppStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Dedupe concurrent refreshes: many requests may 401 at once when the access
// token expires; they should all wait on a single /auth/refresh call.
let refreshPromise = null

function isAuthEndpoint(url = '') {
  return (
    url.includes('/auth/login') ||
    url.includes('/auth/refresh') ||
    url.includes('/auth/jwt/login')
  )
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const status = error.response?.status

    if (
      status === 401 &&
      original &&
      !original._retry &&
      !isAuthEndpoint(original.url) &&
      useAppStore.getState().token
    ) {
      original._retry = true
      try {
        // Bare axios (not `api`) so this call skips the interceptors below.
        refreshPromise =
          refreshPromise ||
          axios.post('/auth/refresh', null, { withCredentials: true })
        const res = await refreshPromise
        refreshPromise = null

        const newToken = res.data.access_token
        useAppStore.getState().setToken(newToken)
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original)
      } catch (refreshErr) {
        refreshPromise = null
        useAppStore.getState().clearAuth()
        window.location.href = '/login'
        return Promise.reject(refreshErr)
      }
    }

    if (status === 401) {
      useAppStore.getState().clearAuth()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
