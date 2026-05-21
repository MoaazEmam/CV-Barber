import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/axios'

function scoreClasses(score) {
  if (score >= 7) return 'bg-green-900 text-green-300'
  if (score >= 4) return 'bg-yellow-900 text-yellow-300'
  return 'bg-red-900 text-red-300'
}

function formatDate(d) {
  if (!d) return ''
  const dt = new Date(d)
  return dt.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const res = await api.get('/api/history')
        if (!cancelled) setApplications(res.data.applications)
      } catch (err) {
        if (!cancelled) setError('Failed to load history.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Application History</h1>
          <p className="text-slate-400 mt-1">Your tailored CVs and job applications</p>
        </div>
        <button
          onClick={() => navigate('/')}
          className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-4 py-2 rounded-lg transition whitespace-nowrap"
        >
          Upload new CV
        </button>
      </div>

      {loading && <p className="text-slate-400">Loading...</p>}
      {error && <p className="text-red-400">{error}</p>}

      {!loading && !error && applications.length === 0 && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center">
          <h2 className="text-xl font-semibold text-white">No applications yet</h2>
          <button
            onClick={() => navigate('/')}
            className="mt-4 bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-4 py-2 rounded-lg transition"
          >
            Tailor your first CV
          </button>
        </div>
      )}

      {!loading && applications.length > 0 && (
        <ul className="space-y-3">
          {applications.map((app) => (
            <li key={app.id}>
              <button
                onClick={() => navigate(`/results/${app.id}`)}
                className="w-full text-left bg-slate-900 hover:bg-slate-900/60 border border-slate-800 rounded-xl p-5 transition flex items-start justify-between gap-4"
              >
                <div>
                  <p className="text-white font-semibold">{app.job_title}</p>
                  <p className="text-slate-400 text-sm">{app.company_name}</p>
                </div>
                <div className="flex items-center gap-3">
                  {app.job_match_score != null && (
                    <span
                      className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold ${scoreClasses(
                        app.job_match_score,
                      )}`}
                    >
                      {app.job_match_score}
                    </span>
                  )}
                  <span className="text-slate-500 text-sm">{formatDate(app.created_at)}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
