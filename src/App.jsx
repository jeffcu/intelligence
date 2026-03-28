import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [briefings, setBriefings] = useState([])
  const [telemetry, setTelemetry] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    // Fetch operational telemetry stats
    fetch('/api/telemetry/stats')
      .then(res => res.json())
      .then(data => setTelemetry(data))
      .catch(err => console.error('Failed to load telemetry matrix:', err))

    // Fetch actual de-hyped briefings
    fetch('/api/briefing/latest')
      .then(res => {
        if (!res.ok) throw new Error('Failed to lock onto API briefing telemetry')
        return res.json()
      })
      .then(data => {
        if (data.briefings) {
          setBriefings(data.briefings)
        }
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  if (loading) return <h2>📡 Scanning frequencies for intelligence...</h2>
  if (error) return <h2>❌ Subspace interference: {error}</h2>

  return (
    <>
      <div className="header-panel">
        <h1>Intelligence Command Center</h1>
        <p>Real-Time Engine Telemetry & De-Hype Tuning Console</p>
      </div>

      {telemetry && (
        <div className="telemetry-dashboard">
          <div className="stat-box">
            <div className="stat-label">Total Articles Stored</div>
            <div className="stat-value">{telemetry.total_stored}</div>
          </div>
          <div className="stat-box" style={{ border: '1px solid rgba(48, 209, 88, 0.4)' }}>
            <div className="stat-label" style={{ color: '#30d158' }}>Vectors Chopped</div>
            <div className="stat-value" style={{ color: '#30d158' }}>{telemetry.total_chopped}</div>
          </div>
          <div className="stat-box">
            <div className="stat-label">AI API Calls</div>
            <div className="stat-value">{telemetry.ai_calls}</div>
          </div>
          <div className="stat-box">
            <div className="stat-label">Total Tokens Burned</div>
            <div className="stat-value">{telemetry.total_tokens.toLocaleString()}</div>
          </div>
          <div className="stat-box">
            <div className="stat-label">Estimated Cost (USD)</div>
            <div className="stat-value">${telemetry.total_cost_usd.toFixed(4)}</div>
          </div>
          <div className="stat-box">
            <div className="stat-label">Avg Engine Latency</div>
            <div className="stat-value">{telemetry.avg_latency_ms}ms</div>
          </div>
        </div>
      )}
      
      <div className="dashboard-grid">
        {briefings.map(article => (
          <div key={article.id} className="intel-card">
            <div className="intel-header">
              <div>
                <div className="meta-tags">
                  <span className="source-tag">{article.source}</span>
                  <span className="date-tag">{new Date(article.published_at).toLocaleString()}</span>
                  {article.entities && article.entities.map((entity, idx) => (
                    <span key={idx} className="source-tag" style={{ background: '#2c2c54', color: '#70a1ff' }}>{entity}</span>
                  ))}
                </div>
                <h3 style={{ margin: '0.5rem 0' }}>
                  <a href={article.link} target="_blank" rel="noopener noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>
                    {article.title}
                  </a>
                </h3>
              </div>
              <div className="scores">
                <span className="score-badge hype">Hype: {article.hype_score}</span>
                <span className="score-badge impact">Impact: {article.impact_score}</span>
              </div>
            </div>
            
            <div className="intel-body">
              <div className="col">
                <h4>Raw Input Extracted</h4>
                <p>{article.summary || 'No raw summary provided.'}</p>
              </div>
              <div className="col">
                <h4>Objective Output (De-Hyped)</h4>
                <p className="processed-text">{article.dehyped_summary || 'Processing failed.'}</p>
                
                <div className="temporal-tags">
                  <h4>Current Facts</h4>
                  <ul className="temporal-list">
                    {article.current_facts && article.current_facts.length > 0 ? article.current_facts.map((fact, i) => (
                      <li key={i} className="fact-item">{fact}</li>
                    )) : <li>No facts extracted.</li>}
                  </ul>

                  <h4 style={{ marginTop: '1rem' }}>Future Opinions & Predictions</h4>
                  <ul className="temporal-list">
                    {article.future_opinions && article.future_opinions.length > 0 ? article.future_opinions.map((opinion, i) => (
                      <li key={i} className="opinion-item">{opinion}</li>
                    )) : <li>No predictions found.</li>}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

export default App
