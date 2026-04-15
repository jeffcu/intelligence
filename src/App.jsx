import { useState, useEffect, useMemo } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState('feed')
  const [showRaw, setShowRaw] = useState(false)
  
  const [briefings, setBriefings] = useState([])
  const [telemetry, setTelemetry] = useState(null)
  const [sources, setSources] = useState([])
  const [targets, setTargets] = useState([])
  const [originalGraphData, setOriginalGraphData] = useState(null)
  const [graphData, setGraphData] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  const [newSourceName, setNewSourceName] = useState('')
  const [newSourceUrl, setNewSourceUrl] = useState('')
  const [newTargetType, setNewTargetType] = useState('Macro')
  const [newTargetValue, setNewTargetValue] = useState('')

  const fetchSources = () => {
    fetch('/api/sources')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP Error: ${res.status}`)
        return res.json()
      })
      .then(data => setSources(Array.isArray(data) ? data : []))
      .catch(err => console.error('Failed to load sources matrix:', err))
  }

  const fetchTargets = () => {
    fetch('/api/targets')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP Error: ${res.status}`)
        return res.json()
      })
      .then(data => setTargets(Array.isArray(data) ? data : []))
      .catch(err => console.error('Failed to load target locks:', err))
  }

  const fetchGraphData = () => {
    fetch('/api/graph')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP Error: ${res.status}`)
        return res.json()
      })
      .then(data => {
        if (data && data.nodes && data.links) {
          setOriginalGraphData(data)
          setGraphData(data)
        }
      })
      .catch(err => console.error('Failed to load graph matrix:', err))
  }

  useEffect(() => {
    // Fetch operational telemetry stats
    fetch('/api/telemetry/stats')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP Error: ${res.status}`)
        return res.json()
      })
      .then(data => setTelemetry(data))
      .catch(err => console.error('Failed to load telemetry matrix:', err))

    // Fetch actual de-hyped briefings
    fetch('/api/briefing/latest')
      .then(res => {
        if (!res.ok) throw new Error('Failed to lock onto API briefing telemetry')
        return res.json()
      })
      .then(data => {
        if (data && Array.isArray(data.briefings)) {
          setBriefings(data.briefings)
        }
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
      
    // Fetch configurations
    fetchSources()
    fetchTargets()
    fetchGraphData()
  }, [])

  // Handle Graph Filtering by Node
  useEffect(() => {
    if (!originalGraphData) return;
    
    if (!selectedNode) {
      // Deep clone to prevent ForceGraph mutation conflicts
      setGraphData({
        nodes: originalGraphData.nodes.map(n => ({ ...n })),
        links: originalGraphData.links.map(l => ({ ...l }))
      });
      return;
    }

    const linkedNodes = new Set();
    linkedNodes.add(selectedNode);

    const filteredLinks = originalGraphData.links.filter(link => {
      // Handle react-force-graph mutability
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
      const targetId = typeof link.target === 'object' ? link.target.id : link.target;

      if (sourceId === selectedNode || targetId === selectedNode) {
        linkedNodes.add(sourceId);
        linkedNodes.add(targetId);
        return true;
      }
      return false;
    });

    const filteredNodes = originalGraphData.nodes.filter(node => linkedNodes.has(node.id));

    setGraphData({
      nodes: filteredNodes.map(n => ({ ...n })),
      links: filteredLinks.map(l => ({ ...l }))
    });
  }, [selectedNode, originalGraphData]);

  const handleToggleSource = (sourceName) => {
    fetch(`/api/sources/${encodeURIComponent(sourceName)}/toggle`, { method: 'PUT' })
      .then(() => fetchSources())
      .catch(err => console.error('Failed to toggle source:', err))
  }

  const handleAddSource = (e) => {
    e.preventDefault();
    if (!newSourceName || !newSourceUrl) return;

    fetch('/api/sources', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_name: newSourceName, feed_url: newSourceUrl })
    })
    .then(() => {
      setNewSourceName('')
      setNewSourceUrl('')
      fetchSources()
    })
    .catch(err => console.error('Failed to add source:', err))
  }

  const handleAddTarget = (e) => {
    e.preventDefault();
    if (!newTargetValue) return;

    fetch('/api/targets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_type: newTargetType, target_value: newTargetValue })
    })
    .then(() => {
      setNewTargetValue('')
      fetchTargets()
    })
    .catch(err => console.error('Failed to add target:', err))
  }

  const handleDeleteTarget = (id) => {
    fetch(`/api/targets/${id}`, { method: 'DELETE' })
      .then(() => fetchTargets())
      .catch(err => console.error('Failed to drop target lock:', err))
  }

  // Compute a sorted list of unique nodes for the dropdown
  const dropdownOptions = useMemo(() => {
    if (!originalGraphData) return [];
    return [...originalGraphData.nodes].sort((a, b) => a.id.localeCompare(b.id));
  }, [originalGraphData]);

  if (loading) return <h2>📡 Scanning frequencies for intelligence...</h2>
  if (error) return <h2>❌ Subspace interference: {error}</h2>

  return (
    <>
      <div className="header-panel">
        <h1>Intelligence Command Center</h1>
        <p>Real-Time Engine Telemetry & De-Hype Tuning Console</p>
      </div>

      <div className="tabs-nav">
        <button 
          className={`tab-btn ${activeTab === 'feed' ? 'tab-active' : ''}`}
          onClick={() => setActiveTab('feed')}
        >📡 Briefing Feed</button>
        <button 
          className={`tab-btn ${activeTab === 'graph' ? 'tab-active' : ''}`}
          onClick={() => setActiveTab('graph')}
        >🕸️ Knowledge Graph (Experimental)</button>
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

      {activeTab === 'feed' && (
        <>
          <div className="config-panels">
            <div className="target-panel">
              <h2>Sensor Target Locks</h2>
              <p style={{ color: '#888', fontSize: '0.85rem' }}>Active intelligence targets guiding the dynamic queries.</p>
              
              <div className="targets-container">
                {targets.map(tgt => (
                  <div key={tgt.id} className="target-pill">
                    <span className="target-type">[{tgt.target_type}]</span>
                    <span className="target-value">{tgt.target_value}</span>
                    <button className="delete-target-btn" onClick={() => handleDeleteTarget(tgt.id)}>×</button>
                  </div>
                ))}
              </div>

              <form className="add-form" onSubmit={handleAddTarget}>
                <select value={newTargetType} onChange={e => setNewTargetType(e.target.value)}>
                  <option value="Ticker">Ticker</option>
                  <option value="Company">Company</option>
                  <option value="Macro">Macro / Topic</option>
                  <option value="Person">Person</option>
                </select>
                <input 
                  type="text" 
                  placeholder="e.g. AAPL, Gold, Donald Trump"
                  value={newTargetValue}
                  onChange={e => setNewTargetValue(e.target.value)}
                  required
                />
                <button type="submit">Lock Target</button>
              </form>
            </div>

            <div className="governance-panel">
              <h2>Source Governance</h2>
              <table className="governance-table">
                <thead>
                  <tr>
                    <th>Source Name</th>
                    <th>Ingested</th>
                    <th>Chopped</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.slice(0, 4).map(src => (
                    <tr key={src.source_name}>
                      <td style={{ fontWeight: 'bold' }}>{src.source_name}</td>
                      <td>{src.total_articles_ingested}</td>
                      <td style={{ color: '#30d158' }}>{src.redundant_articles_chopped}</td>
                      <td>
                        <button 
                          className={`toggle-btn ${src.is_active ? 'toggle-inactive' : 'toggle-active'}`}
                          onClick={() => handleToggleSource(src.source_name)}
                        >
                          {src.is_active ? 'Disable' : 'Enable'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ color: '#888', fontSize: '0.8rem', marginTop: '0.5rem' }}>* Showing Top 4. Manage all in DB.</p>

              <form className="add-form" onSubmit={handleAddSource}>
                <input 
                  type="text" 
                  placeholder="New Source (e.g. Seeking Alpha)" 
                  value={newSourceName}
                  onChange={e => setNewSourceName(e.target.value)}
                  required
                />
                <input 
                  type="url" 
                  placeholder="RSS Feed URL" 
                  value={newSourceUrl}
                  onChange={e => setNewSourceUrl(e.target.value)}
                  required
                />
                <button type="submit">Add Feed</button>
              </form>
            </div>
          </div>
          
          <div className="intel-controls">
            <label>
              <input 
                type="checkbox" 
                checked={showRaw}
                onChange={e => setShowRaw(e.target.checked)}
              />
              Show Raw Input Extraction
            </label>
          </div>

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
                
                <div className={`intel-body ${showRaw ? 'show-raw' : 'hide-raw'}`}>
                  {showRaw && (
                    <div className="col">
                      <h4>Raw Input Extracted</h4>
                      <p>{article.summary || 'No raw summary provided.'}</p>
                    </div>
                  )}
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
      )}

      {activeTab === 'graph' && (
        <div className="graph-lab">
          <h2>Advanced Research Lab: Entity Knowledge Graph</h2>
          <p style={{ maxWidth: '800px' }}>
            The routing matrix is locked. <strong>{originalGraphData?.nodes?.length || 0} Entities/Sources</strong> and <strong>{originalGraphData?.links?.length || 0} Gravimetric Links</strong> are mapped.
            Click a node to center your scanner, or use the dropdown to isolate a target.
          </p>
          
          <div style={{ margin: '1rem 0', display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <select 
              value={selectedNode || ''} 
              onChange={e => setSelectedNode(e.target.value)}
              style={{ padding: '0.6rem', background: '#222', color: '#fff', border: '1px solid #00d2ff', borderRadius: '4px', minWidth: '250px' }}
            >
              <option value="">-- View Entire Matrix --</option>
              {dropdownOptions.map(node => (
                <option key={node.id} value={node.id}>
                  {node.id} [{node.group.toUpperCase()}]
                </option>
              ))}
            </select>
            {selectedNode && (
              <button 
                onClick={() => setSelectedNode(null)}
                style={{ padding: '0.6rem 1rem', background: '#ff453a', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}
              >
                Reset View
              </button>
            )}
          </div>

          <div style={{ marginTop: '1rem', border: '1px solid #333', borderRadius: '8px', overflow: 'hidden', backgroundColor: '#111' }}>
            {graphData?.nodes?.length > 0 ? (
              <ForceGraph2D
                graphData={graphData}
                nodeLabel={node => `${node.id} [${node.group.toUpperCase()}] - Gravity: ${node.val.toFixed(2)}`}
                linkLabel={link => `<div style="background:rgba(0,0,0,0.8); padding:5px; border-radius:4px; max-width: 300px; white-space: pre-wrap;">
                  <strong>Impact: ${link.impact}</strong><br/>
                  <em>${new Date(link.date).toLocaleDateString()}</em><br/>
                  ${link.title}
                </div>`}
                nodeAutoColorBy="group"
                nodeVal="val"
                linkDirectionalParticles={2}
                linkDirectionalParticleSpeed={d => d.impact * 0.001}
                width={1000}
                height={600}
                backgroundColor="#111111"
                onNodeClick={node => setSelectedNode(node.id)}
              />
            ) : (
              <p style={{ padding: '3rem' }}>Calculating gravitational node metrics... (No data yet)</p>
            )}
          </div>
        </div>
      )}
    </>
  )
}

export default App
