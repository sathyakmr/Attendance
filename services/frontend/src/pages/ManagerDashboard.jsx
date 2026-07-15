import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import StatusStamp from '../components/StatusStamp'
import { api } from '../lib/api'

export default function ManagerDashboard() {
  const [requests, setRequests] = useState([])
  const [reviewQueue, setReviewQueue] = useState([])
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionError, setActionError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [reqs, queue, emps] = await Promise.all([
        api.listRegularizations(),
        api.listReviewQueue(),
        api.listEmployees(),
      ])
      setRequests(reqs)
      setReviewQueue(queue)
      setEmployees(emps)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const employeeName = (id) => employees.find((e) => e.id === id)?.full_name || id?.slice(0, 8)

  async function handleDecision(requestId, decision) {
    setActionError(null)
    const notes = decision === 'REJECT' ? window.prompt('Reason for rejection (optional):') || '' : undefined
    try {
      await api.decideRegularization(requestId, decision, notes)
      load()
    } catch (err) {
      setActionError(err.message)
    }
  }

  async function handleResolve(itemId, resolution) {
    setActionError(null)
    const notes = window.prompt(`Notes for ${resolution.toLowerCase()} (optional):`) || ''
    try {
      await api.resolveReviewItem(itemId, resolution, notes)
      load()
    } catch (err) {
      setActionError(err.message)
    }
  }

  const pendingRequests = requests.filter((r) => r.status === 'PENDING' || r.status === 'AI_PRESCREENED')

  if (loading) return <Layout><p className="muted">Loading team data…</p></Layout>

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1>Team &amp; Approvals</h1>
          <p>Regularization requests and AI-flagged anomalies awaiting your review.</p>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {actionError && <div className="error-banner">{actionError}</div>}

      <div className="card-row">
        <div className="card stat-block">
          <div className="stat-value numeric">{pendingRequests.length}</div>
          <div className="stat-label">Pending Requests</div>
        </div>
        <div className="card stat-block">
          <div className="stat-value numeric">{reviewQueue.filter((i) => i.priority === 'HIGH').length}</div>
          <div className="stat-label">High-Priority Flags</div>
        </div>
        <div className="card stat-block">
          <div className="stat-value numeric">{reviewQueue.length}</div>
          <div className="stat-label">Open Review Items</div>
        </div>
      </div>

      <div className="card">
        <h2>Regularization Requests</h2>
        {pendingRequests.length === 0 ? (
          <div className="empty-state">No pending requests.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th>Date</th>
                <th>Type</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {pendingRequests.map((r) => (
                <tr key={r.id}>
                  <td>{employeeName(r.employee_id)}</td>
                  <td className="numeric">{r.target_date}</td>
                  <td>{r.requested_event_type.replace('_', ' ')}</td>
                  <td>{r.reason}</td>
                  <td><StatusStamp status={r.status} /></td>
                  <td>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn btn-approve" onClick={() => handleDecision(r.id, 'APPROVE')}>Approve</button>
                      <button className="btn btn-reject" onClick={() => handleDecision(r.id, 'REJECT')}>Reject</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>AI Review Queue</h2>
        {reviewQueue.length === 0 ? (
          <div className="empty-state">No open anomaly flags.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Priority</th>
                <th>Employee</th>
                <th>Reason</th>
                <th>Raised</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {reviewQueue.map((item) => (
                <tr key={item.id}>
                  <td>
                    <span className={`priority-dot priority-dot--${item.priority}`} />
                    {item.priority}
                  </td>
                  <td>{item.employee_id ? employeeName(item.employee_id) : '—'}</td>
                  <td>{item.reason}</td>
                  <td className="numeric muted">{new Date(item.created_at).toLocaleString()}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn btn-reject" onClick={() => handleResolve(item.id, 'CONFIRMED')}>Confirm</button>
                      <button className="btn btn-secondary" onClick={() => handleResolve(item.id, 'DISMISSED')}>Dismiss</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Layout>
  )
}
