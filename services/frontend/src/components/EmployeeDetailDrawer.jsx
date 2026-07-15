import { useState, useEffect } from 'react'
import StatusStamp from './StatusStamp'
import { api } from '../lib/api'

export default function EmployeeDetailDrawer({ employeeCode, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!employeeCode) return
    let cancelled = false
    setLoading(true)
    setError(null)
    setDetail(null)
    api.getEmployeeDetailHistory(employeeCode)
      .then((data) => { if (!cancelled) setDetail(data) })
      .catch((err) => { if (!cancelled) setError(err.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [employeeCode])

  useEffect(() => {
    function handleEsc(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  if (!employeeCode) return null

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <div className="drawer" role="dialog" aria-label="Employee details">
        <div className="drawer-header">
          <div>
            <h2 style={{ marginBottom: 4 }}>{detail?.full_name || employeeCode}</h2>
            <p className="muted" style={{ margin: 0 }}>{detail?.department || '—'}</p>
          </div>
          <button className="drawer-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        {loading && <p className="muted">Loading employee details…</p>}
        {error && <div className="error-banner">{error}</div>}

        {detail && (
          <>
            <div className="drawer-field-grid">
              <div>
                <div className="drawer-field-label">Employee Code</div>
                <div className="drawer-field-value numeric">{detail.employee_code}</div>
              </div>
              <div>
                <div className="drawer-field-label">Manager</div>
                <div className="drawer-field-value">{detail.manager_name || '—'}</div>
              </div>
              <div>
                <div className="drawer-field-label">Face Enrolled</div>
                <div className="drawer-field-value">
                  <StatusStamp status={detail.face_enrolled ? 'VALIDATED' : 'PENDING'} />
                </div>
              </div>
              <div>
                <div className="drawer-field-label">Total Days Present</div>
                <div className="drawer-field-value numeric">{detail.total_days_present}</div>
              </div>
              <div>
                <div className="drawer-field-label">Total Late Days</div>
                <div className="drawer-field-value numeric">{detail.total_late_days}</div>
              </div>
              <div>
                <div className="drawer-field-label">Last Check In</div>
                <div className="drawer-field-value numeric">
                  {detail.last_check_in ? new Date(detail.last_check_in).toLocaleString() : '—'}
                </div>
              </div>
              <div>
                <div className="drawer-field-label">Last Check Out</div>
                <div className="drawer-field-value numeric">
                  {detail.last_check_out ? new Date(detail.last_check_out).toLocaleString() : '—'}
                </div>
              </div>
            </div>

            <h3>Attendance History</h3>
            {detail.history.length === 0 ? (
              <div className="empty-state">No events recorded.</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Time</th>
                    <th>Type</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.history.map((h, i) => {
                    const ts = new Date(h.event_ts)
                    return (
                      <tr key={i}>
                        <td className="numeric">{ts.toLocaleDateString()}</td>
                        <td className="numeric">{ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                        <td>{h.event_type.replace('_', ' ')}</td>
                        <td><StatusStamp status={h.status} /></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </>
  )
}
