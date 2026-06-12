// Tiny dependency-free bar chart. data: [{ label, count }]. Hover shows
// "label: count" via the native title tooltip. Renders a 0/mid/max y-axis
// with gridlines and ~5 evenly spaced x-axis labels (shortened via
// formatXLabel, e.g. to strip the year off ISO dates).
// fill: stretch vertically to the parent's height (parent must be a sized
// flex column) instead of using the fixed `height`.
export default function BarChart({ data, height = 120, fill = false, formatXLabel = (l) => l }) {
  const max = Math.max(1, ...data.map((d) => d.count))
  const mid = Math.ceil(max / 2)

  // ~5 evenly spaced x labels, always including first and last bars.
  const n = data.length
  const step = Math.max(1, Math.ceil(n / 5))
  const labelIdx = new Set()
  for (let i = 0; i < n; i += step) labelIdx.add(i)
  if (n > 0) labelIdx.add(n - 1)

  return (
    <div className={fill ? 'h-full flex flex-col' : ''}>
      <div className={`flex gap-2 ${fill ? 'flex-1 min-h-0' : ''}`}>
        <div
          className="flex flex-col justify-between text-right text-xs text-[var(--text-muted)] shrink-0 w-7"
          style={fill ? undefined : { height }}
        >
          <span>{max}</span>
          <span>{mid}</span>
          <span>0</span>
        </div>
        <div className="relative flex-1" style={fill ? undefined : { height }}>
          {/* gridlines at max / mid / 0 */}
          <div className="absolute inset-x-0 top-0 border-t border-[var(--border)]" />
          <div className="absolute inset-x-0 top-1/2 border-t border-[var(--border)] opacity-60" />
          <div className="absolute inset-x-0 bottom-0 border-t border-[var(--border)]" />
          <div className="absolute inset-0 flex items-end gap-[2px]">
            {data.map((d) => (
              <div
                key={d.label}
                title={`${d.label}: ${d.count}`}
                className="flex-1 flex flex-col justify-end h-full group cursor-default"
              >
                <div
                  className="w-full rounded-t bg-[var(--accent)] opacity-70 group-hover:opacity-100 transition-opacity"
                  style={{ height: `${(d.count / max) * 100}%`, minHeight: d.count > 0 ? 2 : 0 }}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="flex gap-2 mt-1">
        <div className="w-7 shrink-0" />
        <div className="relative flex-1 h-4 text-xs text-[var(--text-muted)]">
          {data.map((d, i) =>
            labelIdx.has(i) ? (
              <span
                key={d.label}
                className="absolute whitespace-nowrap"
                style={{
                  left: `${((i + 0.5) / n) * 100}%`,
                  transform:
                    i === n - 1 ? 'translateX(-100%)' : i === 0 ? 'none' : 'translateX(-50%)',
                }}
              >
                {formatXLabel(d.label)}
              </span>
            ) : null,
          )}
        </div>
      </div>
    </div>
  )
}
