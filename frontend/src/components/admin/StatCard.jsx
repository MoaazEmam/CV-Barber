export default function StatCard({ label, value, hint }) {
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-4">
      <p className="text-sm text-[var(--text-secondary)]">{label}</p>
      <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">{value}</p>
      {hint && <p className="text-xs text-[var(--text-muted)] mt-1">{hint}</p>}
    </div>
  )
}
