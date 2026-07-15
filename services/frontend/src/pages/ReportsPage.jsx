import { useState, useEffect, useCallback } from 'react'
import Layout from '../components/Layout'
import StatusStamp from '../components/StatusStamp'
import { api } from '../lib/api'

export default function ReportsPage() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [period, setPeriod] = useState('DAILY')

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.listReports()
      setReports(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleGenerate() {
    setGenerating(true)
    setError(null)
    try {
      await api.generateReport(period)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  if (loading) return <Layout><p className="muted">Loading reports…</p></Layout>

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1>Reports</h1>
          <p>Attendance summaries delivered to the owner via WhatsApp.</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <select value={period} onChange={(e) => setPeriod(e.target.value)} style={{ padding: '8px 12px', borderRadius: 3, border: '1px solid var(--color-rule-strong)' }}>
            <option value="DAILY">Daily</option>
            <option value="WEEKLY">Weekly</option>
            <option value="MONTHLY">Monthly</option>
            <option value="ADHOC">Ad hoc (right now)</option>
          </select>
          <button className="btn btn-primary" onClick={handleGenerate} disabled={generating}>
            {generating ? 'Generating…' : 'Generate Now'}
          </button>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <h2>Sent Reports</h2>
        {reports.length === 0 ? (
          <div className="empty-state">No reports generated yet. Try "Generate Now" above.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Period</th>
                <th>Range</th>
                <th>Summary</th>
                <th>Status</th>
                <th>Attempts</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id}>
                  <td>{r.report_period}</td>
                  <td className="numeric muted">
                    {new Date(r.period_start).toLocaleDateString()} – {new Date(r.period_end).toLocaleDateString()}
                  </td>
                  <td style={{ maxWidth: 380, whiteSpace: 'pre-wrap' }}>{r.payload_summary}</td>
                  <td><StatusStamp status={r.status} /></td>
                  <td className="numeric">{r.attempt_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Layout>
  )
}
