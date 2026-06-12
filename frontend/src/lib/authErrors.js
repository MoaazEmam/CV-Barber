// Maps backend auth error responses (FastAPI / FastAPI-Users) to friendly,
// specific messages so the UI never shows a raw error code or a blank string.
// Used by both LoginPage and RegisterPage.

const CODE_MESSAGES = {
  REGISTER_USER_ALREADY_EXISTS: 'An account with this email already exists.',
  LOGIN_BAD_CREDENTIALS: 'Incorrect email/username or password.',
  LOGIN_USER_NOT_VERIFIED: 'Please verify your email before signing in.',
}

// Pydantic v2 prefixes custom validator messages with "Value error, ".
function clean(msg) {
  return String(msg).replace(/^Value error,\s*/i, '')
}

function fallback(context) {
  return context === 'login'
    ? 'Sign-in failed. Please try again.'
    : 'Registration failed. Please try again.'
}

export function authErrorMessage(err, context = 'register') {
  const res = err?.response

  // No response at all → network / CORS / server down.
  if (!res) return 'Network error — check your connection and try again.'

  // Brute-force guard on /auth/* returns 429 + Retry-After.
  if (res.status === 429) return 'Too many attempts. Please wait a minute and try again.'

  const detail = res.data?.detail

  // Clean backend strings, or known FastAPI-Users error codes.
  if (typeof detail === 'string') {
    return CODE_MESSAGES[detail] || detail
  }

  // Pydantic validation errors: [{ loc, msg, type }, ...]
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => {
      const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : undefined
      if (field === 'email') return 'Please enter a valid email address.'
      return clean(d.msg)
    })
    return msgs.filter(Boolean).join(' ') || fallback(context)
  }

  // FastAPI-Users InvalidPasswordException: { code, reason }
  if (detail && typeof detail === 'object') {
    if (detail.reason) return clean(detail.reason)
    if (detail.code && CODE_MESSAGES[detail.code]) return CODE_MESSAGES[detail.code]
  }

  return fallback(context)
}
