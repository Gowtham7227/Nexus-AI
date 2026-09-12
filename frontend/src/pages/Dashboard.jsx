import { useEffect, useMemo, useState } from "react";
import axios from "axios";

import Sidebar from "../components/Sidebar";
import Navbar from "../components/Navbar";
import UploadBox from "../components/UploadBox";
import RecentDocuments from "../components/RecentDocuments";

function Dashboard() {
  const [documents, setDocuments] = useState([]);
  const [processingMode, setProcessingMode] = useState("cloud");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const fetchDocuments = async (showRefresh = false) => {
    try {
      if (showRefresh) setRefreshing(true);
      else setLoading(true);

      setError("");

      const token = localStorage.getItem("token");

      const response = await axios.get(
        "http://127.0.0.1:8000/documents",
        {
          headers: token
            ? {
                Authorization: `Bearer ${token}`,
              }
            : {},
        }
      );

      setDocuments(response.data?.documents || []);
    } catch (err) {
      console.error("Error fetching documents:", err);
      setError(
        err?.response?.status === 401
          ? "Your session has expired. Please log in again."
          : "Unable to load your documents right now. Please check that the backend is running."
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem("token");

    if (token) {
      axios.defaults.headers.common.Authorization = `Bearer ${token}`;
    } else {
      delete axios.defaults.headers.common.Authorization;
    }

    fetchDocuments();

    const loadMode = () => {
      const savedMode = localStorage.getItem(
        "nexusai_processing_mode"
      );

      setProcessingMode(savedMode === "local" ? "local" : "cloud");
    };

    loadMode();

    window.addEventListener("nexusai-mode-change", loadMode);

    return () => {
      window.removeEventListener(
        "nexusai-mode-change",
        loadMode
      );
    };
  }, []);

  const handleUploadSuccess = () => {
    fetchDocuments(true);
  };

  const totalBytes = useMemo(
    () =>
      documents.reduce((total, document) => {
        const size =
          document?.size ??
          document?.file_size ??
          document?.filesize ??
          0;

        return total + (Number(size) || 0);
      }, 0),
    [documents]
  );

  const totalStorage = useMemo(() => {
    if (totalBytes >= 1024 * 1024 * 1024) {
      return `${(totalBytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
    }

    if (totalBytes >= 1024 * 1024) {
      return `${(totalBytes / (1024 * 1024)).toFixed(2)} MB`;
    }

    if (totalBytes >= 1024) {
      return `${(totalBytes / 1024).toFixed(2)} KB`;
    }

    return `${totalBytes} B`;
  }, [totalBytes]);

  const fileTypeCount = useMemo(() => {
    const types = new Set();

    documents.forEach((document) => {
      const name =
        document?.filename ||
        document?.file_name ||
        document?.name ||
        "";

      const extension = name.includes(".")
        ? name.split(".").pop().toUpperCase()
        : "";

      if (extension) types.add(extension);
    });

    return types.size;
  }, [documents]);

  const stats = [
    {
      icon: "▤",
      label: "Documents",
      value: documents.length,
      hint: "Actual files in your workspace",
    },
    {
      icon: "◫",
      label: "Storage",
      value: totalStorage,
      hint: "Calculated from uploaded files",
    },
    {
      icon: "✓",
      label: "RAG Status",
      value: "Enabled",
      hint: "Retrieval system ready",
      status: true,
    },
    {
      icon: processingMode === "local" ? "◉" : "☁",
      label: "AI Mode",
      value: processingMode === "local" ? "Local" : "Cloud",
      hint: processingMode === "local" ? "Qwen3" : "Gemini",
    },
  ];

  return (
    <div className="nx-dashboard-page">
      <style>{`
        .nx-dashboard-page {
          min-height: 100vh;
          background:
            radial-gradient(circle at 85% 0%, rgba(37, 99, 235, 0.10), transparent 30%),
            var(--nx-bg);
          color: var(--nx-text);
        }

        .nx-dashboard-main {
          width: min(1400px, calc(100% - 48px));
          margin: 0 auto;
          padding: 34px 0 48px;
        }

        .nx-dashboard-heading {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          gap: 24px;
          margin-bottom: 26px;
        }

        .nx-dashboard-kicker {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          padding: 7px 12px;
          margin-bottom: 12px;
          border: 1px solid rgba(96, 165, 250, 0.35);
          border-radius: 999px;
          background: rgba(37, 99, 235, 0.12);
          color: #60a5fa;
          font-size: 11px;
          font-weight: 800;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .nx-dashboard-title {
          margin: 0;
          color: var(--nx-text);
          font-size: clamp(32px, 4vw, 48px);
          line-height: 1;
          letter-spacing: -0.04em;
        }

        .nx-dashboard-subtitle {
          max-width: 760px;
          margin: 12px 0 0;
          color: var(--nx-text-muted);
          font-size: 15px;
          line-height: 1.65;
        }

        .nx-dashboard-refresh {
          flex: 0 0 auto;
          padding: 10px 15px;
          border: 1px solid var(--nx-border);
          border-radius: 10px;
          background: var(--nx-surface);
          color: var(--nx-text);
          font-weight: 700;
          cursor: pointer;
        }

        .nx-dashboard-refresh:hover {
          border-color: var(--nx-primary);
        }

        .nx-dashboard-refresh:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .nx-dashboard-stats {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 16px;
          margin-bottom: 20px;
        }

        .nx-stat-card {
          position: relative;
          min-height: 178px;
          overflow: hidden;
          padding: 20px;
          border: 1px solid var(--nx-border);
          border-radius: 16px;
          background: var(--nx-surface);
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.10);
        }

        .nx-stat-card::after {
          content: "";
          position: absolute;
          width: 120px;
          height: 120px;
          right: -54px;
          top: -54px;
          border-radius: 50%;
          background: rgba(37, 99, 235, 0.14);
        }

        .nx-stat-top {
          position: relative;
          z-index: 1;
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 22px;
        }

        .nx-stat-icon {
          display: grid;
          width: 46px;
          height: 46px;
          place-items: center;
          border: 1px solid rgba(96, 165, 250, 0.35);
          border-radius: 12px;
          background: rgba(37, 99, 235, 0.14);
          color: #60a5fa;
          font-size: 22px;
          font-weight: 800;
        }

        .nx-stat-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #94a3b8;
        }

        .nx-status-pill {
          padding: 5px 9px;
          border-radius: 999px;
          background: rgba(16, 185, 129, 0.14);
          color: #10b981;
          font-size: 10px;
          font-weight: 900;
          letter-spacing: 0.08em;
        }

        .nx-stat-label {
          color: var(--nx-text-muted);
          font-size: 12px;
          font-weight: 800;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .nx-stat-value {
          margin-top: 6px;
          color: var(--nx-text);
          font-size: clamp(27px, 3vw, 34px);
          font-weight: 900;
          letter-spacing: -0.03em;
        }

        .nx-stat-hint {
          margin-top: 5px;
          color: var(--nx-text-secondary);
          font-size: 12px;
        }

        .nx-dashboard-grid {
          display: grid;
          grid-template-columns: minmax(0, 1.55fr) minmax(280px, 0.75fr);
          gap: 20px;
          align-items: start;
        }

        .nx-dashboard-panel {
          min-width: 0;
          margin-bottom: 20px;
          padding: 22px;
          border: 1px solid var(--nx-border);
          border-radius: 16px;
          background: var(--nx-surface);
          box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
        }

        .nx-panel-heading {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 17px;
        }

        .nx-panel-title {
          margin: 0;
          color: var(--nx-text);
          font-size: 18px;
        }

        .nx-panel-description {
          margin: 6px 0 0;
          color: var(--nx-text-muted);
          font-size: 13px;
          line-height: 1.5;
        }

        .nx-dashboard-error {
          margin-bottom: 18px;
          padding: 12px 14px;
          border: 1px solid rgba(239, 68, 68, 0.35);
          border-radius: 10px;
          background: rgba(239, 68, 68, 0.10);
          color: #fca5a5;
          font-size: 13px;
          font-weight: 650;
        }

        .nx-workspace-summary {
          display: grid;
          gap: 0;
          border-top: 1px solid var(--nx-border);
        }

        .nx-summary-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 18px;
          padding: 15px 0;
          border-bottom: 1px solid var(--nx-border);
        }

        .nx-summary-label {
          color: var(--nx-text-muted);
          font-size: 13px;
        }

        .nx-summary-value {
          color: var(--nx-text);
          font-size: 14px;
          font-weight: 800;
          text-align: right;
        }

        .nx-mode-badge {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          padding: 6px 9px;
          border-radius: 999px;
          background: rgba(37, 99, 235, 0.12);
          color: #60a5fa;
          font-size: 11px;
          font-weight: 800;
        }

        .nx-ai-shortcut {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 20px;
          padding: 22px;
          border: 1px solid rgba(96, 165, 250, 0.30);
          border-radius: 16px;
          background:
            linear-gradient(135deg, rgba(37, 99, 235, 0.16), rgba(15, 23, 42, 0.10)),
            var(--nx-surface);
        }

        .nx-ai-shortcut h3 {
          margin: 0;
          color: var(--nx-text);
          font-size: 18px;
        }

        .nx-ai-shortcut p {
          margin: 6px 0 0;
          color: var(--nx-text-muted);
          font-size: 13px;
        }

        .nx-ai-button {
          flex: 0 0 auto;
          padding: 11px 17px;
          border: none;
          border-radius: 10px;
          background: var(--nx-primary);
          color: var(--nx-surface);
          font-size: 13px;
          font-weight: 800;
          cursor: pointer;
        }

        .nx-ai-button:hover {
          filter: brightness(1.08);
        }

        @media (max-width: 1050px) {
          .nx-dashboard-stats {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }

          .nx-dashboard-grid {
            grid-template-columns: 1fr;
          }
        }

        @media (max-width: 700px) {
          .nx-dashboard-main {
            width: min(100% - 28px, 1400px);
            padding-top: 24px;
          }

          .nx-dashboard-heading {
            align-items: flex-start;
            flex-direction: column;
          }

          .nx-dashboard-stats {
            grid-template-columns: 1fr;
          }

          .nx-ai-shortcut {
            align-items: flex-start;
            flex-direction: column;
          }

          .nx-ai-button {
            width: 100%;
          }
        }
      `}</style>

      <div style={{ display: "flex", minHeight: "100vh" }}>
        <Sidebar />

        <div style={{ flex: 1, minWidth: 0 }}>
          <Navbar />

          <main className="nx-dashboard-main">
            <section className="nx-dashboard-heading">
              <div>
                <div className="nx-dashboard-kicker">
                  ✦ NexusAI Workspace
                </div>

                <h1 className="nx-dashboard-title">
                  Dashboard
                </h1>

                <p className="nx-dashboard-subtitle">
                  Manage your documents, monitor your AI
                  workspace, and jump straight into document
                  intelligence.
                </p>
              </div>

              <button
                className="nx-dashboard-refresh"
                type="button"
                onClick={() => fetchDocuments(true)}
                disabled={loading || refreshing}
              >
                {refreshing ? "Refreshing…" : "↻ Refresh"}
              </button>
            </section>

            {error && (
              <div className="nx-dashboard-error" role="alert">
                {error}
              </div>
            )}

            <section className="nx-dashboard-stats">
              {stats.map((card) => (
                <div className="nx-stat-card" key={card.label}>
                  <div className="nx-stat-top">
                    <div className="nx-stat-icon">{card.icon}</div>

                    {card.status ? (
                      <span className="nx-status-pill">
                        LIVE
                      </span>
                    ) : (
                      <span className="nx-stat-dot" />
                    )}
                  </div>

                  <div className="nx-stat-label">
                    {card.label}
                  </div>

                  <div className="nx-stat-value">
                    {loading ? "—" : card.value}
                  </div>

                  <div className="nx-stat-hint">
                    {card.hint}
                  </div>
                </div>
              ))}
            </section>

            <div className="nx-dashboard-grid">
              <div>
                <section className="nx-dashboard-panel">
                  <div className="nx-panel-heading">
                    <div>
                      <h2 className="nx-panel-title">
                        Upload Document
                      </h2>
                      <p className="nx-panel-description">
                        Add a document to make it available for
                        NexusAI.
                      </p>
                    </div>
                  </div>

                  <UploadBox
                    onUploadSuccess={handleUploadSuccess}
                    setFileName={() => {}}
                  />
                </section>

                <section className="nx-dashboard-panel">
                  <div className="nx-panel-heading">
                    <div>
                      <h2 className="nx-panel-title">
                        Recent Documents
                      </h2>
                      <p className="nx-panel-description">
                        Your latest files available for AI analysis.
                      </p>
                    </div>
                  </div>

                  <RecentDocuments documents={documents} />
                </section>
              </div>

              <aside>
                <section className="nx-dashboard-panel">
                  <div className="nx-panel-heading">
                    <div>
                      <h2 className="nx-panel-title">
                        Workspace Summary
                      </h2>
                      <p className="nx-panel-description">
                        Live totals calculated from your workspace.
                      </p>
                    </div>
                  </div>

                  <div className="nx-workspace-summary">
                    <div className="nx-summary-row">
                      <span className="nx-summary-label">
                        Documents
                      </span>
                      <strong className="nx-summary-value">
                        {loading ? "—" : documents.length}
                      </strong>
                    </div>

                    <div className="nx-summary-row">
                      <span className="nx-summary-label">
                        Storage used
                      </span>
                      <strong className="nx-summary-value">
                        {loading ? "—" : totalStorage}
                      </strong>
                    </div>

                    <div className="nx-summary-row">
                      <span className="nx-summary-label">
                        File formats
                      </span>
                      <strong className="nx-summary-value">
                        {loading ? "—" : fileTypeCount}
                      </strong>
                    </div>

                    <div className="nx-summary-row">
                      <span className="nx-summary-label">
                        AI processing
                      </span>
                      <span className="nx-mode-badge">
                        {processingMode === "local"
                          ? "◉ Local · Qwen3"
                          : "☁ Cloud · Gemini"}
                      </span>
                    </div>
                  </div>
                </section>
              </aside>
            </div>

            <section className="nx-ai-shortcut">
              <div>
                <h3>🤖 Ask NexusAI</h3>
                <p>
                  Ask questions, summarize, compare, and analyze
                  your uploaded documents.
                </p>
              </div>

              <button
                className="nx-ai-button"
                type="button"
                onClick={() => {
                  window.location.href = "/chat";
                }}
              >
                Open AI Chat →
              </button>
            </section>
          </main>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
