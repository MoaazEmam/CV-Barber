import { useEffect } from 'react'
import axios from 'axios'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import UploadPage from './pages/UploadPage'
import TailorPage from './pages/TailorPage'
import ResultsPage from './pages/ResultsPage'
import HistoryPage from './pages/HistoryPage'
import useAppStore from './store/useAppStore'

export default function App() {
  useEffect(() => {
    const { token, setAuth, setAuthReady } = useAppStore.getState()
    if (token) { setAuthReady(true); return }
    axios
      .post('/auth/refresh', null, { withCredentials: true })
      .then(async (res) => {
        const newToken = res.data.access_token
        const meRes = await axios.get('/users/me', {
          headers: { Authorization: `Bearer ${newToken}` },
          withCredentials: true,
        })
        setAuth(meRes.data, newToken)
      })
      .catch(() => {})
      .finally(() => setAuthReady(true))
  }, [])

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/" element={
            <ProtectedRoute><UploadPage /></ProtectedRoute>
          } />
          <Route path="/tailor" element={
            <ProtectedRoute><TailorPage /></ProtectedRoute>
          } />
          <Route path="/results/:id" element={
            <ProtectedRoute><ResultsPage /></ProtectedRoute>
          } />
          <Route path="/history" element={
            <ProtectedRoute><HistoryPage /></ProtectedRoute>
          } />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
