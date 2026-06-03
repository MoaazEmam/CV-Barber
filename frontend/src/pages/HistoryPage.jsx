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
  const [deleting, setDeleting] = useState(null)

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

  const handleDelete = async (e, appId) => {
    e.stopPropagation()
    if (!window.confirm('Delete this application? This cannot be undone.')) return
    setDeleting(appId)
    try {
      await api.delete(`/api/applications/${appId}`)
      setApplications((prev) => prev.filter((a) => a.id !== appId))
    } catch {
      setError('Failed to delete application.')
    } finally {
      setDeleting(null)
    }
  }

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
            <li
              key={app.id}
              className="flex items-stretch bg-[var(--surface)] border border-[var(--border)] rounded-xl overflow-hidden"
            >
              <button
                onClick={() => navigate(`/results/${app.id}`)}
                className="flex-1 text-left hover:bg-[var(--surface-raised)] p-5 transition-colors flex items-start justify-between gap-4"
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
              <button
                onClick={(e) => handleDelete(e, app.id)}
                disabled={deleting === app.id}
                className="px-4 text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/10 transition-colors border-l border-[var(--border)] disabled:opacity-40"
                title="Delete application"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                </svg>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
