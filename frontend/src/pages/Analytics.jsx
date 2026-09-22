import { useEffect, useMemo, useState, useCallback } from "react";
import api from "../api/client";

import Sidebar from "../components/Sidebar";
import Navbar from "../components/Navbar";

function Analytics() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDays, setSelectedDays] = useState(7);
  const [analyticsOverview, setAnalyticsOverview] = useState(null);
  const [ragDistribution, setRagDistribution] = useState(null);
  const [clearingCache, setClearingCache] = useState(false);
  const [cacheMessage, setCacheMessage] = useState("");

  const fetchAllAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const [docsRes, overviewRes, , ragRes] = await Promise.allSettled([
        api.get("/documents"),
        api.get(`/analytics/overview?days=${selectedDays}`),
        api.get(`/analytics/latency?days=${selectedDays}&limit=50`),
        api.get(`/analytics/rag?days=${selectedDays}`),
        api.get(`/analytics/models?days=${selectedDays}`),
      ]);

      if (docsRes.status === "fulfilled") {
        setDocuments(docsRes.value.data.documents || []);
      }
      if (overviewRes.status === "fulfilled") {
        setAnalyticsOverview(overviewRes.value.data || null);
      }
      if (ragRes.status === "fulfilled") {
        setRagDistribution(ragRes.value.data || null);
      }
    } catch (error) {
      console.error("Error fetching analytics:", error);
    } finally {
      setLoading(false);
    }
  }, [selectedDays]);

  useEffect(() => {
    fetchAllAnalytics();
  }, [fetchAllAnalytics]);

  const handleClearCache = async () => {
    if (!window.confirm("Are you sure you want to invalidate all cached AI responses? Next queries will run full retrieval.")) {
      return;
    }
    try {
      setClearingCache(true);
      const res = await api.post("/cache/clear");
      setCacheMessage(res.data?.message || "Cache cleared successfully.");
      fetchAllAnalytics();
      setTimeout(() => setCacheMessage(""), 4000);
    } catch (err) {
      console.error("Failed to clear cache:", err);
      alert("Failed to clear cache.");
    } finally {
      setClearingCache(false);
    }
  };

  const fileTypeStats = useMemo(() => {
    const stats = {};
    documents.forEach((document) => {
      const filename = document.filename || "";
      const extension = filename.includes(".")
        ? filename.split(".").pop().toUpperCase()
        : "OTHER";
      stats[extension] = (stats[extension] || 0) + 1;
    });
    return Object.entries(stats);
  }, [documents]);

  const totalSize = useMemo(() => {
    return documents.reduce(
      (total, document) => total + (Number(document.size) || 0),
      0
    );
  }, [documents]);

  const formatSize = (bytes) => {
    if (!bytes) return "0 MB";
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="nx-analytics-page">
      <style>{`
        .nx-analytics-page {
          min-height: 100vh;
          background:
            radial-gradient(circle at 88% -5%, var(--nx-primary-soft, rgba(37,99,235,.09)), transparent 30%),
            var(--nx-bg, #f8fafc);
          color: var(--nx-text, #0f172a);
        }

        .nx-analytics-main {
          width: min(1440px, calc(100% - 56px));
          margin: 0 auto;
          padding: 40px 0 56px;
        }

        .nx-analytics-header {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          gap: 24px;
          margin-bottom: 28px;
        }

        .nx-analytics-eyebrow {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 10px;
          padding: 7px 11px;
          border: 1px solid var(--nx-primary-border, rgba(37,99,235,.22));
          border-radius: 999px;
          background: var(--nx-primary-soft, rgba(37,99,235,.08));
          color: var(--nx-primary, #2563eb);
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .09em;
          text-transform: uppercase;
        }

        .nx-analytics-title {
          margin: 0;
          color: var(--nx-text, #0f172a);
          font-size: clamp(28px, 3vw, 40px);
          line-height: 1.08;
          letter-spacing: -.04em;
          font-weight: 900;
        }

        .nx-analytics-subtitle {
          max-width: 680px;
          margin: 10px 0 0;
          color: var(--nx-text-muted, #64748b);
          font-size: 14px;
          line-height: 1.6;
        }

        .nx-header-actions {
          display: flex;
          align-items: center;
          gap: 12px;
          flex-wrap: wrap;
        }

        .nx-time-filter-select {
          padding: 8px 12px;
          border-radius: 10px;
          border: 1px solid var(--nx-border, #cbd5e1);
          background: var(--nx-surface, #ffffff);
          color: var(--nx-text, #0f172a);
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          outline: none;
        }

        .nx-btn-clear-cache {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 8px 14px;
          border-radius: 10px;
          border: 1px solid #fecaca;
          background: #fff1f2;
          color: #be123c;
          font-size: 12px;
          font-weight: 750;
          cursor: pointer;
          transition: all 0.15s ease;
        }

        .nx-btn-clear-cache:hover {
          background: #ffe4e6;
          border-color: #fda4af;
        }

        .nx-analytics-live {
          display: inline-flex;
          align-items: center;
          gap: 9px;
          padding: 8px 12px;
          border: 1px solid var(--nx-border, #cbd5e1);
          border-radius: 10px;
          background: var(--nx-surface, #ffffff);
          color: var(--nx-text-muted, #64748b);
          font-size: 12px;
          font-weight: 750;
          white-space: nowrap;
        }

        .nx-analytics-live-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: #22c55e;
          box-shadow: 0 0 0 4px rgba(34,197,94,.10);
        }

        .nx-analytics-stats {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 14px;
          margin-bottom: 20px;
        }

        .nx-analytics-stat {
          position: relative;
          overflow: hidden;
          padding: 20px;
          border: 1px solid var(--nx-border, #cbd5e1);
          border-radius: 16px;
          background: var(--nx-surface, #ffffff);
          box-shadow: 0 4px 16px rgba(15,23,42,.03);
        }

        .nx-analytics-stat::after {
          content: "";
          position: absolute;
          right: -35px;
          bottom: -45px;
          width: 120px;
          height: 120px;
          border-radius: 50%;
          background: var(--nx-primary-soft, rgba(37,99,235,.07));
          pointer-events: none;
        }

        .nx-analytics-stat-icon {
          display: grid;
          width: 38px;
          height: 38px;
          place-items: center;
          margin-bottom: 14px;
          border: 1px solid var(--nx-primary-border, rgba(37,99,235,.15));
          border-radius: 10px;
          background: var(--nx-primary-soft, rgba(37,99,235,.09));
          color: var(--nx-primary, #2563eb);
          font-size: 16px;
          font-weight: 900;
        }

        .nx-analytics-stat-label {
          position: relative;
          z-index: 1;
          color: var(--nx-text-muted, #64748b);
          font-size: 12px;
          font-weight: 750;
        }

        .nx-analytics-stat-value {
          position: relative;
          z-index: 1;
          margin-top: 4px;
          color: var(--nx-text, #0f172a);
          font-size: 24px;
          font-weight: 900;
          letter-spacing: -.025em;
        }

        .nx-analytics-stat-hint {
          position: relative;
          z-index: 1;
          margin-top: 4px;
          color: var(--nx-text-muted, #64748b);
          font-size: 11px;
        }

        .nx-analytics-grid {
          display: grid;
          grid-template-columns: minmax(0, 1.1fr) minmax(320px, .9fr);
          gap: 20px;
          margin-bottom: 20px;
        }

        .nx-analytics-panel {
          min-width: 0;
          padding: 22px;
          border: 1px solid var(--nx-border, #cbd5e1);
          border-radius: 16px;
          background: var(--nx-surface, #ffffff);
          box-shadow: 0 4px 16px rgba(15,23,42,.03);
          margin-bottom: 20px;
        }

        .nx-analytics-panel-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 18px;
        }

        .nx-analytics-panel-title {
          margin: 0;
          color: var(--nx-text, #0f172a);
          font-size: 16px;
          font-weight: 850;
          letter-spacing: -.015em;
        }

        .nx-analytics-panel-copy {
          margin: 4px 0 0;
          color: var(--nx-text-muted, #64748b);
          font-size: 12px;
          line-height: 1.5;
        }

        .nx-analytics-type-row {
          display: grid;
          grid-template-columns: 140px minmax(0, 1fr) 50px;
          align-items: center;
          gap: 12px;
          margin-bottom: 13px;
        }

        .nx-analytics-type-label {
          color: var(--nx-text, #0f172a);
          font-size: 12px;
          font-weight: 750;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .nx-analytics-track {
          height: 8px;
          overflow: hidden;
          border-radius: 999px;
          background: var(--nx-bg, #f1f5f9);
        }

        .nx-analytics-track-fill {
          height: 100%;
          border-radius: inherit;
          background: var(--nx-primary, #2563eb);
          transition: width .3s ease;
        }

        .nx-analytics-track-fill.green {
          background: #16a34a;
        }

        .nx-analytics-track-fill.amber {
          background: #d97706;
        }

        .nx-analytics-track-fill.purple {
          background: #7c3aed;
        }

        .nx-analytics-type-count {
          color: var(--nx-text-muted, #64748b);
          font-size: 12px;
          font-weight: 800;
          text-align: right;
        }

        .nx-stage-timing-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 12px;
          margin-top: 14px;
        }

        .nx-stage-card {
          padding: 14px;
          border-radius: 12px;
          background: var(--nx-bg, #f8fafc);
          border: 1px solid var(--nx-border, #e2e8f0);
          text-align: center;
        }

        .nx-stage-name {
          font-size: 11.5px;
          font-weight: 750;
          color: var(--nx-text-muted, #64748b);
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }

        .nx-stage-val {
          font-size: 18px;
          font-weight: 900;
          color: var(--nx-text, #0f172a);
          margin-top: 4px;
        }

        .nx-analytics-document-list {
          display: flex;
          flex-direction: column;
        }

        .nx-analytics-document {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          padding: 11px 0;
          border-bottom: 1px solid var(--nx-border, #e2e8f0);
        }

        .nx-analytics-document:last-child {
          border-bottom: 0;
          padding-bottom: 0;
        }

        .nx-analytics-document:first-child {
          padding-top: 0;
        }

        .nx-analytics-document-name {
          min-width: 0;
          overflow: hidden;
          color: var(--nx-text, #0f172a);
          font-size: 12.5px;
          font-weight: 700;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .nx-analytics-document-size {
          flex-shrink: 0;
          color: var(--nx-text-muted, #64748b);
          font-size: 11.5px;
          font-weight: 700;
        }

        .nx-analytics-empty {
          padding: 30px 10px;
          color: var(--nx-text-muted, #64748b);
          font-size: 13.5px;
          text-align: center;
        }

        .nx-cache-toast {
          padding: 10px 16px;
          border-radius: 8px;
          background: #dcfce7;
          border: 1px solid #86efac;
          color: #15803d;
          font-size: 13px;
          font-weight: 700;
          margin-bottom: 18px;
        }

        @media (max-width: 1024px) {
          .nx-analytics-stats {
            grid-template-columns: repeat(2, 1fr);
          }
          .nx-stage-timing-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 768px) {
          .nx-analytics-stats {
            grid-template-columns: 1fr;
          }
          .nx-analytics-grid {
            grid-template-columns: 1fr;
          }
          .nx-analytics-header {
            align-items: flex-start;
            flex-direction: column;
          }
        }
      `}</style>

      <div style={{ display: "flex", minHeight: "100vh" }}>
        <Sidebar />

        <div style={{ flex: 1, minWidth: 0 }}>
          <Navbar />

          <main className="nx-analytics-main">
            <header className="nx-analytics-header">
              <div>
                <div className="nx-analytics-eyebrow">
                  <span>✦</span>
                  AI & RAG Observability
                </div>

                <h1 className="nx-analytics-title">
                  Production Analytics
                </h1>

                <p className="nx-analytics-subtitle">
                  Real-time telemetry, deterministic grounding quality, stage latency breakdowns, user feedback, and response cache efficiency.
                </p>
              </div>

              <div className="nx-header-actions">
                <select
                  className="nx-time-filter-select"
                  value={selectedDays}
                  onChange={(e) => setSelectedDays(Number(e.target.value))}
                >
                  <option value={1}>Last 24 Hours</option>
                  <option value={7}>Last 7 Days</option>
                  <option value={14}>Last 14 Days</option>
                  <option value={30}>Last 30 Days</option>
                </select>

                <button
                  type="button"
                  className="nx-btn-clear-cache"
                  onClick={handleClearCache}
                  disabled={clearingCache}
                  title="Invalidate all cached responses for your account"
                >
                  {clearingCache ? "Clearing..." : "⚡ Invalidate Cache"}
                </button>

                <div className="nx-analytics-live">
                  <span className="nx-analytics-live-dot" />
                  Live Telemetry
                </div>
              </div>
            </header>

            {cacheMessage && (
              <div className="nx-cache-toast">
                ✓ {cacheMessage}
              </div>
            )}

            {loading ? (
              <div className="nx-analytics-panel">
                <div className="nx-analytics-empty">
                  Loading observability & performance metrics...
                </div>
              </div>
            ) : (
              <>
                {/* 1. TOP-LEVEL METRICS CARDS */}
                <section className="nx-analytics-stats">
                  {/* Total AI Requests */}
                  <div className="nx-analytics-stat">
                    <div className="nx-analytics-stat-icon">⚡</div>
                    <div className="nx-analytics-stat-label">Total AI Queries</div>
                    <div className="nx-analytics-stat-value">
                      {analyticsOverview?.total_requests || 0}
                    </div>
                    <div className="nx-analytics-stat-hint">
                      {analyticsOverview?.streaming_requests || 0} streaming · {analyticsOverview?.error_count || 0} errors
                    </div>
                  </div>

                  {/* Cache Efficiency */}
                  <div className="nx-analytics-stat">
                    <div className="nx-analytics-stat-icon">🎯</div>
                    <div className="nx-analytics-stat-label">Cache Hit Rate</div>
                    <div className="nx-analytics-stat-value">
                      {analyticsOverview?.cache_hit_ratio !== undefined ? `${analyticsOverview.cache_hit_ratio}%` : "0%"}
                    </div>
                    <div className="nx-analytics-stat-hint">
                      {analyticsOverview?.cache_hits || 0} hits ({analyticsOverview?.active_cache_entries || 0} active entries)
                    </div>
                  </div>

                  {/* Total Latency */}
                  <div className="nx-analytics-stat">
                    <div className="nx-analytics-stat-icon">⏱</div>
                    <div className="nx-analytics-stat-label">Avg Total Latency</div>
                    <div className="nx-analytics-stat-value">
                      {analyticsOverview?.avg_total_ms ? `${Math.round(analyticsOverview.avg_total_ms)} ms` : "—"}
                    </div>
                    <div className="nx-analytics-stat-hint">
                      TTFT: {analyticsOverview?.avg_ttft_ms ? `${Math.round(analyticsOverview.avg_ttft_ms)} ms` : "—"}
                    </div>
                  </div>

                  {/* Grounding & Satisfaction */}
                  <div className="nx-analytics-stat">
                    <div className="nx-analytics-stat-icon">🛡</div>
                    <div className="nx-analytics-stat-label">Avg Grounding Score</div>
                    <div className="nx-analytics-stat-value">
                      {analyticsOverview?.avg_grounding_score !== undefined
                        ? `${Math.round(analyticsOverview.avg_grounding_score * 100)}%`
                        : "100%"}
                    </div>
                    <div className="nx-analytics-stat-hint">
                      Satisfaction: {analyticsOverview?.satisfaction_ratio !== undefined ? `${analyticsOverview.satisfaction_ratio}% 👍` : "100%"} ({analyticsOverview?.total_feedback || 0} votes)
                    </div>
                  </div>
                </section>

                {/* 2. RAG RETRIEVAL & STAGE LATENCY BREAKDOWN */}
                <section className="nx-analytics-panel">
                  <div className="nx-analytics-panel-header">
                    <div>
                      <h2 className="nx-analytics-panel-title">RAG Stage Latency Breakdown</h2>
                      <p className="nx-analytics-panel-copy">
                        Empirical average execution timings across retrieval and generation pipelines.
                      </p>
                    </div>
                  </div>

                  <div className="nx-stage-timing-grid">
                    <div className="nx-stage-card">
                      <div className="nx-stage-name">Chroma Semantic</div>
                      <div className="nx-stage-val">
                        {analyticsOverview?.avg_chroma_ms ? `${analyticsOverview.avg_chroma_ms.toFixed(1)} ms` : "—"}
                      </div>
                    </div>
                    <div className="nx-stage-card">
                      <div className="nx-stage-name">BM25 Lexical</div>
                      <div className="nx-stage-val">
                        {analyticsOverview?.avg_bm25_ms ? `${analyticsOverview.avg_bm25_ms.toFixed(1)} ms` : "—"}
                      </div>
                    </div>
                    <div className="nx-stage-card">
                      <div className="nx-stage-name">Cross-Encoder</div>
                      <div className="nx-stage-val">
                        {analyticsOverview?.avg_cross_encoder_ms ? `${analyticsOverview.avg_cross_encoder_ms.toFixed(1)} ms` : "—"}
                      </div>
                    </div>
                    <div className="nx-stage-card">
                      <div className="nx-stage-name">Cloud Generation</div>
                      <div className="nx-stage-val">
                        {analyticsOverview?.avg_generation_ms ? `${(analyticsOverview.avg_generation_ms / 1000).toFixed(2)} s` : "—"}
                      </div>
                    </div>
                  </div>
                </section>

                {/* 3. TWO-COLUMN GRID: QUERY TYPES & STRATEGIES */}
                <section className="nx-analytics-grid">
                  {/* Query Type Distribution */}
                  <div className="nx-analytics-panel">
                    <div className="nx-analytics-panel-header">
                      <div>
                        <h2 className="nx-analytics-panel-title">Query Types</h2>
                        <p className="nx-analytics-panel-copy">
                          Classified incoming query intent distribution.
                        </p>
                      </div>
                    </div>

                    {!ragDistribution || Object.keys(ragDistribution.query_types || {}).length === 0 ? (
                      <div className="nx-analytics-empty">No queries recorded for this time range.</div>
                    ) : (
                      Object.entries(ragDistribution.query_types).map(([type, count]) => {
                        const total = analyticsOverview?.total_requests || 1;
                        const pct = Math.round((count / total) * 100);
                        return (
                          <div className="nx-analytics-type-row" key={type}>
                            <span className="nx-analytics-type-label" title={type}>{type}</span>
                            <div className="nx-analytics-track">
                              <div className="nx-analytics-track-fill purple" style={{ width: `${pct}%` }} />
                            </div>
                            <span className="nx-analytics-type-count">{count}</span>
                          </div>
                        );
                      })
                    )}
                  </div>

                  {/* Optimizer Strategies */}
                  <div className="nx-analytics-panel">
                    <div className="nx-analytics-panel-header">
                      <div>
                        <h2 className="nx-analytics-panel-title">Optimizer Strategies</h2>
                        <p className="nx-analytics-panel-copy">
                          Retrieved routes chosen by Adaptive RAG Optimizer.
                        </p>
                      </div>
                    </div>

                    {!ragDistribution || Object.keys(ragDistribution.strategies || {}).length === 0 ? (
                      <div className="nx-analytics-empty">No strategy data available.</div>
                    ) : (
                      Object.entries(ragDistribution.strategies).map(([strategy, count]) => {
                        const total = analyticsOverview?.total_requests || 1;
                        const pct = Math.round((count / total) * 100);
                        return (
                          <div className="nx-analytics-type-row" key={strategy}>
                            <span className="nx-analytics-type-label" title={strategy}>{strategy}</span>
                            <div className="nx-analytics-track">
                              <div className="nx-analytics-track-fill green" style={{ width: `${pct}%` }} />
                            </div>
                            <span className="nx-analytics-type-count">{count}</span>
                          </div>
                        );
                      })
                    )}
                  </div>
                </section>

                {/* 4. WORKSPACE DOCUMENTS & STORAGE SUMMARY */}
                <section className="nx-analytics-grid">
                  <div className="nx-analytics-panel">
                    <div className="nx-analytics-panel-header">
                      <div>
                        <h2 className="nx-analytics-panel-title">Document Formats</h2>
                        <p className="nx-analytics-panel-copy">
                          Extensions of uploaded workspace documents.
                        </p>
                      </div>
                    </div>

                    {fileTypeStats.length === 0 ? (
                      <div className="nx-analytics-empty">No documents uploaded yet.</div>
                    ) : (
                      fileTypeStats.map(([type, count]) => (
                        <div className="nx-analytics-type-row" key={type}>
                          <span className="nx-analytics-type-label">{type}</span>
                          <div className="nx-analytics-track">
                            <div
                              className="nx-analytics-track-fill"
                              style={{ width: `${(count / documents.length) * 100}%` }}
                            />
                          </div>
                          <span className="nx-analytics-type-count">{count}</span>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="nx-analytics-panel">
                    <div className="nx-analytics-panel-header">
                      <div>
                        <h2 className="nx-analytics-panel-title">Workspace Storage</h2>
                        <p className="nx-analytics-panel-copy">
                          Verified workspace document storage statistics.
                        </p>
                      </div>
                    </div>

                    <div className="nx-analytics-document-list">
                      <div className="nx-analytics-document">
                        <span className="nx-analytics-document-name">Total Documents</span>
                        <span className="nx-analytics-document-size">{documents.length}</span>
                      </div>
                      <div className="nx-analytics-document">
                        <span className="nx-analytics-document-name">Storage Used</span>
                        <span className="nx-analytics-document-size">{formatSize(totalSize)}</span>
                      </div>
                      <div className="nx-analytics-document">
                        <span className="nx-analytics-document-name">Unique File Formats</span>
                        <span className="nx-analytics-document-size">{fileTypeStats.length}</span>
                      </div>
                      <div className="nx-analytics-document">
                        <span className="nx-analytics-document-name">Active Cache Entries</span>
                        <span className="nx-analytics-document-size">{analyticsOverview?.active_cache_entries || 0}</span>
                      </div>
                    </div>
                  </div>
                </section>
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}

export default Analytics;