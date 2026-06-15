import { useEffect, useState } from 'react'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'

const PROVIDER_LABELS = {
  groq: 'Groq',
  gemini: 'Google Gemini',
  cerebras: 'Cerebras',
  nvidia: 'NVIDIA',
  mistral: 'Mistral',
  openrouter: 'OpenRouter',
  zai: 'Z.AI',
}

const inputClass =
  'w-full bg-[var(--bg)] border border-[rgba(255,255,255,0.10)] text-[var(--text-primary)] rounded-lg px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-[#5E6AD2]/30 focus:border-[#5E6AD2]/60 transition-colors placeholder:text-[var(--text-muted)]'

export default function ProfilePage() {
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)

  const [providers, setProviders] = useState([])
  const [keys, setKeys] = useState([])
  const [fallback, setFallback] = useState(false)
  const [loaded, setLoaded] = useState(false)

  const [provider, setProvider] = useState('groq')
  const [keyValue, setKeyValue] = useState('')
  const [label, setLabel] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = async () => {
    try {
      const { data } = await api.get('/api/llm-keys')
      setProviders(data.providers || [])
      setKeys(data.keys || [])
      setFallback(!!data.fallback_to_shared)
      if (data.providers?.length) setProvider(data.providers[0])
    } catch {
      setError('Could not load your keys.')
    } finally {
      setLoaded(true)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const addKey = async (e) => {
    e.preventDefault()
    setError('')
    setSaving(true)
    try {
      await api.post('/api/llm-keys', { provider, key: keyValue.trim(), label: label.trim() || undefined })
      setKeyValue('')
      setLabel('')
      await load()
    } catch (err) {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Could not add this key.')
    } finally {
      setSaving(false)
    }
  }

  const deleteKey = async (id) => {
    setError('')
    try {
      await api.delete(`/api/llm-keys/${id}`)
      setKeys((ks) => ks.filter((k) => k.id !== id))
    } catch {
      setError('Could not delete that key.')
    }
  }

  const toggleFallback = async (next) => {
    setFallback(next)
    try {
      const { data } = await api.patch('/users/me', { llm_fallback_to_shared: next })
      setUser(data)
    } catch {
      setFallback(!next) // revert on failure
      setError('Could not update the fallback setting.')
    }
  }

  const hasKeys = keys.length > 0

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold tracking-tight">Profile</h1>
      <p className="text-[var(--text-secondary)] text-sm mt-1">
        Signed in as <span className="text-[var(--text-primary)]">{user?.email}</span>
      </p>

      <section className="mt-8 bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6">
        <h2 className="text-lg font-semibold">Your LLM API keys</h2>
        <p className="text-[var(--text-secondary)] text-sm mt-1">
          Add your own provider keys to run parsing and tailoring on your own quota —
          with a much higher rate limit. Keys are encrypted and never shown again.
        </p>

        {loaded && (
          <div className="mt-5 space-y-2">
            {hasKeys ? (
              keys.map((k) => (
                <div
                  key={k.id}
                  className="flex items-center justify-between bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2.5"
                >
                  <div className="text-sm">
                    <span className="font-medium">{PROVIDER_LABELS[k.provider] || k.provider}</span>
                    {k.label && <span className="text-[var(--text-muted)]"> · {k.label}</span>}
                    <span className="text-[var(--text-muted)]"> · ••••{k.key_hint}</span>
                  </div>
                  <button
                    onClick={() => deleteKey(k.id)}
                    className="text-sm text-[var(--text-secondary)] hover:text-red-400 transition-colors"
                  >
                    Remove
                  </button>
                </div>
              ))
            ) : (
              <p className="text-sm text-[var(--text-muted)]">No keys yet — you're using the shared pool.</p>
            )}
          </div>
        )}

        <form onSubmit={addKey} className="mt-5 grid gap-3 sm:grid-cols-[160px_1fr] sm:items-start">
          <select value={provider} onChange={(e) => setProvider(e.target.value)} className={inputClass}>
            {providers.map((p) => (
              <option key={p} value={p}>{PROVIDER_LABELS[p] || p}</option>
            ))}
          </select>
          <div className="space-y-3">
            <input
              type="password"
              autoComplete="off"
              placeholder="Paste your API key"
              value={keyValue}
              onChange={(e) => setKeyValue(e.target.value)}
              className={inputClass}
              required
            />
            <input
              type="text"
              placeholder="Label (optional, e.g. 'personal')"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              maxLength={60}
              className={inputClass}
            />
            <button
              type="submit"
              disabled={saving || keyValue.trim().length < 8}
              className="w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white font-medium h-10 rounded-lg transition-colors"
            >
              {saving ? 'Validating…' : 'Add key'}
            </button>
          </div>
        </form>

        {error && <p className="text-red-400 text-sm mt-3">{error}</p>}

        <label className="flex items-start gap-2 mt-6 cursor-pointer">
          <input
            type="checkbox"
            checked={fallback}
            onChange={(e) => toggleFallback(e.target.checked)}
            disabled={!hasKeys}
            className="mt-0.5"
          />
          <span className="text-sm text-[var(--text-secondary)]">
            Fall back to the app's shared keys if mine fail
            <span className="block text-xs text-[var(--text-muted)]">
              When off, a request fails clearly if your own keys are down or out of quota.
            </span>
          </span>
        </label>
      </section>
    </div>
  )
}
