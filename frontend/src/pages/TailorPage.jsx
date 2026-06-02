import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'

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
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (!masterCvId) return <Navigate to="/" replace />

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
        top_n_experience: topNExperience,
        top_n_projects: topNProjects,
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
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Max Experience Entries</label>
            <input
              type="number"
              min={1}
              max={10}
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
              max={10}
              value={topNProjects}
              onChange={(e) => setTopNProjects(parseInt(e.target.value || '1', 10))}
              className={inputClass}
            />
          </div>
        </div>

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
