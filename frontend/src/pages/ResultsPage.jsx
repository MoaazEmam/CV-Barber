import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'
import ConfirmDialog from '../components/ConfirmDialog'

function scoreClasses(score) {
  if (score >= 7) return 'bg-emerald-500/15 text-emerald-400'
  if (score >= 4) return 'bg-amber-500/15 text-amber-400'
  return 'bg-red-500/15 text-red-400'
}

function meterColor(score) {
  if (score == null) return 'text-[var(--text-muted)]'
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
      <div className="text-[var(--text-muted)] text-xs mt-1 uppercase tracking-wide">{label}</div>
    </div>
  )
}

function SectionEditor({ applicationId, initialConfig, onSaved }) {
  const [structure, setStructure] = useState(null)
  const [loading, setLoading] = useState(true)
  const [state, setState] = useState({})
  const [saving, setSaving] = useState(false)
  const [successMsg, setSuccessMsg] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  useEffect(() => {
    if (!applicationId) return
    let alive = true
    setLoading(true)
    api
      .get(`/api/applications/${applicationId}/structure`)
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
  }, [applicationId])

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
      onSaved?.()
    } catch (err) {
      console.error('Save failed', err)
      setErrorMsg('Failed to save sections')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-4">CV Sections</h2>
      {loading ? (
        <div className="space-y-2">
          <div className="h-6 bg-[var(--surface-raised)] rounded animate-pulse" />
          <div className="h-6 bg-[var(--surface-raised)] rounded animate-pulse" />
          <div className="h-6 bg-[var(--surface-raised)] rounded animate-pulse" />
        </div>
      ) : !structure ? (
        <p className="text-[var(--text-secondary)] text-sm">No sections found.</p>
      ) : (
        <div className="space-y-4">
          {structure.sections.map((section) => {
            const s = state[section.key]
            if (!s) return null
            return (
              <div key={section.key} className={s.enabled ? '' : 'opacity-50'}>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={s.enabled}
                    onChange={(e) => toggleSection(section.key, e.target.checked)}
                  />
                  <span className="font-medium">{section.label}</span>
                </label>
                {section.subsections.length > 0 && (
                  <div className="ml-6 mt-2 space-y-1">
                    {section.subsections.map((sub) => (
                      <label key={sub.key} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={s.subs[sub.key] ?? true}
                          disabled={!s.enabled}
                          onChange={(e) => toggleSub(section.key, sub.key, e.target.checked)}
                        />
                        <span className="text-[var(--text-secondary)] text-sm">{sub.label}</span>
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
            className="w-full bg-[var(--surface-raised)] hover:bg-[rgba(255,255,255,0.08)] disabled:opacity-50 font-medium px-4 py-2 rounded-lg transition-colors"
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
        setHistory(res.data?.answers || [])
      })
      .catch((err) => console.error('Failed to load QA history', err))
    return () => { alive = false }
  }, [applicationId])

  const addQuestion = () => { if (questions.length < 10) setQuestions([...questions, '']) }
  const removeQuestion = (i) => { setQuestions(questions.filter((_, idx) => idx !== i)) }
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
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-1">Application Questions</h2>
      <p className="text-[var(--text-secondary)] text-sm mb-4">
        Paste questions from the application and get tailored answers
      </p>
      {history.length > 0 && (
        <div className="mb-6 space-y-3">
          <h3 className="text-xs uppercase tracking-wide text-[var(--text-muted)]">Previously answered</h3>
          {history.map((item, i) => (
            <div key={`h-${i}`} className="bg-[var(--surface-raised)] rounded-xl p-4">
              <p className="text-[var(--text-primary)] text-sm font-medium mb-2">{item.question}</p>
              <p className="text-[var(--text-secondary)] leading-relaxed text-sm">{item.answer}</p>
              <button
                onClick={() => copy(item.answer, `h-${i}`)}
                className="mt-2 bg-[var(--bg)] hover:bg-[rgba(255,255,255,0.05)] text-[var(--text-secondary)] text-xs px-2 py-1 rounded border border-[var(--border)]"
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
                className="flex-1 bg-[var(--bg)] border border-[rgba(255,255,255,0.10)] text-[var(--text-primary)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#5E6AD2]/30 focus:border-[#5E6AD2]/60 transition-colors placeholder:text-[var(--text-muted)]"
              />
              {questions.length > 1 && (
                <button
                  onClick={() => removeQuestion(i)}
                  className="text-[var(--text-muted)] hover:text-red-400 px-2 py-1 transition-colors"
                  aria-label="Remove question"
                >
                  ×
                </button>
              )}
            </div>
            <div className="text-[var(--text-muted)] text-xs">{q.length} chars</div>
            {answers[i] && (
              <div className="bg-[var(--surface-raised)] rounded-xl p-4 mt-2">
                <p className="text-[var(--text-secondary)] leading-relaxed text-sm">{answers[i].answer}</p>
                <button
                  onClick={() => copy(answers[i].answer, i)}
                  className="mt-2 bg-[var(--bg)] hover:bg-[rgba(255,255,255,0.05)] text-[var(--text-secondary)] text-xs px-2 py-1 rounded border border-[var(--border)]"
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
          className="bg-[var(--surface-raised)] hover:bg-[rgba(255,255,255,0.08)] disabled:opacity-50 text-[var(--text-secondary)] text-sm px-3 py-1.5 rounded-lg transition-colors"
        >
          Add question
        </button>
      </div>
      <button
        onClick={submit}
        disabled={allEmpty || loading}
        className="mt-4 w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white font-medium h-11 rounded-lg transition-colors"
      >
        {loading ? 'Getting answers...' : 'Get answers'}
      </button>
      {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
    </div>
  )
}

function CoverLetterPanel({ applicationId, initialCoverLetter }) {
  const [letter, setLetter] = useState(initialCoverLetter)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => { setLetter(initialCoverLetter) }, [initialCoverLetter])

  const generate = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.post(`/api/applications/${applicationId}/cover-letter`)
      setLetter(res.data.cover_letter)
    } catch (err) {
      const status = err.response?.status
      const detail = err.response?.data?.detail
      if (status === 429) {
        const m = (detail || '').match(/(\d+)/)
        const sec = m ? m[1] : '60'
        setError(`Rate limit reached. Try again in ${sec} seconds.`)
      } else if (status === 503) {
        setError('Daily usage limit reached. The service resets at midnight.')
      } else {
        setError(typeof detail === 'string' ? detail : 'Failed to generate cover letter.')
      }
    } finally {
      setLoading(false)
    }
  }

  const downloadCoverLetter = async (format) => {
    try {
      const res = await api.get(
        `/api/applications/${applicationId}/cover-letter/download?format=${format}`,
        { responseType: 'blob' },
      )
      const disposition = res.headers['content-disposition'] || ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match ? match[1] : `cover_letter.${format}`
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Cover letter download failed', err)
    }
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(letter)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch (err) {
      console.error('Copy failed', err)
    }
  }

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-1">Cover Letter</h2>
      <p className="text-[var(--text-secondary)] text-sm mb-4">
        Generate a tailored cover letter for this application
      </p>

      {!letter ? (
        <button
          onClick={generate}
          disabled={loading}
          className="w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white font-medium h-11 rounded-lg transition-colors"
        >
          {loading ? 'Generating...' : 'Generate Cover Letter'}
        </button>
      ) : (
        <div className="space-y-4">
          <div className="bg-[var(--surface-raised)] rounded-xl p-4">
            <p className="text-[var(--text-secondary)] leading-relaxed whitespace-pre-wrap text-sm">{letter}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={copy}
              className="bg-[var(--surface-raised)] hover:bg-[rgba(255,255,255,0.08)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm px-3 py-1.5 rounded-lg transition-colors"
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
            {['txt', 'docx', 'pdf'].map((fmt) => (
              <button
                key={fmt}
                onClick={() => downloadCoverLetter(fmt)}
                className="bg-[var(--surface-raised)] hover:bg-[rgba(255,255,255,0.08)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] text-sm px-3 py-1.5 rounded-lg transition-colors"
              >
                Download {fmt.toUpperCase()}
              </button>
            ))}
            <button
              onClick={generate}
              disabled={loading}
              className="bg-[var(--surface-raised)] hover:bg-[rgba(255,255,255,0.08)] disabled:opacity-50 border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text-secondary)] text-sm px-3 py-1.5 rounded-lg transition-colors"
            >
              {loading ? 'Regenerating...' : 'Regenerate'}
            </button>
          </div>
        </div>
      )}

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

  useEffect(() => {
    if (!general || !job) rescore()
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
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">ATS Scores</h2>
        <button
          onClick={rescore}
          disabled={loading}
          className="bg-[var(--surface-raised)] hover:bg-[rgba(255,255,255,0.08)] disabled:opacity-50 text-[var(--text-secondary)] text-xs px-3 py-1.5 rounded-lg transition-colors"
        >
          {loading ? 'Scoring...' : 'Re-score'}
        </button>
      </div>

      {loading && !general && !job ? (
        <div className="space-y-2">
          <div className="h-24 bg-[var(--surface-raised)] rounded animate-pulse" />
          <div className="h-24 bg-[var(--surface-raised)] rounded animate-pulse" />
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
                  <h4 className="text-xs uppercase tracking-wide text-[var(--text-muted)] mb-1">Strengths</h4>
                  <ul className="list-disc list-inside text-[var(--text-secondary)] text-sm space-y-1">
                    {general.strengths.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}
            </div>
            <div className="space-y-3">
              <ScoreMeter score={job?.score} label="Job Match" />
              {job?.matched_keywords?.length > 0 && (
                <div>
                  <h4 className="text-xs uppercase tracking-wide text-[var(--text-muted)] mb-1">Matched</h4>
                  <div className="flex flex-wrap gap-1">
                    {job.matched_keywords.map((k, i) => (
                      <span key={i} className="bg-emerald-500/15 text-emerald-400 rounded-full px-2 py-0.5 text-xs">
                        {k}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {job?.missing_keywords?.length > 0 && (
                <div>
                  <h4 className="text-xs uppercase tracking-wide text-[var(--text-muted)] mb-1">Missing</h4>
                  <div className="flex flex-wrap gap-1">
                    {job.missing_keywords.map((k, i) => (
                      <span key={i} className="bg-red-500/15 text-red-400 rounded-full px-2 py-0.5 text-xs">
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
              <h4 className="text-xs uppercase tracking-wide text-[var(--text-muted)] mb-2">Improvements</h4>
              <ul className="list-disc list-inside text-[var(--text-secondary)] text-sm space-y-1">
                {allImprovements.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function TemplatePanel({ applicationId, onSelect }) {
  const [options, setOptions] = useState([])
  const [selected, setSelected] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [pendingDelete, setPendingDelete] = useState(null)
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [note, setNote] = useState('')

  const load = async (notify = true) => {
    setLoading(true)
    setError('')
    try {
      const res = await api.get(`/api/applications/${applicationId}/template-options`)
      const opts = res.data.options || []
      setOptions(opts)
      setSelected(res.data.selected)
      if (notify) onSelect?.(opts.find((o) => o.id === res.data.selected) || null)
      return res.data
    } catch (err) {
      console.error('Failed to load templates', err)
      setError('Failed to load templates')
      return null
    } finally {
      setLoading(false)
    }
  }

  const removeTemplate = async (opt) => {
    setPendingDelete(null)
    setDeleting(true)
    setError('')
    try {
      const uuid = opt.template_id || opt.id.replace(/^custom:/, '')
      await api.delete(`/api/templates/${uuid}`)
      // Reload options; if the deleted template was the selected one it's now gone,
      // so fall back to a safe default (first built-in / keep-original) and persist it.
      const data = await load(false)
      if (data) {
        const opts = data.options || []
        if (!opts.some((o) => o.id === data.selected)) {
          const fallback = opts.find((o) => o.kind !== 'custom') || opts[0]
          if (fallback) await choose(fallback)
        }
      }
    } catch (err) {
      console.error('Delete template failed', err)
      setError(err.response?.data?.detail || 'Failed to delete template')
    } finally {
      setDeleting(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applicationId])

  const choose = async (opt) => {
    if (busy || opt.id === selected) return
    setBusy(true)
    setError('')
    try {
      await api.patch(`/api/applications/${applicationId}/template`, { template_id: opt.id })
      setSelected(opt.id)
      onSelect?.(opt)
    } catch (err) {
      console.error('Set template failed', err)
      setError(err.response?.data?.detail || 'Failed to set template')
    } finally {
      setBusy(false)
    }
  }

  const upload = async (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setBusy(true)
    setError('')
    setWarning('')
    setNote('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await api.post('/api/templates', fd)
      setWarning(res.data?.warning || '')
      setNote(res.data?.note || '')
      await load(false)
      await choose({ id: res.data.id, name: res.data.name, output: 'pdf', kind: 'custom' })
    } catch (err) {
      console.error('Template upload failed', err)
      setError(err.response?.data?.detail || 'Upload failed. Use a .html or .tex file.')
    } finally {
      setBusy(false)
    }
  }

  const downloadExample = async (fmt) => {
    try {
      const res = await api.get(`/api/templates/example?format=${fmt}`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `cv_example.${fmt}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error('Example download failed', err)
    }
  }

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6">
      <h2 className="text-lg font-semibold mb-1">Template</h2>
      <p className="text-[var(--text-secondary)] text-sm mb-4">
        Choose how your tailored CV looks — preview and download update to match.
      </p>
      {loading ? (
        <div className="grid grid-cols-2 gap-2">
          <div className="h-12 bg-[var(--surface-raised)] rounded animate-pulse" />
          <div className="h-12 bg-[var(--surface-raised)] rounded animate-pulse" />
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {options.map((opt) => (
              <div key={opt.id} className="relative">
                <button
                  onClick={() => choose(opt)}
                  disabled={busy || deleting}
                  className={`w-full text-left rounded-lg border px-3 py-2 transition-colors disabled:opacity-60 ${
                    opt.kind === 'custom' ? 'pr-8' : ''
                  } ${
                    opt.id === selected
                      ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                      : 'border-[var(--border)] hover:bg-[var(--surface-raised)]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{opt.name}</span>
                    <span className="text-[10px] uppercase tracking-wide text-[var(--text-muted)]">
                      {opt.output}
                    </span>
                  </div>
                  {opt.description && (
                    <p className="text-[var(--text-secondary)] text-xs mt-0.5">{opt.description}</p>
                  )}
                </button>
                {opt.kind === 'custom' && (
                  <button
                    type="button"
                    onClick={() => setPendingDelete(opt)}
                    disabled={busy || deleting}
                    title="Delete template"
                    aria-label={`Delete ${opt.name}`}
                    className="absolute top-1.5 right-1.5 w-5 h-5 flex items-center justify-center rounded text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/15 transition-colors disabled:opacity-60"
                  >
                    ×
                  </button>
                )}
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2">
            <button
              type="button"
              aria-disabled="true"
              onClick={(e) => e.preventDefault()}
              title="Custom template uploads are coming soon — we're putting the finishing touches on them!"
              className="inline-flex items-center gap-2 bg-[var(--surface-raised)] text-[var(--text-muted)] text-sm px-3 py-1.5 rounded-lg opacity-60 cursor-not-allowed"
            >
              Upload your own (coming soon)
            </button>
            {/* Hidden until custom template uploads are re-enabled — restore to bring back the example downloads.
            <span className="text-xs text-[var(--text-muted)]">
              New here? Start from an example:
              <button onClick={() => downloadExample('tex')} className="ml-1 text-[var(--accent)] hover:underline">.tex</button>
              <span className="mx-0.5">·</span>
              <button onClick={() => downloadExample('html')} className="text-[var(--accent)] hover:underline">.html</button>
            </span>
            */}
          </div>
        </>
      )}
      {note && <p className="text-emerald-400 text-sm mt-2">{note}</p>}
      {warning && <p className="text-amber-400 text-sm mt-2">{warning}</p>}
      {error && <p className="text-red-400 text-sm mt-2">{error}</p>}
      <ConfirmDialog
        open={!!pendingDelete}
        title="Delete template?"
        message={pendingDelete ? `"${pendingDelete.name}" will be removed from your templates. This can't be undone.` : ''}
        confirmLabel="Delete"
        onConfirm={() => removeTemplate(pendingDelete)}
        onCancel={() => setPendingDelete(null)}
      />
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
  const [previewPdfUrl, setPreviewPdfUrl] = useState('')
  const [previewError, setPreviewError] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const [selectedTemplate, setSelectedTemplate] = useState(null)
  const [showFullJd, setShowFullJd] = useState(false)
  const [sectionConfig, setSectionConfig] = useState(null)
  const [effectiveMasterCvId, setEffectiveMasterCvId] = useState(masterCvId)
  const [initialGeneral, setInitialGeneral] = useState(null)
  const [initialJob, setInitialJob] = useState(null)
  const [initialCoverLetter, setInitialCoverLetter] = useState(null)

  const hasResult = currentApplicationId === id && tailoredResult

  useEffect(() => {
    setPreviewOpen(false)
    setPreviewError('')
    setPreviewPdfUrl((old) => {
      if (old) URL.revokeObjectURL(old)
      return ''
    })
  }, [id])

  useEffect(() => {
    let alive = true
    if (!hasResult) setHydrating(true)
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
        setTailoredResult(d.id, {
          tailored_session_id: d.id,
          job_title: d.job_title,
          company_name: d.company_name,
          job_description: d.job_description,
          full_name: tcv.full_name,
          tailored_summary: tcv.tailored_summary,
          scores,
          created_at: d.created_at,
        })
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
        setInitialCoverLetter(d.cover_letter || null)
        if (!masterCvId) setMasterCv(d.master_cv_id, null)
      })
      .catch((err) => {
        console.error(err)
        if (alive) setHydrateError('Could not load this application')
      })
      .finally(() => alive && setHydrating(false))
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  if (hydrating) {
    return (
      <div className="max-w-2xl mx-auto bg-[var(--surface)] border border-[var(--border)] rounded-xl p-8 text-center">
        <p className="text-[var(--text-secondary)]">Loading application...</p>
      </div>
    )
  }

  if (!hasResult) {
    return (
      <div className="max-w-2xl mx-auto bg-[var(--surface)] border border-[var(--border)] rounded-xl p-8 text-center">
        <h2 className="text-xl font-semibold">Result not found</h2>
        <p className="text-[var(--text-secondary)] mt-2 text-sm">
          {hydrateError || 'This application could not be loaded.'}
        </p>
        <button
          onClick={() => navigate('/history')}
          className="mt-4 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-medium px-4 py-2 rounded-lg transition-colors"
        >
          Go to history
        </button>
      </div>
    )
  }

  const r = tailoredResult
  const experiences = (r.scores || []).filter((s) => s.type === 'experience')
  const projects = (r.scores || []).filter((s) => s.type === 'project')

  const downloadFile = async () => {
    try {
      const res = await api.get(`/api/download/${id}`, { responseType: 'blob' })
      const disposition = res.headers['content-disposition'] || ''
      const match = disposition.match(/filename="?([^"]+)"?/)
      const filename = match ? match[1] : 'cv'
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

  const fetchPreview = async () => {
    setPreviewLoading(true)
    setPreviewError('')
    try {
      const res = await api.get(`/api/preview/${id}`, { responseType: 'blob' })
      const ct = res.headers['content-type'] || ''
      if (ct.includes('application/pdf')) {
        // Wrap in a typed Blob so the browser renders it inline in the iframe.
        const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
        setPreviewPdfUrl((old) => {
          if (old) URL.revokeObjectURL(old)
          return url
        })
      } else {
        // JSON marker: preview not available (e.g. DOCX "keep original").
        setPreviewPdfUrl((old) => {
          if (old) URL.revokeObjectURL(old)
          return ''
        })
        setPreviewError('Preview isn’t available for DOCX — download it to view.')
      }
    } catch (err) {
      console.error('Preview failed', err)
      setPreviewError('Failed to load preview.')
    } finally {
      setPreviewLoading(false)
    }
  }

  const togglePreview = async () => {
    if (previewOpen) { setPreviewOpen(false); return }
    setPreviewOpen(true)
    if (selectedTemplate?.output === 'docx') {
      setPreviewPdfUrl('')
      setPreviewError('Preview isn’t available for DOCX — download it to view.')
      return
    }
    await fetchPreview()
  }

  const handleTemplateSelected = async (opt) => {
    setSelectedTemplate(opt)
    if (!previewOpen) return
    if (opt?.output === 'docx') {
      setPreviewPdfUrl('')
      setPreviewError('Preview isn’t available for DOCX — download it to view.')
    } else {
      await fetchPreview()
    }
  }

  const handleSectionsSaved = async () => {
    if (previewOpen && selectedTemplate?.output !== 'docx') await fetchPreview()
  }

  const tailorAnother = () => {
    const keepMasterId = masterCvId
    const keepMasterMeta = useAppStore.getState().masterCvMeta
    resetCvFlow()
    useAppStore.getState().setMasterCv(keepMasterId, keepMasterMeta)
    navigate('/tailor')
  }

  const changeJobDetails = () => {
    navigate('/tailor', {
      state: {
        prefill: {
          jobTitle: r.job_title,
          companyName: r.company_name,
          jobDescription: r.job_description || '',
          topNExperience: experiences.length || 3,
          topNProjects: projects.length || 3,
        },
      },
    })
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-4xl font-bold tracking-tight">
          {r.job_title} at {r.company_name}
        </h1>
        <p className="text-[var(--text-secondary)] mt-1 text-[15px]">{formatDate(r.created_at || new Date())}</p>
      </div>

      {r.tailored_summary && (
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-3">Tailored Summary</h2>
          <p className="text-[var(--text-secondary)] leading-relaxed">{r.tailored_summary}</p>
        </div>
      )}

      <ATSPanel
        masterCvId={effectiveMasterCvId}
        applicationId={id}
        initialGeneral={initialGeneral}
        initialJob={initialJob}
      />

      {r.job_description && (
        <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6">
          <h2 className="text-lg font-semibold mb-3">Job Description</h2>
          <div
            className={`text-[var(--text-secondary)] text-sm leading-relaxed whitespace-pre-wrap ${
              showFullJd ? '' : 'line-clamp-6'
            }`}
          >
            {r.job_description}
          </div>
          <button
            onClick={() => setShowFullJd((v) => !v)}
            className="mt-3 text-[var(--accent)] hover:opacity-80 text-sm transition-opacity"
          >
            {showFullJd ? 'Show less' : 'Show more'}
          </button>
        </div>
      )}

      <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6 space-y-6">
        <h2 className="text-lg font-semibold">Relevance Scores</h2>

        {experiences.length > 0 && (
          <div>
            <h3 className="text-xs uppercase tracking-wide text-[var(--text-muted)] mb-3">Experience</h3>
            <ul className="space-y-3">
              {experiences.map((e, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span
                    className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold shrink-0 ${scoreClasses(e.score)}`}
                  >
                    {e.score}
                  </span>
                  <div>
                    <p className="font-medium">{e.name}</p>
                    <p className="text-[var(--text-secondary)] text-sm">{e.reason}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {projects.length > 0 && (
          <div>
            <h3 className="text-xs uppercase tracking-wide text-[var(--text-muted)] mb-3">Projects</h3>
            <ul className="space-y-3">
              {projects.map((p, i) => (
                <li key={i} className="flex items-start gap-3">
                  <span
                    className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold shrink-0 ${scoreClasses(p.score)}`}
                  >
                    {p.score}
                  </span>
                  <div>
                    <p className="font-medium">{p.name}</p>
                    <p className="text-[var(--text-secondary)] text-sm">{p.reason}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <QAPanel applicationId={id} />

      <CoverLetterPanel applicationId={id} initialCoverLetter={initialCoverLetter} />

      <SectionEditor
        applicationId={id}
        initialConfig={sectionConfig}
        onSaved={handleSectionsSaved}
      />

      <TemplatePanel applicationId={id} onSelect={handleTemplateSelected} />

      <div className="flex flex-wrap gap-3">
        <button
          onClick={downloadFile}
          className="bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-medium px-4 py-2 rounded-lg transition-colors"
        >
          {selectedTemplate?.output ? `Download ${selectedTemplate.output.toUpperCase()}` : 'Download'}
        </button>
        <button
          onClick={togglePreview}
          className="bg-[var(--surface)] hover:bg-[var(--surface-raised)] border border-[var(--border)] text-[var(--text-primary)] font-medium px-4 py-2 rounded-lg transition-colors"
        >
          {previewOpen ? 'Hide preview' : 'Preview CV'}
        </button>
        <button
          onClick={tailorAnother}
          className="bg-[var(--surface)] hover:bg-[var(--surface-raised)] border border-[var(--border)] text-[var(--text-primary)] font-medium px-4 py-2 rounded-lg transition-colors"
        >
          Tailor another job
        </button>
        <button
          onClick={changeJobDetails}
          className="bg-[var(--surface)] hover:bg-[var(--surface-raised)] border border-[var(--border)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] font-medium px-4 py-2 rounded-lg transition-colors"
        >
          Change job details
        </button>
      </div>

      {previewOpen && (
        <div className="bg-white rounded-xl overflow-hidden border border-[var(--border)]">
          {previewLoading ? (
            <div className="p-6 text-slate-700">Loading preview...</div>
          ) : previewError ? (
            <div className="p-6 text-slate-700">{previewError}</div>
          ) : previewPdfUrl ? (
            <iframe
              title="CV Preview"
              src={previewPdfUrl}
              className="w-full"
              style={{ height: '800px', border: 'none' }}
            />
          ) : (
            <div className="p-6 text-slate-700">No preview available.</div>
          )}
        </div>
      )}
    </div>
  )
}
