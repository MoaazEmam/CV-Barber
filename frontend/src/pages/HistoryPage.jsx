import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/axios'

function scoreClasses(score) {
  if (score >= 7) return 'bg-emerald-500/15 text-emerald-400'
  if (score >= 4) return 'bg-amber-500/15 text-amber-400'
  return 'bg-red-500/15 text-red-400'
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

function GhostCard() {
  return (
    <div className="opacity-25 pointer-events-none border border-[var(--border)] rounded-xl p-5 flex items-start justify-between gap-4">
      <div className="space-y-2">
        <div className="h-4 w-44 bg-[var(--surface-raised)] rounded" />
        <div className="h-3 w-28 bg-[var(--surface-raised)] rounded" />
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <div className="w-8 h-8 rounded-full bg-[var(--surface-raised)]" />
        <div className="h-3 w-16 bg-[var(--surface-raised)] rounded" />
      </div>
    </div>
  )
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
          <h1 className="text-4xl font-bold tracking-tight text-[var(--text-primary)]">
            Application History
          </h1>
          <p className="text-[var(--text-secondary)] mt-1 text-[15px]">
            Your tailored CVs and job applications
          </p>
        </div>
        <button
          onClick={() => navigate('/')}
          className="bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-medium px-4 py-2 rounded-lg transition-colors whitespace-nowrap"
        >
          Upload new CV
        </button>
      </div>

      {loading && <p className="text-[var(--text-secondary)]">Loading...</p>}
      {error && <p className="text-red-400">{error}</p>}

      {!loading && !error && applications.length === 0 && (
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-8">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Your tailored applications will appear here
          </h2>
          <p className="text-[var(--text-secondary)] text-sm mt-1.5">
            Each one tracks relevance scores, ATS analysis, and your cover letter.
          </p>
          <div className="mt-5 space-y-2">
            <GhostCard />
            <GhostCard />
          </div>
          <button
            onClick={() => navigate('/')}
            className="mt-5 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-medium px-4 py-2 rounded-lg transition-colors"
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
                className="w-full text-left bg-[var(--surface)] hover:bg-[var(--surface-raised)] border border-[var(--border)] rounded-xl p-5 transition-colors flex items-start justify-between gap-4"
              >
                <div>
                  <p className="text-[var(--text-primary)] font-semibold">{app.job_title}</p>
                  <p className="text-[var(--text-secondary)] text-sm">{app.company_name}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  {app.job_match_score != null && (
                    <span
                      className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold ${scoreClasses(
                        app.job_match_score,
                      )}`}
                    >
                      {app.job_match_score}
                    </span>
                  )}
                  <span className="text-[var(--text-muted)] text-sm">{formatDate(app.created_at)}</span>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
