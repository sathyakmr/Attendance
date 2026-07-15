import { useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useAuth } from '../lib/auth'

const ROLE_HOME = {
  EMPLOYEE: '/employee',
  MANAGER: '/manager',
  HR_ADMIN: '/hr',
  SUPER_ADMIN: '/hr',
}

export default function LoginPage() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await login(username, password)
      const dest = location.state?.from || ROLE_HOME[result.role] || '/'
      navigate(dest, { replace: true })
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.punchRow}>
          <div style={styles.punchHole} />
          <div style={styles.punchHole} />
        </div>
        <h1 style={styles.title}>Attendance Ledger</h1>
        <p className="muted" style={{ marginBottom: 24 }}>Sign in to clock in, review, or approve.</p>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <button type="submit" className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="muted" style={{ textAlign: 'center', marginTop: 8 }}>
          <Link to="/checkin">Face check-in kiosk →</Link>
        </p>
      </div>
    </div>
  )
}

const styles = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'var(--color-ink)',
  },
  card: {
    background: 'var(--color-paper-raised)',
    padding: '40px 36px',
    borderRadius: 8,
    width: 380,
    boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
    position: 'relative',
  },
  punchRow: {
    position: 'absolute',
    top: 0,
    left: '50%',
    transform: 'translate(-50%, -50%)',
    display: 'flex',
    gap: 60,
  },
  punchHole: {
    width: 16,
    height: 16,
    borderRadius: '50%',
    background: 'var(--color-ink)',
    boxShadow: 'inset 0 2px 3px rgba(0,0,0,0.5)',
  },
  title: {
    marginTop: 8,
    textAlign: 'center',
  },
}
