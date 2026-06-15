// Triggers a browser download for a Blob response in a way that works across
// desktop and mobile browsers (notably Chrome on Android).
//
// Two things matter for mobile Chrome:
//   1. The Blob must carry an explicit MIME type, otherwise the saved file is
//      named "blob" with no extension and the user has to rename it by hand.
//   2. The object URL must not be revoked synchronously after a().click() —
//      mobile Chrome processes the click asynchronously and revoking too early
//      cancels/garbles the download. Defer the revoke instead.
export function saveBlob(data, filename, contentType) {
  const type = contentType || data.type || 'application/octet-stream'
  const blob = data instanceof Blob && data.type ? data : new Blob([data], { type })

  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

// Pulls a filename out of a Content-Disposition header, falling back to the
// provided default. Handles both quoted and unquoted filename values.
export function filenameFromDisposition(disposition, fallback) {
  const match = (disposition || '').match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i)
  return match ? decodeURIComponent(match[1].trim()) : fallback
}
