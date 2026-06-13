import { useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'

const TECH_TOKEN_RE =
  /\b(python|java(script)?|typescript|react|node|sql|postgres|mysql|mongo|aws|azure|gcp|docker|kubernetes|k8s|api|rest|graphql|ci\/cd|git|linux|c\+\+|c#|golang|go|rust|php|ruby|django|flask|fastapi|spring|angular|vue|terraform|ansible|redis|kafka|spark|ml|machine learning|data|agile|scrum|html|css|excel|figma|swift|kotlin)\b/gi

// A JD is "thin" when it's short or names almost no concrete skills — the
// signal that fetching a fuller typical description would help.
function isThinJd(jd) {
  const text = jd.trim()
  if (!text) return false
  if (text.length < 600) return true
  const matches = text.match(TECH_TOKEN_RE)
  return new Set((matches || []).map((m) => m.toLowerCase())).size < 3
}

export default function TailorPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const prefill = location.state?.prefill

  const masterCvId = useAppStore((s) => s.masterCvId)
  const masterCvMeta = useAppStore((s) => s.masterCvMeta)
  const setTailoredResult = useAppStore((s) => s.setTailoredResult)

  const [jobTitle, setJobTitle] = useState(prefill?.jobTitle ?? '')
  const [companyName, setCompanyName] = useState(prefill?.companyName ?? '')
  const [jobDescription, setJobDescription] = useState(prefill?.jobDescription ?? '')
  const [topNExperience, setTopNExperience] = useState(prefill?.topNExperience ?? 3)
  const [topNProjects, setTopNProjects] = useState(prefill?.topNProjects ?? 3)
  const [rewriteSummary, setRewriteSummary] = useState(true)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // JD enrichment (web search) — only offered when the backend has a key.
  const [enrichEnabled, setEnrichEnabled] = useState(false)
  const [enriching, setEnriching] = useState(false)
  const [enrichError, setEnrichError] = useState('')
  const [enrichPreview, setEnrichPreview] = useState(null) // {supplement, sources}
  const [jdSupplement, setJdSupplement] = useState(null)
  const [enrichDismissed, setEnrichDismissed] = useState(false)

  useEffect(() => {
    api
      .get('/api/enrich-jd/enabled')
      .then((res) => setEnrichEnabled(Boolean(res.data?.enabled)))
      .catch(() => setEnrichEnabled(false))
  }, [])

  if (!masterCvId) return <Navigate to="/" replace />

  const showEnrichChip =
    enrichEnabled &&
    !enrichDismissed &&
    !jdSupplement &&
    !enrichPreview &&
    jobTitle.trim().length >= 2 &&
    isThinJd(jobDescription)

  const handleEnrich = async () => {
    setEnriching(true)
    setEnrichError('')
    try {
      const res = await api.post('/api/enrich-jd', {
        job_title: jobTitle.trim(),
        company_name: companyName.trim() || undefined,
      })
      setEnrichPreview(res.data)
    } catch (err) {
      const status = err.response?.status
      if (status === 429) {
        setEnrichError('Too many searches — try again in a minute.')
      } else {
        setEnrichError('Could not fetch a description for this role.')
      }
    } finally {
      setEnriching(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await api.post('/api/tailor', {
        session_id: masterCvId,
        job_title: jobTitle,
        company_name: companyName,
        job_description: jobDescription,
        jd_supplement: jdSupplement || undefined,
        top_n_experience: topNExperience,
        top_n_projects: topNProjects,
        rewrite_summary: rewriteSummary,
      })
      const id = res.data.tailored_session_id
      setTailoredResult(id, { ...res.data, job_description: jobDescription })
      navigate(`/results/${id}`)
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail
      if (status === 429) {
        const m = (detail || '').match(/(\d+)/)
        const sec = m ? m[1] : '60'
        setError(`Rate limit reached. Try again in ${sec} seconds.`)
      } else if (typeof detail === 'string') {
        setError(detail)
      } else {
        setError('Failed to tailor CV.')
      }
    } finally {
      setLoading(false)
    }
  }

  const inputClass =
    'w-full bg-[var(--bg)] border border-[rgba(255,255,255,0.10)] text-[var(--text-primary)] rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#5E6AD2]/30 focus:border-[#5E6AD2]/60 transition-colors placeholder:text-[var(--text-muted)]'
  const labelClass = 'block text-sm font-medium text-[var(--text-secondary)] mb-1.5'

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-4xl font-bold tracking-tight">Describe the role</h1>
        {masterCvMeta && (
          <p className="text-[var(--text-secondary)] mt-1 text-[15px]">
            Tailoring for {masterCvMeta.full_name}
          </p>
        )}
        {prefill && (
          <p className="text-[var(--accent)] text-sm mt-1">
            Pre-filled from a previous application — update the details and re-tailor.
          </p>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6 space-y-4"
      >
        <div>
          <label className={labelClass}>Job Title</label>
          <input
            type="text"
            required
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
            className={inputClass}
          />
        </div>

        <div>
          <label className={labelClass}>Company Name</label>
          <input
            type="text"
            required
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            className={inputClass}
          />
        </div>

        <div>
          <label className={labelClass}>Job Description</label>
          <textarea
            required
            rows={8}
            placeholder="Paste the full job description here"
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            className={inputClass}
          />

          {showEnrichChip && (
            <div className="mt-2 flex items-center justify-between gap-3 bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2">
              <p className="text-xs text-[var(--text-secondary)]">
                This job description looks short — fetch a fuller typical description for this role?
              </p>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={handleEnrich}
                  disabled={enriching}
                  className="text-xs text-[var(--accent)] hover:opacity-80 font-medium disabled:opacity-50"
                >
                  {enriching ? 'Searching…' : 'Enrich'}
                </button>
                <button
                  type="button"
                  onClick={() => setEnrichDismissed(true)}
                  className="text-xs text-[var(--text-muted)] hover:text-white"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}
          {enrichError && <p className="text-red-400 text-xs mt-2">{enrichError}</p>}

          {enrichPreview && (
            <div className="mt-2 bg-[var(--bg)] border border-[var(--border)] rounded-lg p-3 space-y-2">
              <p className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wide">
                Web-sourced supplement (preview)
              </p>
              <p className="text-sm text-[var(--text-primary)] whitespace-pre-wrap max-h-48 overflow-y-auto">
                {enrichPreview.supplement}
              </p>
              {enrichPreview.sources?.length > 0 && (
                <p className="text-xs text-[var(--text-muted)] truncate">
                  Sources:{' '}
                  {enrichPreview.sources.map((s, i) => (
                    <a
                      key={s.url}
                      href={s.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[var(--accent)] hover:opacity-80"
                    >
                      {i > 0 ? ', ' : ''}
                      {s.title || s.url}
                    </a>
                  ))}
                </p>
              )}
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setJdSupplement(enrichPreview.supplement)
                    setEnrichPreview(null)
                  }}
                  className="text-xs bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-medium px-3 py-1.5 rounded-lg transition-colors"
                >
                  Use this
                </button>
                <button
                  type="button"
                  onClick={() => setEnrichPreview(null)}
                  className="text-xs text-[var(--text-secondary)] hover:text-white px-3 py-1.5"
                >
                  Discard
                </button>
              </div>
            </div>
          )}

          {jdSupplement && (
            <div className="mt-2 flex items-center justify-between gap-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg px-3 py-2">
              <p className="text-xs text-emerald-400">
                Supplementary description attached — it will be used alongside your pasted JD.
              </p>
              <button
                type="button"
                onClick={() => setJdSupplement(null)}
                className="text-xs text-[var(--text-muted)] hover:text-white shrink-0"
              >
                Remove
              </button>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Max Experience Entries</label>
            <input
              type="number"
              min={1}
              max={50}
              value={topNExperience}
              onChange={(e) => setTopNExperience(parseInt(e.target.value || '1', 10))}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Max Projects</label>
            <input
              type="number"
              min={1}
              max={50}
              value={topNProjects}
              onChange={(e) => setTopNProjects(parseInt(e.target.value || '1', 10))}
              className={inputClass}
            />
          </div>
        </div>

        <label className="flex items-start gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={rewriteSummary}
            onChange={(e) => setRewriteSummary(e.target.checked)}
            className="mt-0.5"
          />
          <span className="text-sm text-[var(--text-secondary)]">
            Rewrite my summary for this job
            <span className="block text-xs text-[var(--text-muted)]">
              Experience &amp; projects are always reordered. Uncheck to keep your original summary.
            </span>
          </span>
        </label>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white font-medium h-11 rounded-lg transition-colors"
        >
          {loading ? 'Tailoring...' : 'Generate tailored CV'}
        </button>

        {error && <p className="text-red-400 text-sm">{error}</p>}
      </form>
    </div>
  )
}
