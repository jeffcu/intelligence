import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import './NewsView.css';

// Relative URLs — works in Vite dev (proxied) and Docker production (same origin)
const INTELLIGENCE_API = '';
const ONE_DAY_MS = 24 * 60 * 60 * 1000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(isoString) {
    const diff = Date.now() - new Date(isoString).getTime();
    if (isNaN(diff)) return '—';
    const mins = Math.floor(diff / 60000);
    if (mins < 1)  return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24)  return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}

function isOld(isoString) {
    return Date.now() - new Date(isoString).getTime() > ONE_DAY_MS;
}

function sortArticles(articles) {
    return [...articles].sort((a, b) => {
        const aOld = isOld(a.published_at);
        const bOld = isOld(b.published_at);
        if (aOld !== bOld) return aOld ? 1 : -1;
        const sigA = (a.impact_score || 0) - (a.hype_score || 0);
        const sigB = (b.impact_score || 0) - (b.hype_score || 0);
        return sigB - sigA;
    });
}

function truncate(text, maxLen = 160) {
    if (!text) return '';
    return text.length > maxLen ? text.slice(0, maxLen - 1) + '…' : text;
}

function signalColor(signal) {
    if (signal >= 40)  return '#05c46b';
    if (signal >= 10)  return '#feca57';
    if (signal >= -10) return '#aaa';
    return '#ff6b6b';
}

function isEquityTicker(id) {
    if (!id) return false;
    if (/^\d/.test(id)) return false;
    if (id.length >= 8) return false;
    if (id.length === 5 && /X$/i.test(id)) return false;
    return true;
}

// ---------------------------------------------------------------------------
// BriefingCard — single collapsible article row
// ---------------------------------------------------------------------------

const MATERIAL_EVENT_BADGES = {
    'Earnings Report':    { label: 'Earnings',    color: '#05c46b' },
    'Earnings Call':      { label: 'Earnings',    color: '#05c46b' },
    'Analyst Upgrade':    { label: '↑ Upgrade',   color: '#00f2fe' },
    'Analyst Downgrade':  { label: '↓ Downgrade', color: '#ff6b6b' },
    'Price Target Change':{ label: 'Price Target',color: '#feca57' },
    'Executive Change':   { label: 'Leadership',  color: '#feca57' },
    'Merger & Acquisition':{ label: 'M&A',        color: '#a29bfe' },
    'Regulatory Action':  { label: 'Regulatory',  color: '#fd79a8' },
    'Material Event':     { label: 'Material',    color: '#e17055' },
};

const BriefingCard = ({ b, isExpanded, onToggle }) => {
    const signal = (b.impact_score || 0) - (b.hype_score || 0);
    const aged   = isOld(b.published_at);
    const badge  = MATERIAL_EVENT_BADGES[b.event_type];

    return (
        <div
            className={`briefing-card ${isExpanded ? 'briefing-card--expanded' : ''} ${aged ? 'briefing-card--aged' : ''}`}
            onClick={onToggle}
        >
            <div className="card-collapsed">
                <span className="card-chevron">{isExpanded ? '▼' : '▶'}</span>
                <div className="card-main">
                    <div className="card-title-row">
                        <span className="card-title">{b.title}</span>
                        <div className="card-title-right">
                            {badge && (
                                <span className="event-badge" style={{ borderColor: badge.color, color: badge.color }}>
                                    {badge.label}
                                </span>
                            )}
                            <div className="card-target-pills">
                                {b.matched_targets && b.matched_targets.map((t, i) => (
                                    <span key={i} className="pill pill--target">🎯 {t}</span>
                                ))}
                            </div>
                        </div>
                    </div>
                    <div className="card-meta">
                        <span className="meta-source">{b.source}</span>
                        <span className="meta-dot">·</span>
                        <span className={`meta-time ${aged ? 'meta-time--aged' : ''}`}>{relativeTime(b.published_at)}</span>
                        <span className="meta-dot">·</span>
                        <span>Impact <strong className={b.impact_score >= 70 ? 'score-high' : ''}>{b.impact_score}</strong></span>
                        <span className="meta-dot">·</span>
                        <span>Signal <strong style={{ color: signalColor(signal) }}>{signal > 0 ? '+' : ''}{signal}</strong></span>
                    </div>
                    <div className="card-oneliner">{truncate(b.dehyped_summary)}</div>
                </div>
            </div>

            {isExpanded && (
                <div className="card-expanded" onClick={e => e.stopPropagation()}>
                    <div className="expanded-summary">{b.dehyped_summary}</div>
                    <div className="tag-row">
                        {b.entities && b.entities.map((e, i) => (
                            <span key={`e-${i}`} className="pill pill--entity">{e}</span>
                        ))}
                        {b.macro_themes && b.macro_themes.map((t, i) => (
                            <span key={`t-${i}`} className="pill pill--macro">{t}</span>
                        ))}
                    </div>
                    <div className="facts-opinions">
                        <div>
                            <h4 className="section-label">Extracted Facts</h4>
                            <ul className="fact-list">
                                {b.current_facts && b.current_facts.length > 0
                                    ? b.current_facts.map((f, i) => <li key={i}>{f}</li>)
                                    : <li className="empty-list">No hard facts extracted.</li>}
                            </ul>
                        </div>
                        <div>
                            <h4 className="section-label">Future Projections</h4>
                            <ul className="fact-list opinion-list">
                                {b.future_opinions && b.future_opinions.length > 0
                                    ? b.future_opinions.map((o, i) => <li key={i}>{o}</li>)
                                    : <li className="empty-list">No projections detected.</li>}
                            </ul>
                        </div>
                    </div>
                    <div className="expanded-footer">
                        <span className="hype-indicator">Hype: {b.hype_score}/100</span>
                        <a href={b.link} target="_blank" rel="noreferrer" className="source-link">
                            Source: {b.source} ↗
                        </a>
                    </div>
                </div>
            )}
        </div>
    );
};

// ---------------------------------------------------------------------------
// SummaryCard — AI digest card for one ticker or topic
// ---------------------------------------------------------------------------

// Parse **highlighted** phrases from AI-generated paragraph text.
// Splits on **...** markers and returns an array of React nodes.
// Sentences without markers render as plain text (graceful for old summaries).
const renderHighlighted = (text) => {
    if (!text) return null;
    const parts = text.split(/\*\*(.+?)\*\*/g);
    if (parts.length === 1) return text; // no markers — plain text
    return parts.map((part, i) =>
        i % 2 === 1
            ? <mark key={i} className="summary-hl">{part}</mark>
            : part
    );
};

const SENTIMENT_COLORS = {
    'Positive': '#05c46b',
    'Negative': '#ff6b6b',
    'Neutral':  '#888',
    'Mixed':    '#feca57',
};

const SummaryCard = ({ summary }) => {
    const [factsOpen, setFactsOpen] = useState(false);
    const sentColor = SENTIMENT_COLORS[summary.sentiment] || '#888';
    const isTicker  = !summary.target_type || summary.target_type === 'Ticker';
    const hasFacts  = summary.key_facts && summary.key_facts.length > 0;

    return (
        <div className={`summary-card ${summary.has_material_events ? 'summary-card--material' : ''}`}>
            <div className="summary-header">
                <span className={`summary-label ${isTicker ? 'summary-label--ticker' : 'summary-label--topic'}`}>
                    {summary.target_value}
                </span>
                <span className="summary-sentiment" style={{ color: sentColor }}>
                    {summary.sentiment}
                </span>
                {summary.has_material_events && (
                    <span className="summary-material-badge">Material</span>
                )}
                <span className="summary-meta">
                    {summary.article_count} article{summary.article_count !== 1 ? 's' : ''}
                    &nbsp;·&nbsp;{relativeTime(summary.generated_at)}
                </span>
            </div>

            <p className="summary-paragraph">{renderHighlighted(summary.paragraph)}</p>

            {hasFacts && (
                <button className="summary-facts-toggle" onClick={() => setFactsOpen(o => !o)}>
                    {factsOpen ? '▼' : '▶'} Key facts ({summary.key_facts.length})
                </button>
            )}
            {factsOpen && hasFacts && (
                <ul className="summary-facts">
                    {summary.key_facts.map((f, i) => <li key={i}>{f}</li>)}
                </ul>
            )}
        </div>
    );
};

// ---------------------------------------------------------------------------
// TargetsPanel — tracked tickers + topic chips + inline editor
// ---------------------------------------------------------------------------

const TARGET_TYPES = ['Ticker', 'Company', 'Topic', 'Macro', 'Person', 'Sector'];

const TargetsPanel = ({ targets, onRefresh }) => {
    const [editMode,   setEditMode]   = useState(false);
    const [newType,    setNewType]    = useState('Ticker');
    const [newValue,   setNewValue]   = useState('');
    const [adding,     setAdding]     = useState(false);
    const [deletingId, setDeletingId] = useState(null);
    const [addError,   setAddError]   = useState(null);

    const tickers    = targets.filter(t => t.target_type === 'Ticker');
    const nonTickers = targets.filter(t => t.target_type !== 'Ticker');

    const grouped = {};
    nonTickers.forEach(t => {
        const key = t.target_type || 'Topic';
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(t);
    });

    const handleAdd = async () => {
        const val = newValue.trim().toUpperCase().replace(/\s+/g, '');
        if (!val) return;
        setAdding(true);
        setAddError(null);
        try {
            const res = await fetch(`${INTELLIGENCE_API}/api/targets`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_type: newType, target_value: newType === 'Ticker' ? val : newValue.trim() }),
            });
            if (!res.ok) {
                const err = await res.json();
                setAddError(err.detail || 'Already tracked.');
            } else {
                setNewValue('');
                onRefresh();
            }
        } catch {
            setAddError('Could not reach Intelligence API.');
        } finally {
            setAdding(false);
        }
    };

    const handleDelete = async (id) => {
        setDeletingId(id);
        try {
            await fetch(`${INTELLIGENCE_API}/api/targets/${id}`, { method: 'DELETE' });
            onRefresh();
        } finally {
            setDeletingId(null);
        }
    };

    return (
        <div className={`targets-panel ${editMode ? 'targets-panel--editing' : ''}`}>

            {tickers.length > 0 && (
                <div className="targets-group">
                    <span className="targets-group-label">Tracking</span>
                    {tickers.map(t => (
                        <span key={t.id} className={`targets-chip targets-chip--ticker ${editMode ? 'targets-chip--editable' : ''}`}>
                            {t.target_value}
                            {editMode && (
                                <button
                                    className="chip-delete-btn"
                                    onClick={() => handleDelete(t.id)}
                                    disabled={deletingId === t.id}
                                >
                                    {deletingId === t.id ? '…' : '×'}
                                </button>
                            )}
                        </span>
                    ))}
                </div>
            )}

            {Object.entries(grouped).map(([type, items]) => (
                <div key={type} className="targets-group">
                    <span className="targets-group-label">{type}</span>
                    {items.map(t => (
                        <span key={t.id} className={`targets-chip targets-chip--topic ${editMode ? 'targets-chip--editable' : ''}`}>
                            {t.target_value}
                            {editMode && (
                                <button
                                    className="chip-delete-btn"
                                    onClick={() => handleDelete(t.id)}
                                    disabled={deletingId === t.id}
                                >
                                    {deletingId === t.id ? '…' : '×'}
                                </button>
                            )}
                        </span>
                    ))}
                </div>
            ))}

            <button
                className={`targets-edit-btn ${editMode ? 'targets-edit-btn--active' : ''}`}
                onClick={() => { setEditMode(e => !e); setAddError(null); setNewValue(''); }}
            >
                {editMode ? '✓ Done' : '✎ Edit'}
            </button>

            {editMode && (
                <div className="targets-add-form">
                    <select
                        value={newType}
                        onChange={e => setNewType(e.target.value)}
                        className="targets-type-select"
                    >
                        {TARGET_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <input
                        type="text"
                        value={newValue}
                        onChange={e => { setNewValue(e.target.value); setAddError(null); }}
                        onKeyDown={e => e.key === 'Enter' && handleAdd()}
                        placeholder={newType === 'Ticker' ? 'AAPL · NVDA · MSFT…' : 'Gold · Interest Rates · Elon Musk…'}
                        className="targets-add-input"
                        autoFocus
                    />
                    <button
                        onClick={handleAdd}
                        disabled={adding || !newValue.trim()}
                        className="targets-add-btn"
                    >
                        {adding ? '…' : '+ Add'}
                    </button>
                    {addError && <span className="targets-add-error">{addError}</span>}
                </div>
            )}
        </div>
    );
};

// ---------------------------------------------------------------------------
// CollapsibleSection
// ---------------------------------------------------------------------------

const CollapsibleSection = ({ title, icon, count, isOpen, onToggleOpen, emptyMessage, isEmpty, children }) => (
    <div className="news-section">
        <div className="section-header section-header--collapsible" onClick={onToggleOpen}>
            <span className="section-icon">{icon}</span>
            <span className="section-title">{title}</span>
            <span className="section-count">{count ?? 0}</span>
            <span className="section-collapse-chevron">{isOpen ? '▼' : '▶'}</span>
        </div>
        {isOpen && (
            <div className="section-body">
                {isEmpty
                    ? <p className="section-empty">{emptyMessage}</p>
                    : children}
            </div>
        )}
    </div>
);

// ---------------------------------------------------------------------------
// EarningsWidget
// ---------------------------------------------------------------------------

const EARNINGS_LABEL_STYLE = (delta) => {
    if (delta === 0)  return { color: '#05c46b', fontWeight: 700 };
    if (delta === 1)  return { color: '#feca57', fontWeight: 700 };
    if (delta <= 7 && delta > 0) return { color: '#feca57' };
    if (delta < 0)   return { color: '#888' };
    return { color: '#aaa' };
};

const EarningsWidget = () => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${INTELLIGENCE_API}/api/earnings-calendar`)
            .then(r => r.ok ? r.json() : [])
            .then(d => { setItems(Array.isArray(d) ? d : []); setLoading(false); })
            .catch(() => setLoading(false));
    }, []);

    return (
        <div className="fp-widget">
            <div className="fp-widget-header">
                <span className="fp-widget-icon">📅</span>
                <span className="fp-widget-title">Earnings Calendar</span>
            </div>
            {loading ? (
                <p className="fp-widget-empty">Loading…</p>
            ) : items.length === 0 ? (
                <p className="fp-widget-empty">No upcoming earnings for tracked tickers.</p>
            ) : (
                <div className="fp-widget-scroll">
                    <table className="fp-earnings-table">
                        <tbody>
                            {items.map(e => (
                                <tr key={e.ticker} className={e.delta <= 1 && e.delta >= 0 ? 'fp-earnings-row--soon' : ''}>
                                    <td className="fp-earnings-ticker">{e.ticker}</td>
                                    <td className="fp-earnings-when" style={EARNINGS_LABEL_STYLE(e.delta)}>{e.label}</td>
                                    <td className="fp-earnings-date">{e.date}</td>
                                    <td className="fp-earnings-est">{!e.confirmed ? 'est.' : ''}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

// ---------------------------------------------------------------------------
// IpoWidget
// ---------------------------------------------------------------------------

function highlightCompany(title, entities) {
    if (!entities || entities.length === 0) return title;
    for (const company of entities) {
        const idx = title.toLowerCase().indexOf(company.toLowerCase());
        if (idx === -1) continue;
        return (
            <>
                {title.slice(0, idx)}
                <strong className="fp-ipo-company">{title.slice(idx, idx + company.length)}</strong>
                {title.slice(idx + company.length)}
            </>
        );
    }
    return title;
}

const IpoWidget = () => {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${INTELLIGENCE_API}/api/ipo-events`)
            .then(r => r.ok ? r.json() : [])
            .then(d => { setItems(Array.isArray(d) ? d : []); setLoading(false); })
            .catch(() => setLoading(false));
    }, []);

    return (
        <div className="fp-widget">
            <div className="fp-widget-header">
                <span className="fp-widget-icon">🚀</span>
                <span className="fp-widget-title">IPO Pipeline</span>
            </div>
            {loading ? (
                <p className="fp-widget-empty">Loading…</p>
            ) : items.length === 0 ? (
                <p className="fp-widget-empty">No IPO filings or events in recent feed.</p>
            ) : (
                <div className="fp-widget-scroll">
                    <ul className="fp-widget-list">
                        {items.map(ev => (
                            <li key={ev.id} className="fp-widget-ipo-item">
                                <a href={ev.link} target="_blank" rel="noreferrer" className="fp-widget-ipo-title">
                                    {highlightCompany(ev.title, ev.entities)}
                                </a>
                                <span className="fp-widget-time">{relativeTime(ev.published_at)}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};

// ---------------------------------------------------------------------------
// Analytics helpers
// ---------------------------------------------------------------------------

function qualityColor(rate) {
    if (rate >= 60) return '#05c46b';
    if (rate >= 30) return '#feca57';
    return '#ff6b6b';
}

function hupeColor(score) {
    if (score == null) return '#888';
    if (score <= 30) return '#05c46b';
    if (score <= 60) return '#feca57';
    return '#ff6b6b';
}

const NODE_COLORS = {
    focus:  '#E2B254',  // gold  — tracked companies/symbols/topics
    theme:  '#9b59b6',  // purple — macro themes
    source: '#4a9ebe',  // blue   — news sources
};

// Builds a force-graph dataset from briefings + tracked targets.
// mode: 'focus-themes' | 'focus-sources' | 'themes-sources'
function buildGraphForMode(mode, articles, targets) {
    const trackedSet = new Set((targets || []).map(t => t.target_value.toLowerCase()));

    const nodes   = {};
    const linkMap = {};

    const addNode = (id, group, primary, impact, ref) => {
        if (!id) return;
        if (!nodes[id]) nodes[id] = { id, group, val: 0, count: 0, primary, articles: [] };
        nodes[id].val   += Math.max(1, impact) / 15;
        nodes[id].count += 1;
        if (nodes[id].articles.length < 12) nodes[id].articles.push(ref);
    };

    const addLink = (src, tgt, weight) => {
        if (!src || !tgt || src === tgt) return;
        const key = `${src}|||${tgt}`;
        if (!linkMap[key]) linkMap[key] = { source: src, target: tgt, weight: 0 };
        linkMap[key].weight += weight;
    };

    articles.forEach(article => {
        const matched = article.matched_targets || [];
        const themes  = article.macro_themes   || [];
        const source  = article.source         || 'Unknown';
        const impact  = article.impact_score   || 10;
        const ref = { title: article.title, link: article.link, source, impact };

        // Focus items = targets explicitly matched to this article (most reliable)
        // Fall back to entities that happen to share a name with a tracked target
        const focusItems = matched.length > 0
            ? matched
            : (article.entities || []).filter(e => trackedSet.has(e.toLowerCase()));

        if (mode === 'focus-themes') {
            if (focusItems.length === 0 || themes.length === 0) return;
            focusItems.forEach(f => addNode(f, 'focus', true,  impact, ref));
            themes.forEach(t      => addNode(t, 'theme', false, impact, ref));
            focusItems.forEach(f  => themes.forEach(t => addLink(f, t, 1)));

        } else if (mode === 'focus-sources') {
            if (focusItems.length === 0) return;
            focusItems.forEach(f => addNode(f, 'focus',  true,  impact, ref));
            addNode(source,        'source', false, impact, ref);
            focusItems.forEach(f  => addLink(f, source, impact));

        } else if (mode === 'themes-sources') {
            if (themes.length === 0) return;
            themes.forEach(t => addNode(t, 'theme',  true,  impact, ref));
            addNode(source,     'source', false, impact, ref);
            themes.forEach(t  => addLink(t, source, 1));
        }
    });

    const links     = Object.values(linkMap);
    const connected = new Set(links.flatMap(l => [l.source, l.target]));
    // Keep primary nodes even if isolated (they may have articles but no cross-links yet)
    return {
        nodes: Object.values(nodes).filter(n => connected.has(n.id) || n.primary),
        links,
    };
}

// ---------------------------------------------------------------------------
// ThemeMixView
// ---------------------------------------------------------------------------

const ThemeMixView = ({ articles }) => {
    const themeCounts = useMemo(() => {
        const counts = {};
        articles.forEach(a => (a.macro_themes || []).forEach(t => { counts[t] = (counts[t] || 0) + 1; }));
        return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 18);
    }, [articles]);

    const max = themeCounts[0]?.[1] || 1;

    return (
        <div className="theme-mix">
            <p className="analytics-section-desc">
                AI-extracted macro themes across the last {articles.length} articles — derived from Gemini entity/theme tagging.
            </p>
            <div className="theme-mix-bars">
                {themeCounts.map(([theme, count]) => (
                    <div key={theme} className="theme-mix-row">
                        <span className="theme-mix-label">{theme}</span>
                        <div className="theme-mix-bar-wrap">
                            <div className="theme-mix-bar" style={{ width: `${(count / max) * 100}%` }} />
                        </div>
                        <span className="theme-mix-count">{count}</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

// ---------------------------------------------------------------------------
// SourceFiltersView — enable/disable source toggles
// ---------------------------------------------------------------------------

const SourceFiltersView = ({ sources, onToggleSource }) => {
    if (sources.length === 0) return <p className="analytics-empty">No sources configured.</p>;
    return (
        <div className="source-filters-grid">
            {[...sources].sort((a, b) => a.source_name.localeCompare(b.source_name)).map(s => (
                <button
                    key={s.source_name}
                    className={`source-filter-chip ${s.is_active ? 'source-filter-chip--active' : 'source-filter-chip--inactive'}`}
                    onClick={() => onToggleSource(s.source_name)}
                >
                    <span className="source-filter-dot" style={{ background: s.is_active ? '#05c46b' : '#444' }} />
                    {s.source_name}
                </button>
            ))}
        </div>
    );
};

// ---------------------------------------------------------------------------
// SourceAnalyticsView — performance table
// ---------------------------------------------------------------------------

const SourceAnalyticsView = ({ sources, onToggleSource }) => {
    const enriched = useMemo(() => sources.map(s => {
        const ingested  = s.total_articles_ingested    || 0;
        const chopped   = s.redundant_articles_chopped || 0;
        const deflected = s.deflected_articles         || 0;
        const passed    = Math.max(0, ingested - chopped - deflected);
        const passRate  = ingested > 0 ? (passed  / ingested) * 100 : 0;
        const chopRate  = ingested > 0 ? (chopped / ingested) * 100 : 0;
        return { ...s, passed, passRate, chopRate };
    }).sort((a, b) => b.passRate - a.passRate || b.passed - a.passed), [sources]);

    if (sources.length === 0) return <p className="analytics-empty">No source data available.</p>;

    return (
        <div className="source-analytics">
            <p className="analytics-section-desc">
                Ranked by pass rate — share of ingested articles that cleared quality gates and reached the feed.
                Low pass rate means high duplication or irrelevance. High hype score means sensationalist writing.
            </p>
            <table className="source-table">
                <thead>
                    <tr>
                        <th>Source</th>
                        <th className="col-num">Ingested</th>
                        <th className="col-num">In Feed</th>
                        <th>Signal Quality</th>
                        <th className="col-num">Dedup %</th>
                        <th className="col-num">Avg Hype</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody>
                    {enriched.map(s => (
                        <tr key={s.source_name} className={`source-row ${!s.is_active ? 'source-row--inactive' : ''}`}>
                            <td className="source-name-cell">
                                <span className="source-active-dot" style={{ background: s.is_active ? '#05c46b' : '#444' }} />
                                {s.source_name}
                            </td>
                            <td className="col-num">{s.total_articles_ingested?.toLocaleString() || 0}</td>
                            <td className="col-num source-passed">{s.passed.toLocaleString()}</td>
                            <td className="source-quality-cell">
                                <div className="quality-bar-wrap">
                                    <div className="quality-bar" style={{ width: `${Math.round(s.passRate)}%`, background: qualityColor(s.passRate) }} />
                                    <span className="quality-label">{Math.round(s.passRate)}%</span>
                                </div>
                            </td>
                            <td className="col-num">{Math.round(s.chopRate)}%</td>
                            <td className="col-num" style={{ color: hupeColor(s.average_hype_score) }}>
                                {s.average_hype_score != null ? Math.round(s.average_hype_score) : '—'}
                            </td>
                            <td>
                                <button
                                    className={`source-toggle-btn ${s.is_active ? 'source-toggle-btn--live' : 'source-toggle-btn--paused'}`}
                                    onClick={() => onToggleSource(s.source_name)}
                                >
                                    {s.is_active ? 'Pause' : 'Enable'}
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

// ---------------------------------------------------------------------------
// GraphView
// ---------------------------------------------------------------------------

const GRAPH_MODES = [
    { id: 'focus-themes',  label: 'Focus → Themes',   desc: 'Your tracked companies and topics (gold) surrounded by the AI-extracted themes they generate. Reveals what narratives each target is driving.' },
    { id: 'focus-sources', label: 'Focus → Sources',  desc: 'Your tracked targets (gold) surrounded by the sources covering them. Shows which outlets are most active on each of your positions.' },
    { id: 'themes-sources',label: 'Themes → Sources', desc: 'Macro themes (purple) surrounded by sources that produce them. Reveals each outlet\'s editorial focus and topic coverage.' },
];

const GraphView = ({ articles, targets }) => {
    const fgRef      = useRef();
    const zoomRef    = useRef(1);   // current zoom level, updated by onZoom
    const [graphMode,  setGraphMode]  = useState('focus-themes');
    const [drillNode,  setDrillNode]  = useState(null);   // zoomed/dimmed state
    const [popupNode,  setPopupNode]  = useState(null);   // article popup

    const handleZoomIn  = useCallback(() => {
        const next = Math.min(zoomRef.current * 1.5, 12);
        fgRef.current?.zoom(next, 250);
    }, []);

    const handleZoomOut = useCallback(() => {
        const next = Math.max(zoomRef.current / 1.5, 0.1);
        fgRef.current?.zoom(next, 250);
    }, []);

    // Full graph for the active mode
    const fullGraph = useMemo(
        () => buildGraphForMode(graphMode, articles, targets),
        [graphMode, articles, targets]
    );

    // Set of direct neighbors of the drilled node (for dimming non-neighbors)
    const neighborSet = useMemo(() => {
        if (!drillNode) return null;
        const set = new Set([drillNode.id]);
        fullGraph.links.forEach(l => {
            const src = typeof l.source === 'object' ? l.source.id : l.source;
            const tgt = typeof l.target === 'object' ? l.target.id : l.target;
            if (src === drillNode.id) set.add(tgt);
            if (tgt === drillNode.id) set.add(src);
        });
        return set;
    }, [drillNode, fullGraph]);

    // Spread nodes out whenever the graph data or mode changes
    useEffect(() => {
        if (!fgRef.current) return;
        const timer = setTimeout(() => {
            const fg = fgRef.current;
            if (!fg) return;
            const charge = fg.d3Force('charge');
            const link   = fg.d3Force('link');
            if (charge) charge.strength(-320);
            if (link)   link.distance(110);
            fg.d3ReheatSimulation();
        }, 100);
        return () => clearTimeout(timer);
    }, [graphMode, fullGraph]);

    // Node painter — handles normal, drilled-center, neighbor, and dimmed states
    const paintNode = useCallback((node, ctx, globalScale) => {
        const isDrilling = !!neighborSet;
        const isCenter   = isDrilling && node.id === drillNode?.id;
        const isNeighbor = isDrilling && !isCenter && neighborSet.has(node.id);
        const isDimmed   = isDrilling && !isCenter && !isNeighbor;

        const isPrimary = node.primary;
        const r = isPrimary
            ? Math.max(8, Math.min(32, Math.sqrt(Math.max(1, node.val)) * 4.5))
            : Math.max(3, Math.min(13, Math.sqrt(Math.max(1, node.val)) * 2.5));

        ctx.globalAlpha = isDimmed ? 0.08 : (isPrimary ? 1 : 0.75);

        ctx.beginPath();
        ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
        ctx.fillStyle = NODE_COLORS[node.group] || '#888';
        ctx.fill();

        // Center node gets a bright ring
        if (isCenter) {
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 2.5 / globalScale;
            ctx.stroke();
        } else if (isPrimary && !isDimmed) {
            ctx.strokeStyle = 'rgba(255,255,255,0.2)';
            ctx.lineWidth = 1.5 / globalScale;
            ctx.stroke();
        }

        ctx.globalAlpha = isDimmed ? 0.08 : 1;

        // Labels: primary always shown; secondary shown when zoomed or prominent
        const showLabel = isCenter || isPrimary || isNeighbor || globalScale > 1.8 || node.val > 12;
        if (showLabel) {
            const fs = (isPrimary || isCenter)
                ? Math.max(10, Math.min(15, 13 / globalScale))
                : Math.max(7,  Math.min(10, 9  / globalScale));
            const label = node.id.length > 26 ? node.id.slice(0, 24) + '…' : node.id;
            ctx.font         = `${(isPrimary || isCenter) ? 'bold ' : ''}${fs}px Inter,sans-serif`;
            ctx.textAlign    = 'center';
            ctx.textBaseline = 'top';
            ctx.fillStyle    = (isPrimary || isCenter) ? '#fff' : 'rgba(200,200,200,0.85)';
            ctx.fillText(label, node.x, node.y + r + 2 / globalScale);
        }

        ctx.globalAlpha = 1;
    }, [neighborSet, drillNode]);

    const handleNodeClick = useCallback((node) => {
        if (drillNode?.id === node.id) {
            // Clicking the drilled node again = back
            setDrillNode(null);
            setPopupNode(null);
            fgRef.current?.zoom(1, 500);
            return;
        }
        setDrillNode(node);
        if (node.articles?.length > 0) setPopupNode(node);
        // Zoom and center on the clicked node
        setTimeout(() => {
            if (fgRef.current && node.x != null) {
                fgRef.current.centerAt(node.x, node.y, 400);
                fgRef.current.zoom(3, 400);
            }
        }, 30);
    }, [drillNode]);

    const handleBack = useCallback(() => {
        setDrillNode(null);
        setPopupNode(null);
        fgRef.current?.zoom(1, 500);
    }, []);

    const modeDesc = GRAPH_MODES.find(m => m.id === graphMode)?.desc || '';

    return (
        <div className="analytics-graph">
            <h3 className="analytics-section-title">Knowledge Graph</h3>

            <div className="graph-mode-tabs">
                {GRAPH_MODES.map(m => (
                    <button
                        key={m.id}
                        className={`graph-mode-tab ${graphMode === m.id ? 'graph-mode-tab--active' : ''}`}
                        onClick={() => { setGraphMode(m.id); setDrillNode(null); setPopupNode(null); }}
                    >{m.label}</button>
                ))}
            </div>
            <p className="analytics-section-desc">{modeDesc}</p>

            <div className="graph-canvas-wrap">
                {drillNode && (
                    <button className="graph-back-btn" onClick={handleBack}>
                        ← Back
                    </button>
                )}
                <div className="graph-zoom-controls">
                    <button className="graph-zoom-btn" onClick={handleZoomIn}  title="Zoom in">+</button>
                    <button className="graph-zoom-btn" onClick={handleZoomOut} title="Zoom out">−</button>
                </div>
                <div className="graph-canvas">
                    {fullGraph?.nodes?.length > 0 ? (
                        <ForceGraph2D
                            ref={fgRef}
                            graphData={fullGraph}
                            nodeLabel={node => `${node.id} · ${node.count} article${node.count !== 1 ? 's' : ''}`}
                            nodeCanvasObject={paintNode}
                            nodeCanvasObjectMode={() => 'replace'}
                            linkWidth={link => Math.max(0.4, Math.min(4, (link.weight || 1) * 0.4))}
                            linkColor={link => {
                                if (!neighborSet) return 'rgba(120,120,120,0.25)';
                                const src = typeof link.source === 'object' ? link.source.id : link.source;
                                const tgt = typeof link.target === 'object' ? link.target.id : link.target;
                                const active = neighborSet.has(src) && neighborSet.has(tgt);
                                return active ? 'rgba(200,200,200,0.5)' : 'rgba(80,80,80,0.08)';
                            }}
                            linkDirectionalParticles={1}
                            linkDirectionalParticleSpeed={0.004}
                            width={960}
                            height={540}
                            backgroundColor="#0d0d0d"
                            onNodeClick={handleNodeClick}
                            onZoom={({ k }) => { zoomRef.current = k; }}
                        />
                    ) : (
                        <p className="graph-empty">No graph data yet — run the ingestor to populate connections.</p>
                    )}
                </div>
            </div>

            {/* Article popup — dismissable independently of drill state */}
            {popupNode && (
                <div className="graph-popup-backdrop" onClick={() => setPopupNode(null)}>
                    <div className="graph-popup" onClick={e => e.stopPropagation()}>
                        <div className="graph-popup-hd">
                            <span className="graph-node-badge" style={{ background: NODE_COLORS[popupNode.group] || '#666' }}>
                                {popupNode.group}
                            </span>
                            <strong className="graph-panel-name">{popupNode.id}</strong>
                            <span className="graph-panel-count">{popupNode.count} article{popupNode.count !== 1 ? 's' : ''}</span>
                            <button className="graph-panel-close" onClick={() => setPopupNode(null)}>✕</button>
                        </div>
                        <div className="graph-article-list">
                            {popupNode.articles.map((a, i) => (
                                <a key={i} href={a.link} target="_blank" rel="noreferrer" className="graph-article-item">
                                    <span className="graph-article-source">{a.source}</span>
                                    <span className="graph-article-title">{a.title}</span>
                                    <span className="graph-article-impact" style={{ color: signalColor(a.impact) }}>
                                        +{a.impact}
                                    </span>
                                </a>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

// ---------------------------------------------------------------------------
// AnalyticsView
// ---------------------------------------------------------------------------

const AnalyticsSection = ({ title, defaultOpen = true, children }) => {
    const [open, setOpen] = useState(defaultOpen);
    return (
        <div className="analytics-section">
            <button className="analytics-section-hd" onClick={() => setOpen(o => !o)}>
                <span className="analytics-section-title">{title}</span>
                <span className="analytics-section-chevron">{open ? '▼' : '▶'}</span>
            </button>
            {open && <div className="analytics-section-body">{children}</div>}
        </div>
    );
};

const AnalyticsView = ({ sources, onToggleSource, articles, targets }) => (
    <div className="analytics-view">
        <AnalyticsSection title="Filters">
            <SourceFiltersView sources={sources} onToggleSource={onToggleSource} />
        </AnalyticsSection>
        <AnalyticsSection title="News Mix by Theme">
            <ThemeMixView articles={articles} />
        </AnalyticsSection>
        <AnalyticsSection title="Knowledge Graph" defaultOpen={false}>
            <GraphView articles={articles} targets={targets} />
        </AnalyticsSection>
        <AnalyticsSection title="Performance by Source" defaultOpen={false}>
            <SourceAnalyticsView sources={sources} onToggleSource={onToggleSource} />
        </AnalyticsSection>
    </div>
);

// ---------------------------------------------------------------------------
// FrontPageView — newspaper layout
// ---------------------------------------------------------------------------

const FrontPageView = ({ portfolioArticles, topicArticles, tickerSummaries, topicSummaries, expandedIds, toggleCard }) => {
    const allArticles = sortArticles([...portfolioArticles, ...topicArticles]);

    const sortedTickerSummaries = [...tickerSummaries].sort((a, b) => {
        if (a.has_material_events !== b.has_material_events) return a.has_material_events ? -1 : 1;
        return (b.article_count || 0) - (a.article_count || 0);
    });

    const sortedTopicSummaries = [...topicSummaries].sort((a, b) => {
        if (a.has_material_events !== b.has_material_events) return a.has_material_events ? -1 : 1;
        return (b.article_count || 0) - (a.article_count || 0);
    });

    const lead      = allArticles[0];
    const featured  = allArticles.slice(1, 4);
    const secondary = allArticles.slice(4);

    return (
        <div className="front-page-view">
            <div className="fp-masthead">
                <div className="fp-date">
                    {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                </div>
                <div className="fp-rule fp-rule--thick" />
            </div>

            {lead && (
                <section className="fp-section">
                    <div className="fp-stories-top">
                        <div className="fp-lead">
                            <div className="fp-byline">
                                <span className="meta-source">{lead.source}</span>
                                <span className="meta-dot">·</span>
                                <span>{relativeTime(lead.published_at)}</span>
                                {lead.matched_targets && lead.matched_targets.slice(0, 3).map((t, i) => (
                                    <span key={i} className="pill pill--target" style={{ marginLeft: '0.3rem' }}>🎯 {t}</span>
                                ))}
                                <span className="fp-signal" style={{ color: signalColor((lead.impact_score || 0) - (lead.hype_score || 0)), marginLeft: 'auto' }}>
                                    Signal {(lead.impact_score || 0) - (lead.hype_score || 0) > 0 ? '+' : ''}{(lead.impact_score || 0) - (lead.hype_score || 0)}
                                </span>
                            </div>
                            <h2 className="fp-lead-headline">
                                <a href={lead.link} target="_blank" rel="noreferrer">{lead.title}</a>
                            </h2>
                            <p className="fp-lead-lede">{lead.dehyped_summary}</p>
                            {lead.current_facts && lead.current_facts.length > 0 && (
                                <ul className="fp-facts">
                                    {lead.current_facts.slice(0, 4).map((f, i) => <li key={i}>{f}</li>)}
                                </ul>
                            )}
                            <div className="fp-lead-widgets">
                                <EarningsWidget />
                                <IpoWidget />
                            </div>
                        </div>

                        {featured.length > 0 && (
                            <div className="fp-featured-col">
                                {featured.map(b => {
                                    const sig = (b.impact_score || 0) - (b.hype_score || 0);
                                    return (
                                        <div key={b.id} className="fp-featured-story">
                                            <div className="fp-byline">
                                                <span className="meta-source">{b.source}</span>
                                                <span className="meta-dot">·</span>
                                                <span>{relativeTime(b.published_at)}</span>
                                                <span className="fp-signal" style={{ color: signalColor(sig), marginLeft: 'auto' }}>
                                                    {sig > 0 ? '+' : ''}{sig}
                                                </span>
                                            </div>
                                            <h4 className="fp-story-headline">
                                                <a href={b.link} target="_blank" rel="noreferrer">{b.title}</a>
                                            </h4>
                                            <p className="fp-story-lede">{truncate(b.dehyped_summary, 140)}</p>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </section>
            )}

            {sortedTickerSummaries.length > 0 && (
                <section className="fp-section">
                    <div className="fp-rule" />
                    <h3 className="fp-section-title">Ticker Briefings</h3>
                    <div className="fp-summaries-grid">
                        {sortedTickerSummaries.map(s => (
                            <SummaryCard key={s.target_value} summary={s} />
                        ))}
                    </div>
                </section>
            )}

            {sortedTopicSummaries.length > 0 && (
                <section className="fp-section">
                    <div className="fp-rule" />
                    <h3 className="fp-section-title">Topic Briefings</h3>
                    <div className="fp-summaries-grid">
                        {sortedTopicSummaries.map(s => (
                            <SummaryCard key={s.target_value} summary={s} />
                        ))}
                    </div>
                </section>
            )}

            {secondary.length > 0 && (
                <section className="fp-section">
                    <div className="fp-rule" />
                    <h3 className="fp-section-title">More Stories</h3>
                    <div className="fp-secondary-grid">
                        {secondary.map(b => {
                            const sig = (b.impact_score || 0) - (b.hype_score || 0);
                            return (
                                <div
                                    key={b.id}
                                    className="fp-secondary-story"
                                    onClick={() => toggleCard(b.id)}
                                    style={{ cursor: 'pointer' }}
                                >
                                    <div className="fp-byline">
                                        <span className="meta-source">{b.source}</span>
                                        <span className="fp-signal" style={{ color: signalColor(sig), marginLeft: 'auto' }}>
                                            {sig > 0 ? '+' : ''}{sig}
                                        </span>
                                    </div>
                                    <h5 className="fp-story-headline fp-story-headline--sm">
                                        <a href={b.link} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}>{b.title}</a>
                                    </h5>
                                    {expandedIds.has(b.id) && (
                                        <p className="fp-story-lede">{b.dehyped_summary}</p>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </section>
            )}

            {allArticles.length === 0 && sortedTickerSummaries.length === 0 && sortedTopicSummaries.length === 0 && (
                <p className="section-empty" style={{ padding: '2rem 0' }}>
                    No intelligence yet. Add tickers or topics above, then run the ingestor.
                </p>
            )}
        </div>
    );
};

// ---------------------------------------------------------------------------
// NewsView — main component
// ---------------------------------------------------------------------------

const REFRESH_INTERVAL_MS = 5 * 60 * 1000;

const NewsView = () => {
    const [briefings,  setBriefings]  = useState([]);
    const [targets,    setTargets]    = useState([]);
    const [summaries,  setSummaries]  = useState([]);
    const [loading,    setLoading]    = useState(true);
    const [error,      setError]      = useState(null);
    const [expandedIds, setExpandedIds] = useState(new Set());
    const [aiStats,    setAiStats]    = useState(null);

    const [sources, setSources] = useState([]);

    const [targetsOpen, setTargetsOpen] = useState(true);
    const [viewMode,    setViewMode]    = useState('front-page');

    const [portSummariesOpen,  setPortSummariesOpen]  = useState(true);
    const [portArticlesOpen,   setPortArticlesOpen]   = useState(false);
    const [topicSummariesOpen, setTopicSummariesOpen] = useState(true);
    const [topicArticlesOpen,  setTopicArticlesOpen]  = useState(false);

    const toggleCard = (id) => {
        setExpandedIds(prev => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    };

    const fetchData = useCallback(async (silent = false) => {
        try {
            if (!silent) setLoading(true);
            setError(null);
            const [briefRes, targetRes, summaryRes] = await Promise.all([
                fetch(`${INTELLIGENCE_API}/api/briefing/latest?limit=100`),
                fetch(`${INTELLIGENCE_API}/api/targets`),
                fetch(`${INTELLIGENCE_API}/api/summaries/latest`),
            ]);
            if (!briefRes.ok) throw new Error('Intelligence API is offline or unreachable.');

            const briefData   = await briefRes.json();
            const targetData  = targetRes.ok  ? await targetRes.json()  : [];
            const summaryData = summaryRes.ok ? await summaryRes.json() : [];

            setBriefings(Array.isArray(briefData.briefings) ? briefData.briefings : []);
            setTargets(Array.isArray(targetData) ? targetData : []);
            setSummaries(Array.isArray(summaryData) ? summaryData : []);
        } catch (err) {
            setError(err.message);
        } finally {
            if (!silent) setLoading(false);
        }
    }, []);

    const fetchAiStats = useCallback(async () => {
        try {
            const res = await fetch(`${INTELLIGENCE_API}/api/telemetry/stats`);
            if (res.ok) setAiStats(await res.json());
        } catch { /* non-fatal */ }
    }, []);

    const fetchAnalytics = useCallback(async () => {
        try {
            const sourcesRes = await fetch(`${INTELLIGENCE_API}/api/sources`);
            if (sourcesRes.ok) {
                const s = await sourcesRes.json();
                setSources(Array.isArray(s) ? s : []);
            }
        } catch { /* non-fatal */ }
    }, []);

    const handleToggleSource = useCallback(async (sourceName) => {
        try {
            await fetch(`${INTELLIGENCE_API}/api/sources/${encodeURIComponent(sourceName)}/toggle`, { method: 'PUT' });
            fetchAnalytics();
        } catch { /* non-fatal */ }
    }, [fetchAnalytics]);

    useEffect(() => {
        fetchData();
        fetchAiStats();
        fetchAnalytics();
    }, [fetchData, fetchAiStats, fetchAnalytics]);

    useEffect(() => {
        const id = setInterval(() => { fetchData(true); fetchAiStats(); }, REFRESH_INTERVAL_MS);
        return () => clearInterval(id);
    }, [fetchData, fetchAiStats]);

    const tickerSet = new Set(
        targets.filter(t => t.target_type === 'Ticker').map(t => t.target_value.toUpperCase())
    );
    const topicSet = new Set(
        targets.filter(t => t.target_type !== 'Ticker').map(t => t.target_value)
    );

    const isPortfolioArticle = (b) =>
        tickerSet.size > 0 && (b.matched_targets || []).some(t => tickerSet.has(t.toUpperCase()));
    const isTopicArticle = (b) =>
        !isPortfolioArticle(b) && topicSet.size > 0 && (b.matched_targets || []).some(t => topicSet.has(t));
    const meetsSignal = (b) => ((b.impact_score || 0) - (b.hype_score || 0)) >= 0;

    const portfolioArticles = sortArticles(briefings.filter(b => isPortfolioArticle(b) && meetsSignal(b)));
    const topicArticles     = sortArticles(briefings.filter(b => isTopicArticle(b)     && meetsSignal(b)));

    const tickerSummaries = Object.values(
        summaries
            .filter(s => !s.target_type || s.target_type === 'Ticker')
            .reduce((acc, s) => {
                if (!acc[s.target_value] || s.generated_at > acc[s.target_value].generated_at)
                    acc[s.target_value] = s;
                return acc;
            }, {})
    );
    const topicSummaries  = summaries.filter(s => s.target_type  && s.target_type !== 'Ticker');

    const tickerCount    = targets.filter(t => t.target_type === 'Ticker').length;
    const nonTickerCount = targets.filter(t => t.target_type !== 'Ticker').length;

    return (
        <div className="news-view-container">

            <div className="news-header">
                <div className="intel-header-brand">
                    <span className="intel-brand-name">Intelligence</span>
                    <nav className="intel-nav">
                        <button
                            className={`intel-nav-tab ${viewMode === 'front-page' ? 'intel-nav-tab--active' : ''}`}
                            onClick={() => setViewMode('front-page')}
                        >Newspaper</button>
                        <span className="intel-nav-sep">|</span>
                        <button
                            className={`intel-nav-tab ${viewMode === 'feed' ? 'intel-nav-tab--active' : ''}`}
                            onClick={() => setViewMode('feed')}
                        >Feed</button>
                        <span className="intel-nav-sep">|</span>
                        <button
                            className={`intel-nav-tab ${viewMode === 'analytics' ? 'intel-nav-tab--active' : ''}`}
                            onClick={() => setViewMode('analytics')}
                        >Analytics</button>
                    </nav>
                </div>
                <div className="header-controls">
                </div>
            </div>

            {aiStats && (
                <div className="ai-stats-bar">
                    <span className="ai-stats-label">Intelligence Engine</span>
                    <span className="ai-stat"><strong>{aiStats.ai_calls?.toLocaleString()}</strong> AI calls</span>
                    <span className="ai-stat-dot">·</span>
                    <span className="ai-stat"><strong>{(aiStats.total_tokens / 1000).toFixed(0)}k</strong> tokens</span>
                    <span className="ai-stat-dot">·</span>
                    <span className="ai-stat"><strong>${aiStats.total_cost_usd?.toFixed(4)}</strong> spent</span>
                    <span className="ai-stat-dot">·</span>
                    <span className="ai-stat"><strong>{aiStats.total_stored?.toLocaleString()}</strong> stored</span>
                    <span className="ai-stat-dot">·</span>
                    <span className="ai-stat"><strong>{aiStats.total_chopped?.toLocaleString()}</strong> deduped</span>
                    <span className="ai-stat-dot">·</span>
                    <span className="ai-stat"><strong>{aiStats.total_deflected?.toLocaleString()}</strong> deflected</span>
                </div>
            )}

            <div className="targets-section">
                <div className="targets-section-toggle" onClick={() => setTargetsOpen(o => !o)}>
                    <span className="targets-toggle-arrow">{targetsOpen ? '▾' : '▸'}</span>
                    <span className="targets-toggle-label">Tracking</span>
                    <span className="targets-toggle-counts">
                        {tickerCount} tickers · {nonTickerCount} topics
                    </span>
                </div>
                {targetsOpen && <TargetsPanel targets={targets} onRefresh={fetchData} />}
            </div>

            {error && (
                <div className="error-banner">
                    <strong>Offline:</strong> {error}
                </div>
            )}

            {loading ? (
                <p className="loading-msg">Scanning subspace frequencies…</p>
            ) : viewMode === 'analytics' ? (
                <AnalyticsView
                    sources={sources}
                    onToggleSource={handleToggleSource}
                    articles={briefings}
                    targets={targets}
                />
            ) : viewMode === 'front-page' ? (
                <FrontPageView
                    portfolioArticles={portfolioArticles}
                    topicArticles={topicArticles}
                    tickerSummaries={tickerSummaries}
                    topicSummaries={topicSummaries}
                    expandedIds={expandedIds}
                    toggleCard={toggleCard}
                />
            ) : (
                <div className="news-sections">
                    <CollapsibleSection
                        title="Ticker Summaries" icon="📊" count={tickerSummaries.length}
                        isOpen={portSummariesOpen} onToggleOpen={() => setPortSummariesOpen(o => !o)}
                        isEmpty={tickerSummaries.length === 0}
                        emptyMessage="No ticker summaries yet — add tickers above, then run the ingestor."
                    >
                        {tickerSummaries.map(s => <SummaryCard key={s.target_value} summary={s} />)}
                    </CollapsibleSection>

                    <CollapsibleSection
                        title="Ticker News" icon="📈" count={portfolioArticles.length}
                        isOpen={portArticlesOpen} onToggleOpen={() => setPortArticlesOpen(o => !o)}
                        isEmpty={portfolioArticles.length === 0}
                        emptyMessage="No ticker articles yet. Add tickers above and run the ingestor."
                    >
                        {portfolioArticles.map(b => (
                            <BriefingCard key={b.id} b={b} isExpanded={expandedIds.has(b.id)} onToggle={() => toggleCard(b.id)} />
                        ))}
                    </CollapsibleSection>

                    <CollapsibleSection
                        title="Topic Summaries" icon="📋" count={topicSummaries.length}
                        isOpen={topicSummariesOpen} onToggleOpen={() => setTopicSummariesOpen(o => !o)}
                        isEmpty={topicSummaries.length === 0}
                        emptyMessage="No topic summaries yet — briefings generate automatically."
                    >
                        {topicSummaries.map(s => <SummaryCard key={s.target_value} summary={s} />)}
                    </CollapsibleSection>

                    <CollapsibleSection
                        title="Topic News" icon="🌐" count={topicArticles.length}
                        isOpen={topicArticlesOpen} onToggleOpen={() => setTopicArticlesOpen(o => !o)}
                        isEmpty={topicArticles.length === 0}
                        emptyMessage="No topic articles yet."
                    >
                        {topicArticles.map(b => (
                            <BriefingCard key={b.id} b={b} isExpanded={expandedIds.has(b.id)} onToggle={() => toggleCard(b.id)} />
                        ))}
                    </CollapsibleSection>
                </div>
            )}
        </div>
    );
};

export default NewsView;
