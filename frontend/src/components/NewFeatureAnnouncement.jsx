import { useNavigate } from 'react-router-dom'
import api from '../lib/axios'
import useAppStore from '../store/useAppStore'

// One-time announcement for the bring-your-own LLM keys feature. Gated on a
// backend flag (has_seen_llm_keys_announcement) so it shows exactly once per
// user — new and existing — and stays dismissed across refreshes and devices.
export default function NewFeatureAnnouncement() {
  const navigate = useNavigate()
  const user = useAppStore((s) => s.user)
  const setUser = useAppStore((s) => s.setUser)

  // Don't show until the email is verified (the verify modal takes priority),
  // or to users who've already seen it.
  if (!user || user.has_seen_llm_keys_announcement || !user.is_verified) {
    return null
  }

  const dismiss = async () => {
    try {
      const { data } = await api.patch('/users/me', { has_seen_llm_keys_announcement: true })
      setUser(data)
    } catch {
      // Optimistically hide even if the PATCH fails — it'll re-show next session.
      setUser({ ...user, has_seen_llm_keys_announcement: true })
    }
  }

  const goToProfile = async () => {
    await dismiss()
    navigate('/profile')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md bg-[var(--surface)] border border-[var(--border)] rounded-xl p-6 relative">
        <button
          onClick={dismiss}
          aria-label="Close"
          className="absolute top-3 right-3 text-[var(--text-muted)] hover:text-white transition-colors text-xl leading-none px-2 py-1"
        >
          &times;
        </button>

        <h2 className="text-lg font-bold tracking-tight">New: bring your own AI keys</h2>
        <p className="text-[var(--text-secondary)] text-sm mt-2">
          You can now add your own LLM provider API keys (Groq, Gemini, and more) in your
          profile. Use your own quota for parsing and tailoring — with a much higher rate
          limit, and no waiting on the shared pool.
        </p>

        <button
          onClick={goToProfile}
          className="mt-5 w-full bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white font-medium h-10 rounded-lg transition-colors"
        >
          Set up my keys
        </button>
        <button
          onClick={dismiss}
          className="mt-3 w-full text-sm text-[var(--text-muted)] hover:text-white transition-colors"
        >
          Maybe later
        </button>
      </div>
    </div>
  )
}
