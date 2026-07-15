import { useState, useEffect, useCallback } from 'react'
import StatusStamp from './StatusStamp'
import { api } from '../lib/api'

const PAGE_SIZE = 20

export default function AttendanceHistoryTable({ departments, onSelectEmployee }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [search, setSearch] = useState('')
  const [datePreset, setDatePreset] = useState('')
  const [department, setDepartment] = useState('')
  const [status, setStatus] = useState('')

  const load = useCallback(async (targetPage) => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.getAttendanceHistoryTable({
        page: targetPage,
        pageSize: PAGE_SIZE,
        search: search || undefined,
        department: department || undefined,
        status: status || undefined,
        date: datePreset || undefined,
      })
      setItems(result.items)
      setTotal(result.total)
      setPage(result.page)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, department, status, datePreset])

  // Reset to page 1 whenever a filter changes; otherwise just (re)load current page.
  useEffect(() => {
    load(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, department, status, datePreset])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="card">
      <h2>Attendance History</h2>

      <div className="filter-bar">
        <div className="field">
          <label htmlFor="hist-search">Search</label>
          <input
            id="hist-search"
            placeholder="Employee code or name"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="hist-date">Date</label>
          <select id="hist-date" value={datePreset} onChange={(e) => setDatePreset(e.target.value)}>
            <option value="">All time</option>
            <option value="TODAY">Today</option>
            <option value="YESTERDAY">Yesterday</option>
            <option value="THIS_WEEK">This Week</option>
            <option value="THIS_MONTH">This Month</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="hist-dept">Department</label>
          <select id="hist-dept" value={department} onChange={(e) => setDepartment(e.target.value)}>
            <option value="">All</option>
            {departments.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="hist-status">Status</label>
          <select id="hist-status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All</option>
            <option value="VALIDATED">Validated</option>
            <option value="FLAGGED">Flagged</option>
            <option value="REJECTED">Rejected</option>
            <option value="PENDING_VALIDATION">Pending</option>
            <option value="SUPERSEDED">Superseded</option>
          </select>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {loading ? (
        <p className="muted">Loading attendance history…</p>
      ) : items.length === 0 ? (
        <div className="empty-state">No matching attendance events.</div>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>Employee Code</th>
                <th>Employee Name</th>
                <th>Department</th>
                <th>Date</th>
                <th>Time</th>
                <th>Event Type</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const ts = new Date(item.event_ts)
                return (
                  <tr
                    key={item.id}
                    className="row-clickable"
                    onClick={() => onSelectEmployee(item.employee_code)}
                    title="View employee details"
                  >
                    <td className="numeric">{item.employee_code}</td>
                    <td>{item.full_name}</td>
                    <td>{item.department || '—'}</td>
                    <td className="numeric">{ts.toLocaleDateString()}</td>
                    <td className="numeric">{ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                    <td>{item.event_type.replace('_', ' ')}</td>
                    <td><StatusStamp status={item.status} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>

          <div className="pagination">
            <span>
              Page {page} of {totalPages} · {total} total events
            </span>
            <div className="pagination-controls">
              <button className="btn btn-secondary" disabled={page <= 1} onClick={() => load(page - 1)}>
                ← Prev
              </button>
              <button className="btn btn-secondary" disabled={page >= totalPages} onClick={() => load(page + 1)}>
                Next →
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
