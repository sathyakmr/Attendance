import { useState } from 'react'
import Layout from '../components/Layout'
import { api } from '../lib/api'

const SUGGESTIONS = [
  'How many open anomaly flags are there right now?',
  'Who was late more than 3 times this month?',
  'Show me flagged events',
]

export default function QueryPage() {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function handleAsk(q) {
    const finalQuestion = q ?? question
    if (!finalQuestion.trim()) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.nlQuery(finalQuestion)
      setHistory((h) => [{ question: finalQuestion, ...result }, ...h])
      setQuestion('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="page-header">
        <div>
          <h1>Ask a Question</h1>
          <p>Natural-language queries over the attendance ledger, guarded and grounded.</p>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="card">
        <form
          onSubmit={(e) => { e.preventDefault(); handleAsk() }}
          style={{ display: 'flex', gap: 8 }}
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. how many anomalies are open right now"
            style={{ flex: 1, padding: '9px 11px', border: '1px solid var(--color-rule-strong)', borderRadius: 3 }}
          />
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Asking…' : 'Ask'}
          </button>
        </form>
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {SUGGESTIONS.map((s) => (
            <button key={s} className="btn btn-secondary" style={{ fontSize: 12 }} onClick={() => handleAsk(s)}>
              {s}
            </button>
          ))}
        </div>
      </div>

      {history.length > 0 && (
        <div className="card">
          <h2>History</h2>
          {history.map((item, i) => (
            <div key={i} style={{ marginBottom: 16, paddingBottom: 16, borderBottom: i < history.length - 1 ? '1px solid var(--color-rule)' : 'none' }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{item.question}</div>
              <div>{item.answer}</div>
              <div className="muted" style={{ marginTop: 4 }}>
                source: {item.source} {item.grounded ? '· grounded' : '· not grounded'}
              </div>
            </div>
          ))}
        </div>
      )}
    </Layout>
  )
}
