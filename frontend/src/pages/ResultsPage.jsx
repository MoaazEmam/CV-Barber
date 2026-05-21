import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'

function scoreClasses(score) {
  if (score >= 7) return 'bg-green-900 text-green-300'
  if (score >= 4) return 'bg-yellow-900 text-yellow-300'
  return 'bg-red-900 text-red-300'
}

function meterColor(score) {
  if (score == null) return 'text-slate-400'
  if (score >= 70) return 'text-green-400'
  if (score >= 40) return 'text-yellow-400'
  return 'text-red-400'
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

function ScoreMeter({ score, label }) {
  const display = score == null ? '--' : score
  const color = meterColor(score)
  return (
    <div className="flex flex-col items-center">
      <div className={`text-5xl font-bold ${color}`}>{display}</div>
      <div className="text-slate-500 text-xs mt-1 uppercase tracking-wide">{label}</div>
    </div>
  )
}

function SectionEditor({ masterCvId, applicationId, initialConfig }) {
  const [structure, setStructure] = useState(null)
  const [loading, setLoading] = useState(true)
  const [state, setState] = useState({}) // { sectionKey: { enabled, subs: { subKey: bool } } }
  const [saving, setSaving] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (!masterCvId) return
    let alive = true
    setLoading(true)
    api
      .get(`/api/cv/structure/${masterCvId}`)
      .then((res) => {
        if (!alive) return
        setStructure(res.data)
        const initState = {}
        for (const section of res.data.sections) {
          const cfg = initialConfig?.[section.key]
          initState[section.key] = {
            enabled: cfg?.enabled ?? true,
            subs: Object.fromEntries(
              section.subsections.map((s) => [
                s.key,
                cfg?.subsections?.[s.key] ?? true,
              ]),
            ),
          }
        }
        setState(initState)
      })
      .catch((err) => {
        console.error('Failed to load structure', err)
        if (alive) setErrorMsg('Failed to load sections')
      })
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [masterCvId])

  const toggleSection = (sectionKey, enabled) => {
    setState((prev) => {
      const next = { ...prev }
      const sub = { ...next[sectionKey].subs }
      if (!enabled) {
        for (const k of Object.keys(sub)) sub[k] = false
      }
      next[sectionKey] = { enabled, subs: sub }
      return next
    })
  }

  const toggleSub = (sectionKey, subKey, enabled) => {
    setState((prev) => {
      const next = { ...prev }
      const subs = { ...next[sectionKey].subs, [subKey]: enabled }
      const anyOn = Object.values(subs).some((v) => v)
      next[sectionKey] = {
        enabled: anyOn ? next[sectionKey].enabled : false,
        subs,
      }
      return next
    })
  }

  const save = async () => {
    setSaving(true)
    setErrorMsg('')
    setSuccessMsg('')
    try {
      const section_config = {}
      for (const [key, val] of Object.entries(state)) {
        section_config[key] = {
          enabled: val.enabled,
          subsections: val.subs,
        }
      }
      await api.patch(`/api/applications/${applicationId}/sections`, { section_config })
      setSuccessMsg('Sections saved')
      setTimeout(() => setSuccessMsg(''), 2000)
    } catch (err) {
      console.error('Save failed', err)
      setErrorMsg('Failed to save sections')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
      <h2 className="text-lg font-semibold text-white mb-4">CV Sections</h2>
      {loading ? (
        <div className="space-y-2">
          <div className="h-6 bg-slate-800 rounded animate-pulse" />
          <div className="h-6 bg-slate-800 rounded animate-pulse" />
          <div className="h-6 bg-slate-800 rounded animate-pulse" />
        </div>
      ) : !structure ? (
        <p className="text-slate-400 text-sm">No sections found.</p>
      ) : (
        <div className="space-y-4">
          {structure.sections.map((section) => {
            const s = state[section.key]
            if (!s) return null
            return (
              <div
                key={section.key}
                className={s.enabled ? '' : 'opacity-50'}
              >
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={s.enabled}
                    onChange={(e) => toggleSection(section.key, e.target.checked)}
                  />
                  <span className="text-white font-medium">{section.label}</span>
                </label>
                {section.subsections.length > 0 && (
                  <div className="ml-6 mt-2 space-y-1">
                    {section.subsections.map((sub) => (
                      <label
                        key={sub.key}
                        className="flex items-center gap-2 cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={s.subs[sub.key] ?? true}
                          disabled={!s.enabled}
                          onChange={(e) => toggleSub(section.key, sub.key, e.target.checked)}
                        />
                        <span className="text-slate-400 text-sm">{sub.label}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
          <button
            onClick={save}
            disabled={saving}
            className="w-full bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white font-medium px-4 py-2 rounded-lg transition"
          >
            {saving ? 'Saving...' : 'Save sections'}
          </button>
          {successMsg && <p className="text-green-400 text-sm">{successMsg}</p>}
          {errorMsg && <p className="text-red-400 text-sm">{errorMsg}</p>}
        </div>
      )}
    </div>
  )
}

function QAPanel({ applicationId }) {
  const [questions, setQuestions] = useState([''])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [answers, setAnswers] = useState([])
  const [copiedIdx, setCopiedIdx] = useState(null)
  const [history, setHistory] = useState([])

  useEffect(() => {
    let alive = true
    api
      .get(`/api/applications/${applicationId}/qa`)
      .then((res) => {
        if (!alive) return
        const items = res.data?.answers || []
        setHistory(items)
      })
      .catch((err) => {
        console.error('Failed to load QA history', err)
      })
    return () => {
      alive = false
    }
  }, [applicationId])

  const addQuestion = () => {
    if (questions.length < 10) setQuestions([...questions, ''])
  }
  const removeQuestion = (i) => {
    setQuestions(questions.filter((_, idx) => idx !== i))
  }
  const updateQuestion = (i, val) => {
    const next = [...questions]
    next[i] = val
    setQuestions(next)
  }

  const submit = async () => {
    setLoading(true)
    setError('')
    try {
      const filtered = questions.map((q) => q.trim()).filter((q) => q.length > 0)
      const res = await api.post(`/api/applications/${applicationId}/qa`, { questions: filtered })
      const newAnswers = res.data.answers || []
      setAnswers(newAnswers)
      setHistory((prev) => [...prev, ...newAnswers])
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || 'Failed to get answers')
    } finally {
      setLoading(false)
    }
  }

  const copy = async (text, i) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedIdx(i)
      setTimeout(() => setCopiedIdx(null), 1500)
    } catch (err) {
      console.error('Copy failed', err)
    }
  }

  const allEmpty = questions.every((q) => q.trim().length === 0)

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
      <h2 className="text-lg font-semibold text-white mb-1">Application Questions</h2>
      <p className="text-slate-400 text-sm mb-4">
        Paste questions from the application and get tailored answers
      </p>
      {history.length > 0 && (
        <div className="mb-6 space-y-3">
          <h3 className="text-xs uppercase tracking-wide text-slate-500">Previously answered</h3>
          {history.map((item, i) => (
            <div key={`h-${i}`} className="bg-slate-800 rounded-xl p-4">
              <p className="text-slate-200 text-sm font-medium mb-2">{item.question}</p>
              <p className="text-slate-300 leading-relaxed text-sm">{item.answer}</p>
              <button
                onClick={() => copy(item.answer, `h-${i}`)}
                className="mt-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs px-2 py-1 rounded"
              >
                {copiedIdx === `h-${i}` ? 'Copied!' : 'Copy'}
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="space-y-3">
        {questions.map((q, i) => (
          <div key={i} className="space-y-1">
            <div className="flex items-start gap-2">
              <textarea
                rows={3}
                value={q}
                onChange={(e) => updateQuestion(i, e.target.value)}
                placeholder="Paste a question..."
                className="flex-1 bg-slate-800 border border-slate-700 text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-indigo-500"
              />
              {questions.length > 1 && (
                <button
                  onClick={() => removeQuestion(i)}
                  className="text-slate-500 hover:text-red-400 px-2 py-1"
                  aria-label="Remove question"
                >
                  ×
                </button>
              )}
            </div>
            <div className="text-slate-500 text-xs">{q.length} chars</div>
            {answers[i] && (
              <div className="bg-slate-800 rounded-xl p-4 mt-2">
                <p className="text-slate-300 leading-relaxed text-sm">{answers[i].answer}</p>
                <button
                  onClick={() => copy(answers[i].answer, i)}
                  className="mt-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs px-2 py-1 rounded"
                >
                  {copiedIdx === i ? 'Copied!' : 'Copy'}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="flex gap-2 mt-3">
        <button
          onClick={addQuestion}
          disabled={questions.length >= 10}
          className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white text-sm px-3 py-1.5 rounded-lg"
        >
          Add question
        </button>
      </div>
      <button
        onClick={submit}
        disabled={allEmpty || loading}
        className="mt-4 w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium px-4 py-2 rounded-lg transition"
      >
        {loading ? 'Getting answers...' : 'Get answers'}
      </button>
      {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
    </div>
  )
}

function ATSPanel({ masterCvId, applicationId, initialGeneral, initialJob }) {
  const [general, setGeneral] = useState(initialGeneral)
  const [job, setJob] = useState(initialJob)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const rescore = async () => {
    setLoading(true)
    setError('')
    try {
      const [g, j] = await Promise.all([
        masterCvId ? api.post(`/api/cv/${masterCvId}/ats/general`) : Promise.resolve(null),
        api.post(`/api/applications/${applicationId}/ats/job`),
      ])
      if (g) setGeneral(g.data)
      setJob(j.data)
    } catch (err) {
      console.error(err)
      setError(err.response?.data?.detail || 'Failed to score. Try Re-score in a moment.')
    } finally {
      setLoading(false)
    }
  }

  // If we don't have a persisted score, compute on mount once. Otherwise show stored data.
  useEffect(() => {
    if (!general || !job) {
      rescore()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    setGeneral(initialGeneral)
    setJob(initialJob)
  }, [initialGeneral, initialJob])

  const allImprovements = useMemo(() => {
    const set = new Set()
    for (const s of general?.improvements || []) set.add(s)
    for (const s of job?.improvements || []) set.add(s)
    return Array.from(set)
  }, [general, job])

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">ATS Scores</h2>
        <button
          onClick={rescore}
          disabled={loading}
          className="bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded-lg"
        >
          {loading ? 'Scoring...' : 'Re-score'}
        </button>
      </div>

      {loading && !general && !job ? (
        <div className="space-y-2">
          <div className="h-24 bg-slate-800 rounded animate-pulse" />
          <div className="h-24 bg-slate-800 rounded animate-pulse" />
        </div>
      ) : error ? (
        <p className="text-red-400 text-sm">{error}</p>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-3">
              <ScoreMeter score={general?.score} label="General CV" />
              {general?.strengths?.length > 0 && (
                <div>
                  <h4 className="text-xs uppercase tracking-wide text-slate-500 mb-1">Strengths</h4>
                  <ul className="list-disc list-inside text-slate-300 text-sm space-y-1">
                    {general.strengths.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div className="space-y-3">
              <ScoreMeter score={job?.score} label="Job Match" />
              {job?.matched_keywords?.length > 0 && (
                <div>
                  <h4 className="text-xs uppercase tracking-wide text-slate-500 mb-1">Matched</h4>
                  <div className="flex flex-wrap gap-1">
                    {job.matched_keywords.map((k, i) => (
                      <span key={i} className="bg-green-900 text-green-300 rounded-full px-2 py-0.5 text-xs">
                        {k}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {job?.missing_keywords?.length > 0 && (
                <div>
                  <h4 className="text-xs uppercase tracking-wide text-slate-500 mb-1">Missing</h4>
                  <div className="flex flex-wrap gap-1">
                    {job.missing_keywords.map((k, i) => (
                      <span key={i} className="bg-red-900 text-red-300 rounded-full px-2 py-0.5 text-xs">
                        {k}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
          {allImprovements.length > 0 && (
            <div className="mt-6">
              <h4 className="text-xs uppercase tracking-wide text-slate-500 mb-2">Improvements</h4>
              <ul className="list-disc list-inside text-slate-400 text-sm space-y-1">
                {allImprovements.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function ResultsPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const currentApplicationId = useAppStore((s) => s.currentApplicationId)
  const tailoredResult = useAppStore((s) => s.tailoredResult)
  const resetCvFlow = useAppStore((s) => s.resetCvFlow)
  const masterCvId = useAppStore((s) => s.masterCvId)
  const setTailoredResult = useAppStore((s) => s.setTailoredResult)
  const setMasterCv = useAppStore((s) => s.setMasterCv)

  const [hydrating, setHydrating] = useState(false)
  const [hydrateError, setHydrateError] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewHtml, setPreviewHtml] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [showFullJd, setShowFullJd] = useState(false)
  const [sectionConfig, setSectionConfig] = useState(null)
  const [effectiveMasterCvId, setEffectiveMasterCvId] = useState(masterCvId)
  const [initialGeneral, setInitialGeneral] = useState(null)
  const [initialJob, setInitialJob] = useState(null)

  const hasResult = currentApplicationId === id && tailoredResult

  useEffect(() => {
    setPreviewOpen(false)
    setPreviewHtml('')
  }, [id])

  useEffect(() => {
    // Always hit the detail endpoint so we get persisted ATS scores + section_config
    // + master_cv_id, even when navigating from a fresh tailor. The store already has
    // a rendered tailored result if the user just tailored, so we don't block UI on
    // the fetch unless we have nothing to show.
    let alive = true
    if (!hasResult) {
      setHydrating(true)
    }
    setHydrateError('')
    api
      .get(`/api/applications/${id}`)
      .then((res) => {
        if (!alive) return
        const d = res.data
        const tcv = d.tailored_cv_data || {}
        const scores = [
          ...(tcv.experience || []).map((e) => ({
            name: e.title,
            type: 'experience',
            score: e.relevance_score,
            reason: e.relevance_reason,
          })),
          ...(tcv.projects || []).map((p) => ({
            name: p.name,
            type: 'project',
            score: p.relevance_score,
            reason: p.relevance_reason,
          })),
        ]
        const result = {
          tailored_session_id: d.id,
          job_title: d.job_title,
          company_name: d.company_name,
          job_description: d.job_description,
          full_name: tcv.full_name,
          tailored_summary: tcv.tailored_summary,
          scores,
          created_at: d.created_at,
        }
        setTailoredResult(d.id, result)
        setSectionConfig(d.section_config || null)
        setEffectiveMasterCvId(d.master_cv_id)
        if (d.general_ats_score != null) {
          setInitialGeneral({
            score: d.general_ats_score,
            strengths: d.ats_improvement_points?.strengths || [],
            improvements: d.ats_improvement_points?.improvements || [],
          })
        }
        if (d.job_match_score != null) {
          setInitialJob({
            score: d.job_match_score,
            matched_keywords: d.job_improvement_points?.matched_keywords || [],
            missing_keywords: d.job_improvement_points?.missing_keywords || [],
            improvements: d.job_improvement_points?.improvements || [],
          })
        }
        if (!masterCvId) {
          setMasterCv(d.master_cv_id, null)
        }
      })
      .catch((err) => {
        console.error(err)
        if (alive) setHydrateError('Could not load this application')
      })
      .finally(() => alive && setHydrating(false))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (hydrating) {
    return (
      <div className="max-w-2xl mx-auto bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center">
        <p className="text-slate-400">Loading application...</p>
      </div>
    )
  }

  if (!hasResult) {
    return (
      <div className="max-w-2xl mx-auto bg-slate-900 border border-slate-800 rounded-2xl p-8 text-center">
        <h2 className="text-xl font-semibold text-white">Result not found</h2>
        <p className="text-slate-400 mt-2 text-sm">
          {hydrateError || 'This application could not be loaded.'}
        </p>
        <button
          onClick={() => navigate('/history')}
          className="mt-4 bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-4 py-2 rounded-lg transition"
        >
          Go to history
        </button>
      </div>
    )
  }

  const r = tailoredResult
  const experiences = (r.scores || []).filter((s) => s.type === 'experience')
  const projects = (r.scores || []).filter((s) => s.type === 'project')

  const downloadFile = async (format) => {
    try {
      const res = await api.get(`/api/download/${id}?format=${format}`, {
        responseType: 'blob',
      })
      const disposition = res.headers['content-disposition'] || ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match ? match[1] : `cv.${format}`
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Download failed', err)
    }
  }

  const togglePreview = async () => {
    if (previewOpen) {
      setPreviewOpen(false)
      return
    }
    setPreviewOpen(true)
    if (!previewHtml) {
      setPreviewLoading(true)
      try {
        const res = await api.get(`/api/preview/${id}`)
        setPreviewHtml(res.data)
      } catch (err) {
        console.error('Preview failed', err)
      } finally {
        setPreviewLoading(false)
      }
    }
  }

  const tailorAnother = () => {
    const keepMasterId = masterCvId
    const keepMasterMeta = useAppStore.getState().masterCvMeta
    resetCvFlow()
    useAppStore.getState().setMasterCv(keepMasterId, keepMasterMeta)
    navigate('/tailor')
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white">
          {r.job_title} at {r.company_name}
        </h1>
        <p className="text-slate-400 mt-1">{formatDate(r.created_at || new Date())}</p>
      </div>

      {r.tailored_summary && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white mb-3">Tailored Summary</h2>
          <p className="text-slate-300 leading-relaxed">{r.tailored_summary}</p>
        </div>
      )}

      <ATSPanel
        masterCvId={effectiveMasterCvId}
        applicationId={id}
        initialGeneral={initialGeneral}
        initialJob={initialJob}
      />

      {r.job_description && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white mb-3">Job Description</h2>
          <div
            className={`text-slate-400 text-sm leading-relaxed whitespace-pre-wrap ${
              showFullJd ? '' : 'line-clamp-6'
            }`}
          >
            {r.job_description}
          </div>
          <button
            onClick={() => setShowFullJd((v) => !v)}
            className="mt-3 text-indigo-400 hover:text-indigo-300 text-sm"
          >
            {showFullJd ? 'Show less' : 'Show more'}
          </button>
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-6">
        <h2 className="text-lg font-semibold text-white">Relevance Scores</h2>

        {experiences.length > 0 && (
          <div>
            <h3 className="text-sm uppercase tracking-wide text-slate-500 mb-3">Experience</h3>
            <ul className="space-y-3">
              {experiences.map((e, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span
                    className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold ${scoreClasses(
                      e.score,
                    )}`}
                  >
                    {e.score}
                  </span>
                  <div>
                    <p className="text-white font-medium">{e.name}</p>
                    <p className="text-slate-400 text-sm">{e.reason}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {projects.length > 0 && (
          <div>
            <h3 className="text-sm uppercase tracking-wide text-slate-500 mb-3">Projects</h3>
            <ul className="space-y-3">
              {projects.map((p, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span
                    className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold ${scoreClasses(
                      p.score,
                    )}`}
                  >
                    {p.score}
                  </span>
                  <div>
                    <p className="text-white font-medium">{p.name}</p>
                    <p className="text-slate-400 text-sm">{p.reason}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {effectiveMasterCvId && (
        <SectionEditor
          masterCvId={effectiveMasterCvId}
          applicationId={id}
          initialConfig={sectionConfig}
        />
      )}

      <QAPanel applicationId={id} />

      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => downloadFile('docx')}
          className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-4 py-2 rounded-lg transition"
        >
          Download DOCX
        </button>
        <button
          onClick={() => downloadFile('pdf')}
          className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-4 py-2 rounded-lg transition"
        >
          Download PDF
        </button>
        <button
          onClick={togglePreview}
          className="bg-slate-800 hover:bg-slate-700 text-white font-medium px-4 py-2 rounded-lg transition"
        >
          {previewOpen ? 'Hide preview' : 'Preview CV'}
        </button>
        <button
          onClick={tailorAnother}
          className="bg-slate-800 hover:bg-slate-700 text-white font-medium px-4 py-2 rounded-lg transition"
        >
          Tailor another job
        </button>
      </div>

      {previewOpen && (
        <div className="bg-white rounded-2xl overflow-hidden">
          {previewLoading ? (
            <div className="p-6 text-slate-700">Loading preview...</div>
          ) : (
            <iframe
              title="CV Preview"
              srcDoc={previewHtml}
              className="w-full"
              style={{ height: '800px', border: 'none' }}
            />
          )}
        </div>
      )}
    </div>
  )
}
