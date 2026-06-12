import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import api from '../lib/axios'

// Floating "Feedback" button (bottom-right) opening a small panel where any
// signed-in user can send a suggestion / bug report. The current route is
// attached as page_context so admins know where the issue happened.
export default function FeedbackWidget() {
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [type, setType] = useState('suggestion')
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  const close = () => {
    setOpen(false)
    setSent(false)
    setError('')
  }

  const submit = async (e) => {
    e.preventDefault()
    if (message.trim().length < 3) {
      setError('Please write a few more words.')
      return
    }
    setSending(true)
    setError('')
    try {
      await api.post('/api/feedback', {
        type,
        message: message.trim(),
        page_context: location.pathname,
      })
      setMessage('')
      setSent(true)
    } catch (err) {
      setError(
        err.response?.status === 429
          ? 'Slow down a little — try again in a minute.'
          : 'Failed to send feedback. Please try again.',
      )
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="fixed bottom-5 right-5 z-50">
      {open && (
        <div className="absolute bottom-12 right-0 w-80 bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4 shadow-2xl">
          {sent ? (
            <div className="text-center py-4">
              <p className="text-[var(--text-primary)] font-medium">Thanks for the feedback!</p>
              <p className="text-[var(--text-secondary)] text-sm mt-1">We read everything.</p>
              <button
                onClick={close}
                className="mt-4 text-sm text-[var(--accent)] hover:opacity-80"
              >
                Close
              </button>
            </div>
          ) : (
            <form onSubmit={submit} className="space-y-3">
              <p className="text-sm font-semibold text-[var(--text-primary)]">Send feedback</p>
              <div className="flex gap-2">
                {['suggestion', 'bug', 'other'].map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setType(t)}
                    className={`text-xs px-3 py-1 rounded-lg border transition-colors capitalize ${
                      type === t
                        ? 'border-[var(--accent)] text-[var(--text-primary)]'
                        : 'border-[var(--border)] text-[var(--text-secondary)] hover:text-white'
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={4}
                maxLength={5000}
                placeholder={
                  type === 'bug'
                    ? 'What went wrong? What did you expect to happen?'
                    : 'What would make CV Barber better?'
                }
                className="w-full bg-[var(--bg)] border border-[var(--border)] rounded-lg p-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] resize-none"
              />
              {error && <p className="text-red-400 text-xs">{error}</p>}
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={close}
                  className="text-sm text-[var(--text-secondary)] hover:text-white px-3 py-1.5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={sending}
                  className="bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                >
                  {sending ? 'Sending…' : 'Send'}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
      <button
        onClick={() => (open ? close() : setOpen(true))}
        className="bg-[var(--surface)] border border-[var(--border)] hover:border-[var(--accent)] text-[var(--text-secondary)] hover:text-white text-sm px-4 py-2 rounded-full shadow-lg transition-colors"
      >
        {open ? '✕' : 'Feedback'}
      </button>
    </div>
  )
}
