import { useState, useEffect, useRef } from 'react'
import { api } from '../lib/api'

const POLL_INTERVAL_MS = 5000

export default function LiveActivityPanel() {
  const [events, setEvents] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const intervalRef = useRef(null)

  useEffect(() => {
    let cancelled = false

    async function fetchLive() {
      try {
        const data = await api.getLiveAttendance()
        if (!cancelled) {
          setEvents(data)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) setError(err.message)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchLive() // immediate first load, then poll
    intervalRef.current = setInterval(fetchLive, POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [])

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ marginBottom: 0 }}>Live Activity</h2>
        <span className="muted" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span className="live-feed-dot" />
          updates every 5s
        </span>
      </div>
      <div style={{ marginTop: 12 }}>
        {loading ? (
          <p className="muted">Loading live feed…</p>
        ) : error ? (
          <div className="error-banner">{error}</div>
        ) : events.length === 0 ? (
          <div className="empty-state">No recent attendance events.</div>
        ) : (
          <div className="live-feed">
            {events.map((e) => (
              <div key={e.id} className="live-feed-row">
                <span className="live-feed-time">
                  {new Date(e.event_ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
                <span className="live-feed-name">{e.full_name}</span>
                <span className="muted">{e.event_type.replace('_', ' ')}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
