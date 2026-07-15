const CARD_DEFS = [
  { key: 'totalEmployees', label: 'Total Employees' },
  { key: 'presentToday', label: 'Present Today' },
  { key: 'absentToday', label: 'Absent Today' },
  { key: 'lateToday', label: 'Late Today' },
  { key: 'faceEnrolled', label: 'Face Enrolled' },
  { key: 'pendingRegularization', label: 'Pending Regularization' },
]

export default function SummaryCards({ summary, loading }) {
  return (
    <div className="card-grid">
      {CARD_DEFS.map((def) => (
        <div key={def.key} className={`card stat-block${loading ? ' loading' : ''}`}>
          <div className="stat-value numeric">{loading ? '—' : (summary?.[def.key] ?? 0)}</div>
          <div className="stat-label">{def.label}</div>
        </div>
      ))}
    </div>
  )
}
