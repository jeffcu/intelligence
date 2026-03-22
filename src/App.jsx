import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [briefings, setBriefings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/briefing/latest')
      .then(res => {
        if (!res.ok) throw new Error('Failed to lock onto API telemetry')
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
        <h1>Intelligence Tuning Console</h1>
        <p>Reviewing Raw Ingestion vs. LLM De-Hyped Outputs</p>
      </div>
      
      <div className="dashboard-grid">
        {briefings.map(article => (
          <div key={article.id} className="intel-card">
            <div className="intel-header">
              <div>
                <div className="meta-tags">
                  <span className="source-tag">{article.source}</span>
                  <span className="date-tag">{new Date(article.published_at).toLocaleString()}</span>
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
                <h4>Raw Summary / Extracted Content</h4>
                <p>{article.summary || 'No raw summary provided.'}</p>
              </div>
              <div className="col">
                <h4>De-Hyped Output (Flash 2.5)</h4>
                <p className="processed-text">{article.dehyped_summary || 'Processing failed.'}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

export default App
