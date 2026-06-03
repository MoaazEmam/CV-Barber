import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'
import ConfirmDialog from '../components/ConfirmDialog'

const ACCEPTED = ['.pdf', '.docx']

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
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

function PreviousCVsSection({ onSelect }) {
  const [cvs, setCvs] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null)
  const [confirmCv, setConfirmCv] = useState(null)
  const masterCvId = useAppStore((s) => s.masterCvId)
  const resetCvFlow = useAppStore((s) => s.resetCvFlow)

  useEffect(() => {
    let alive = true
    api
      .get('/api/master-cvs')
      .then((res) => {
        if (!alive) return
        setCvs(res.data?.master_cvs || [])
      })
      .catch(() => {})
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [])

  const handleConfirmedDelete = async () => {
    const cv = confirmCv
    setConfirmCv(null)
    setDeleting(cv.id)
    try {
      await api.delete(`/api/master-cvs/${cv.id}`)
      setCvs((prev) => prev.filter((c) => c.id !== cv.id))
      if (masterCvId === cv.id) resetCvFlow()
    } catch {
    } finally {
      setDeleting(null)
    }
  }

  if (loading || cvs.length === 0) return null

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-[var(--border)]" />
        <span className="text-[var(--text-muted)] text-sm">or use a previously uploaded CV</span>
        <div className="flex-1 h-px bg-[var(--border)]" />
      </div>
      <div className="space-y-2">
        {cvs.map((cv) => (
          <div
            key={cv.id}
            className="flex items-center justify-between bg-[var(--surface)] border border-[var(--border)] rounded-xl px-4 py-3"
          >
            <div>
              <p className="text-[var(--text-primary)] font-medium text-sm">{cv.full_name}</p>
              <p className="text-[var(--text-muted)] text-xs mt-0.5">
                {cv.experience_count} exp · {cv.project_count} projects · {cv.skills_count} skills
                {' · '}{formatDate(cv.created_at)}
              </p>
            </div>
            <div className="flex items-center gap-2 ml-3 shrink-0">
              <button
                onClick={() => onSelect(cv)}
                className="bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium px-3 py-1.5 rounded-lg transition-colors"
              >
                Use this CV
              </button>
              <button
                onClick={() => setConfirmCv(cv)}
                disabled={deleting === cv.id}
                className="text-[var(--text-muted)] hover:text-red-400 p-1.5 rounded-lg hover:bg-red-500/10 transition-colors disabled:opacity-40"
                title="Delete this CV"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                </svg>
              </button>
            </div>
          </div>
        ))}
      </div>

      <ConfirmDialog
        open={confirmCv !== null}
        title="Delete CV?"
        message={confirmCv ? `"${confirmCv.full_name}" and all its tailored applications will be permanently removed.` : ''}
        onConfirm={handleConfirmedDelete}
        onCancel={() => setConfirmCv(null)}
      />
    </div>
  )
}

export default function UploadPage() {
  const navigate = useNavigate()
  const setMasterCv = useAppStore((s) => s.setMasterCv)
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState('')
  const [warnings, setWarnings] = useState([])
  const [loading, setLoading] = useState(false)

  const pickFile = (f) => {
    if (!f) return
    const ext = '.' + f.name.split('.').pop().toLowerCase()
    if (!ACCEPTED.includes(ext)) {
      setError('Only PDF and DOCX files are supported.')
      return
    }
    setError('')
    setWarnings([])
    setFile(f)
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files[0]) pickFile(e.dataTransfer.files[0])
  }

  const onParse = async () => {
    if (!file) return
    setLoading(true)
    setError('')
    setWarnings([])
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/api/parse', form)
      const meta = {
        full_name: res.data.full_name,
        experience_count: res.data.experience_count,
        project_count: res.data.project_count,
        skills_count: res.data.skills_count,
      }
      setMasterCv(res.data.session_id, meta)
      if (res.data.warnings?.length) {
        // Parsed, but extraction looked incomplete — let the user see why before
        // proceeding instead of silently navigating on.
        setWarnings(res.data.warnings)
        return
      }
      navigate('/tailor')
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Failed to read CV.')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectExisting = (cv) => {
    setMasterCv(cv.id, {
      full_name: cv.full_name,
      experience_count: cv.experience_count,
      project_count: cv.project_count,
      skills_count: cv.skills_count,
    })
    navigate('/tailor')
  }

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      <div>
        <h1 className="text-4xl font-bold tracking-tight text-[var(--text-primary)]">
          Upload your CV
        </h1>
        <p className="text-[var(--text-secondary)] mt-2 text-[15px]">
          We'll read it once and use it as the foundation for every application.
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`border rounded-xl p-14 text-center transition-all cursor-default ${
          dragOver
            ? 'border-dashed border-[var(--accent)] bg-[var(--accent-subtle)]'
            : 'border-[rgba(255,255,255,0.08)] bg-[radial-gradient(ellipse_at_center,rgba(94,106,210,0.04)_0%,transparent_70%)]'
        }`}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.2}
          stroke="currentColor"
          className="w-14 h-14 mx-auto text-[var(--text-muted)]"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 7.5 7.5 12M12 7.5v9"
          />
        </svg>

        {file ? (
          <div className="mt-4">
            <p className="text-sm text-[var(--text-secondary)]">
              <span className="text-[var(--text-primary)] font-medium">{file.name}</span>
              {' · '}{formatSize(file.size)}
            </p>
            <button
              onClick={() => setFile(null)}
              className="mt-2 text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
            >
              Remove
            </button>
          </div>
        ) : (
          <p className="mt-4 text-[var(--text-secondary)]">
            Drag and drop your CV here,{' '}
            <button
              onClick={() => inputRef.current?.click()}
              className="text-[var(--accent)] hover:opacity-80 transition-opacity font-medium underline underline-offset-2"
            >
              or browse
            </button>
          </p>
        )}

        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          hidden
          onChange={(e) => pickFile(e.target.files[0])}
        />
      </div>

      <p className="text-xs text-[var(--text-muted)] text-center -mt-1">.pdf and .docx supported</p>

      <button
        onClick={onParse}
        disabled={!file || loading}
        className={`w-full font-medium h-11 rounded-lg transition-colors ${
          file && !loading
            ? 'bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white'
            : 'bg-[var(--surface-raised)] text-[var(--text-muted)] cursor-not-allowed'
        }`}
      >
        {loading ? 'Analyzing...' : 'Analyze CV'}
      </button>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {warnings.length > 0 && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 space-y-2">
          <p className="text-amber-300 text-sm font-medium">
            We parsed your CV, but a few things looked off:
          </p>
          <ul className="list-disc list-inside text-amber-200/90 text-sm space-y-1">
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
          <button
            onClick={() => navigate('/tailor')}
            className="mt-1 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            Continue anyway →
          </button>
        </div>
      )}

      <PreviousCVsSection onSelect={handleSelectExisting} />
    </div>
  )
}
