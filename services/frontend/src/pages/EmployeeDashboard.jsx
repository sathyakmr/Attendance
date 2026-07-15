import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import StatusStamp from '../components/StatusStamp'
import { useAuth } from '../lib/auth'
import { api } from '../lib/api'

export default function EmployeeDashboard() {
  const { user } = useAuth()
  const [employee, setEmployee] = useState(null)
  const [events, setEvents] = useState([])
  const [myRequests, setMyRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const allEmployees = await api.listEmployees()
      const me = allEmployees.find((e) => e.id === user.employeeId)
      setEmployee(me || null)

      if (me) {
        const [history, requests] = await Promise.all([
          api.getAttendanceHistory(me.employee_code),
          api.listRegularizations(),
        ])
        setEvents(history)
        setMyRequests(requests)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [user.employeeId])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  if (loading) return <Layout><p className="muted">Loading your attendance record…</p></Layout>

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1>{employee ? employee.full_name : 'My Attendance'}</h1>
          <p>{employee?.department} · {employee?.employee_code}</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cancel' : 'Request Regularization'}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {showForm && (
        <RegularizationForm
          onSubmitted={() => {
            setShowForm(false)
            loadAll()
          }}
        />
      )}

      <div className="card-row">
        <div className="card stat-block">
          <div className="stat-value numeric">{events.length}</div>
          <div className="stat-label">Recorded Events</div>
        </div>
        <div className="card stat-block">
          <div className="stat-value numeric">{events.filter((e) => e.status === 'FLAGGED').length}</div>
          <div className="stat-label">Flagged Events</div>
        </div>
        <div className="card stat-block">
          <div className="stat-value numeric">{myRequests.length}</div>
          <div className="stat-label">Regularization Requests</div>
        </div>
      </div>

      <div className="card">
        <h2>Attendance History</h2>
        {events.length === 0 ? (
          <div className="empty-state">No attendance events recorded yet.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Type</th>
                <th>Source</th>
                <th>Status</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td className="numeric">{new Date(e.event_ts).toLocaleString()}</td>
                  <td>{e.event_type.replace('_', ' ')}</td>
                  <td>{e.source}</td>
                  <td><StatusStamp status={e.status} /></td>
                  <td className="muted">{e.validation_notes || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>My Regularization Requests</h2>
        {myRequests.length === 0 ? (
          <div className="empty-state">No requests submitted.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Target Date</th>
                <th>Type</th>
                <th>Reason</th>
                <th>Status</th>
                <th>AI Note</th>
              </tr>
            </thead>
            <tbody>
              {myRequests.map((r) => (
                <tr key={r.id}>
                  <td className="numeric">{r.target_date}</td>
                  <td>{r.requested_event_type.replace('_', ' ')}</td>
                  <td>{r.reason}</td>
                  <td><StatusStamp status={r.status} /></td>
                  <td className="muted">{r.decision_notes || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Layout>
  )
}

function RegularizationForm({ onSubmitted }) {
  const [targetDate, setTargetDate] = useState('')
  const [eventType, setEventType] = useState('CHECK_IN')
  const [time, setTime] = useState('09:00:00')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.createRegularization({
        target_date: targetDate,
        requested_event_type: eventType,
        requested_time: time,
        reason,
      })
      onSubmitted()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="card">
      <h2>New Regularization Request</h2>
      {error && <div className="error-banner">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="card-row">
          <div className="field">
            <label htmlFor="target-date">Date</label>
            <input id="target-date" type="date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="event-type">Type</label>
            <select id="event-type" value={eventType} onChange={(e) => setEventType(e.target.value)}>
              <option value="CHECK_IN">Check In</option>
              <option value="CHECK_OUT">Check Out</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="time">Time</label>
            <input id="time" type="time" step="1" value={time} onChange={(e) => setTime(e.target.value)} required />
          </div>
        </div>
        <div className="field">
          <label htmlFor="reason">Reason</label>
          <textarea
            id="reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Device malfunction at the entrance this morning"
            required
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Submitting…' : 'Submit Request'}
        </button>
      </form>
    </div>
  )
}
