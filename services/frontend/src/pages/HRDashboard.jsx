import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import SummaryCards from '../components/SummaryCards'
import LiveActivityPanel from '../components/LiveActivityPanel'
import AttendanceHistoryTable from '../components/AttendanceHistoryTable'
import EmployeeDetailDrawer from '../components/EmployeeDetailDrawer'
import { api } from '../lib/api'

export default function HRDashboard() {
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)

  const [summary, setSummary] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(true)

  const [selectedEmployeeCode, setSelectedEmployeeCode] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const emps = await api.listEmployees()
      setEmployees(emps)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true)
    try {
      const data = await api.getDashboardSummary()
      setSummary(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setSummaryLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    loadSummary()
  }, [load, loadSummary])

  const departments = [...new Set(employees.map((e) => e.department).filter(Boolean))]

  if (loading) return <Layout><p className="muted">Loading organization…</p></Layout>

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1>Organization</h1>
          <p>Org-wide employee directory and attendance overview.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Cancel' : 'Add Employee'}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {showForm && <NewEmployeeForm onCreated={() => { setShowForm(false); load(); loadSummary() }} />}

      <SummaryCards summary={summary} loading={summaryLoading} />

      <LiveActivityPanel />

      <AttendanceHistoryTable
        departments={departments}
        onSelectEmployee={(code) => setSelectedEmployeeCode(code)}
      />

      <div className="card">
        <h2>Directory</h2>
        {employees.length === 0 ? (
          <div className="empty-state">No employees on record.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Department</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {employees.map((e) => (
                <tr
                  key={e.id}
                  className="row-clickable"
                  onClick={() => setSelectedEmployeeCode(e.employee_code)}
                  title="View employee details"
                >
                  <td className="numeric">{e.employee_code}</td>
                  <td>{e.full_name}</td>
                  <td>{e.department || '—'}</td>
                  <td>{e.is_active ? 'Active' : 'Inactive'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selectedEmployeeCode && (
        <EmployeeDetailDrawer
          employeeCode={selectedEmployeeCode}
          onClose={() => setSelectedEmployeeCode(null)}
        />
      )}
    </Layout>
  )
}

function NewEmployeeForm({ onCreated }) {
  const [employeeCode, setEmployeeCode] = useState('')
  const [fullName, setFullName] = useState('')
  const [department, setDepartment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.createEmployee({ employee_code: employeeCode, full_name: fullName, department })
      onCreated()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="card">
      <h2>New Employee</h2>
      {error && <div className="error-banner">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="card-row">
          <div className="field">
            <label htmlFor="employee-code">Employee Code</label>
            <input id="employee-code" value={employeeCode} onChange={(e) => setEmployeeCode(e.target.value)} placeholder="EMP005" required />
          </div>
          <div className="field">
            <label htmlFor="full-name">Full Name</label>
            <input id="full-name" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </div>
          <div className="field">
            <label htmlFor="department">Department</label>
            <input id="department" value={department} onChange={(e) => setDepartment(e.target.value)} />
          </div>
        </div>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Creating…' : 'Create Employee'}
        </button>
      </form>
    </div>
  )
}
