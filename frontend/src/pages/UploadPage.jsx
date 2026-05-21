import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'

const ACCEPTED = ['.pdf', '.docx']

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function UploadPage() {
  const navigate = useNavigate()
  const setMasterCv = useAppStore((s) => s.setMasterCv)
  const masterCvMeta = useAppStore((s) => s.masterCvMeta)
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(masterCvMeta)

  const pickFile = (f) => {
    if (!f) return
    const ext = '.' + f.name.split('.').pop().toLowerCase()
    if (!ACCEPTED.includes(ext)) {
      setError('Only PDF and DOCX files are supported.')
      return
    }
    setError('')
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
    setResult(null)
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
      setResult(meta)
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Failed to parse CV.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white">Upload your CV</h1>
        <p className="text-slate-400 mt-1">
          Upload a PDF or DOCX and we'll parse it into your master CV
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`border-2 border-dashed rounded-2xl p-12 text-center transition ${
          dragOver ? 'border-indigo-500 bg-slate-900/60' : 'border-slate-700'
        }`}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
          className="w-10 h-10 mx-auto text-slate-500"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 7.5 7.5 12M12 7.5v9"
          />
        </svg>
        <p className="mt-3 text-slate-300">Drag and drop your CV here</p>
        <p className="text-slate-500 text-sm my-1">or</p>
        <button
          onClick={() => inputRef.current?.click()}
          className="bg-slate-800 hover:bg-slate-700 text-white px-4 py-2 rounded-lg transition mt-2"
        >
          Browse files
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          hidden
          onChange={(e) => pickFile(e.target.files[0])}
        />
        {file && (
          <p className="mt-4 text-sm text-slate-400">
            <span className="text-slate-200">{file.name}</span> · {formatSize(file.size)}
          </p>
        )}
      </div>

      <button
        onClick={onParse}
        disabled={!file || loading}
        className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2.5 rounded-lg transition"
      >
        {loading ? 'Parsing...' : 'Parse CV'}
      </button>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {result && (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-3">
          <h2 className="text-lg font-semibold text-white">CV parsed successfully</h2>
          <p className="text-slate-300">{result.full_name}</p>
          <p className="text-slate-400 text-sm">
            {result.experience_count} experience entries, {result.project_count} projects
          </p>
          <button
            onClick={() => navigate('/tailor')}
            className="bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-4 py-2 rounded-lg transition"
          >
            Tailor this CV
          </button>
        </div>
      )}
    </div>
  )
}
