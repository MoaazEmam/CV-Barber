import { useEffect, useState } from 'react'
import api from '../lib/axios'
import StatCard from '../components/admin/StatCard'
import BarChart from '../components/admin/BarChart'

const TYPE_BADGES = {
  suggestion: 'bg-sky-500/15 text-sky-400',
  bug: 'bg-red-500/15 text-red-400',
  other: 'bg-zinc-500/15 text-zinc-400',
}

function formatDate(d) {
  return new Date(d).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

// fill: lets the content stretch to the card's full height (cards in a grid
// row are equal-height, so a short chart would otherwise leave dead space).
function Section({ title, children, fill = false }) {
  return (
    <div className={`bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 ${fill ? 'flex flex-col' : ''}`}>
      <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wide mb-4">
        {title}
      </h2>
      {fill ? <div className="flex-1 min-h-0">{children}</div> : children}
    </div>
  )
}

export default function AdminPage() {
  const [metrics, setMetrics] = useState(null)
  const [feedback, setFeedback] = useState([])
  const [feedbackFilter, setFeedbackFilter] = useState('all')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const [m, fb] = await Promise.all([
          api.get('/api/admin/metrics'),
          api.get('/api/admin/feedback'),
        ])
        if (!cancelled) {
          setMetrics(m.data)
          setFeedback(fb.data)
        }
      } catch {
        if (!cancelled) setError('Failed to load admin data.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const toggleStatus = async (item) => {
    const newStatus = item.status === 'open' ? 'resolved' : 'open'
    try {
      const res = await api.patch(`/api/admin/feedback/${item.id}`, { status: newStatus })
      setFeedback((prev) => prev.map((f) => (f.id === item.id ? { ...f, ...res.data } : f)))
    } catch {
      setError('Failed to update feedback status.')
    }
  }

  if (loading) return <p className="text-[var(--text-secondary)]">Loading...</p>
  if (error && !metrics) return <p className="text-red-400">{error}</p>

  const visibleFeedback =
    feedbackFilter === 'all' ? feedback : feedback.filter((f) => f.status === feedbackFilter)
  const maxTemplate = Math.max(1, ...metrics.template_popularity.map((t) => t.count))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-4xl font-bold tracking-tight text-[var(--text-primary)]">Admin</h1>
        <p className="text-[var(--text-secondary)] mt-1 text-[15px]">
          Usage metrics and user feedback
        </p>
      </div>

      {error && <p className="text-red-400">{error}</p>}

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        <StatCard label="Users" value={metrics.total_users} hint={`${metrics.verified_users} verified · ${metrics.unverified_users} unverified`} />
        <StatCard label="Active users" value={metrics.active_users_7d} hint={`last 7 days · ${metrics.active_users_30d} in 30 days`} />
        <StatCard label="CVs uploaded" value={metrics.total_master_cvs} />
        <StatCard label="Applications" value={metrics.total_applications} hint={`${metrics.avg_applications_per_user} avg / user`} />
        <StatCard label="Cover letters" value={metrics.cover_letters_generated} />
        <StatCard label="Custom templates" value={metrics.custom_templates} />
        <StatCard label="Q&A sets" value={metrics.qa_sets} />
        <StatCard label="Open feedback" value={metrics.open_feedback_count} />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Signups — last 30 days">
          <BarChart
            data={metrics.signups_per_day.map((d) => ({ label: d.date, count: d.count }))}
            formatXLabel={(d) => d.slice(5)}
          />
        </Section>
        <Section title="Activity (CVs + applications) — last 30 days">
          <BarChart
            data={metrics.activity_per_day.map((d) => ({ label: d.date, count: d.count }))}
            formatXLabel={(d) => d.slice(5)}
          />
        </Section>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Section title="Peak hours (UTC) — last 30 days" fill>
          <BarChart
            fill
            data={metrics.peak_hours.map((h) => ({ label: `${String(h.hour).padStart(2, '0')}:00`, count: h.count }))}
          />
        </Section>
        <Section title="Template popularity">
          {metrics.template_popularity.length === 0 && (
            <p className="text-sm text-[var(--text-muted)]">No applications yet.</p>
          )}
          <div className="space-y-2">
            {metrics.template_popularity.map((t) => (
              <div key={t.label} className="flex items-center gap-3">
                <span className="text-sm text-[var(--text-secondary)] w-40 truncate" title={t.label}>
                  {t.label}
                </span>
                <div className="flex-1 h-3 bg-[var(--surface-raised)] rounded overflow-hidden">
                  <div
                    className="h-full bg-[var(--accent)] opacity-70 rounded"
                    style={{ width: `${(t.count / maxTemplate) * 100}%` }}
                  />
                </div>
                <span className="text-sm text-[var(--text-primary)] w-8 text-right">{t.count}</span>
              </div>
            ))}
          </div>
        </Section>
      </div>

      <Section title="Feedback">
        <div className="flex gap-2 mb-4">
          {['all', 'open', 'resolved'].map((f) => (
            <button
              key={f}
              onClick={() => setFeedbackFilter(f)}
              className={`text-sm px-3 py-1 rounded-lg border transition-colors ${
                feedbackFilter === f
                  ? 'border-[var(--accent)] text-[var(--text-primary)]'
                  : 'border-[var(--border)] text-[var(--text-secondary)] hover:text-white'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
        {visibleFeedback.length === 0 && (
          <p className="text-sm text-[var(--text-muted)]">No feedback yet.</p>
        )}
        <ul className="space-y-3">
          {visibleFeedback.map((item) => (
            <li
              key={item.id}
              className="border border-[var(--border)] rounded-xl p-4 flex items-start justify-between gap-4"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_BADGES[item.type] || TYPE_BADGES.other}`}>
                    {item.type}
                  </span>
                  <span className="text-sm text-[var(--text-secondary)]">
                    {item.username || item.user_email}
                  </span>
                  {item.page_context && (
                    <span className="text-xs text-[var(--text-muted)]">on {item.page_context}</span>
                  )}
                  <span className="text-xs text-[var(--text-muted)]">{formatDate(item.created_at)}</span>
                </div>
                <p className="text-[var(--text-primary)] text-sm mt-2 whitespace-pre-wrap break-words">
                  {item.message}
                </p>
              </div>
              <button
                onClick={() => toggleStatus(item)}
                className={`shrink-0 text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                  item.status === 'open'
                    ? 'border-[var(--border)] text-[var(--text-secondary)] hover:text-emerald-400 hover:border-emerald-500/40'
                    : 'border-emerald-500/40 text-emerald-400 hover:opacity-80'
                }`}
              >
                {item.status === 'open' ? 'Mark resolved' : 'Resolved ✓'}
              </button>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  )
}
