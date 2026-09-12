import { useEffect, useMemo, useState } from "react";
import api from "../api/client";

import Sidebar from "../components/Sidebar";
import Navbar from "../components/Navbar";

function Analytics() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchDocuments = async () => {
    try {
      const response = await api.get(
        "/documents"
      );

      setDocuments(response.data.documents || []);
    } catch (error) {
      console.error("Error fetching analytics:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fileTypeStats = useMemo(() => {
    const stats = {};

    documents.forEach((document) => {
      const filename = document.filename || "";
      const extension =
        filename.includes(".")
          ? filename.split(".").pop().toUpperCase()
          : "OTHER";

      stats[extension] = (stats[extension] || 0) + 1;
    });

    return Object.entries(stats);
  }, [documents]);

  const totalSize = useMemo(() => {
    return documents.reduce(
      (total, document) =>
        total + (Number(document.size) || 0),
      0
    );
  }, [documents]);

  const formatSize = (bytes) => {
    if (!bytes) {
      return "0 MB";
    }

    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="nx-analytics-page">
      <style>{`
        .nx-analytics-page {
          min-height: 100vh;
          background:
            radial-gradient(circle at 88% -5%, var(--nx-primary-soft, rgba(37,99,235,.09)), transparent 30%),
            var(--nx-bg);
          color: var(--nx-text);
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
          color: var(--nx-primary);
          font-size: 10px;
          font-weight: 900;
          letter-spacing: .09em;
          text-transform: uppercase;
        }

        .nx-analytics-title {
          margin: 0;
          color: var(--nx-text);
          font-size: clamp(30px, 3vw, 42px);
          line-height: 1.08;
          letter-spacing: -.04em;
          font-weight: 900;
        }

        .nx-analytics-subtitle {
          max-width: 680px;
          margin: 10px 0 0;
          color: var(--nx-text-muted);
          font-size: 14px;
          line-height: 1.7;
        }

        .nx-analytics-live {
          display: inline-flex;
          align-items: center;
          gap: 9px;
          padding: 10px 13px;
          border: 1px solid var(--nx-border);
          border-radius: 12px;
          background: var(--nx-surface);
          color: var(--nx-text-muted);
          font-size: 12px;
          font-weight: 750;
          white-space: nowrap;
          box-shadow: 0 5px 18px rgba(15,23,42,.05);
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
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: 14px;
          margin-bottom: 20px;
        }

        .nx-analytics-stat {
          position: relative;
          overflow: hidden;
          padding: 21px;
          border: 1px solid var(--nx-border);
          border-radius: 16px;
          background: var(--nx-surface);
          box-shadow: 0 8px 28px rgba(15,23,42,.055);
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
          width: 42px;
          height: 42px;
          place-items: center;
          margin-bottom: 18px;
          border: 1px solid var(--nx-primary-border, rgba(37,99,235,.15));
          border-radius: 12px;
          background: var(--nx-primary-soft, rgba(37,99,235,.09));
          color: var(--nx-primary);
          font-size: 18px;
          font-weight: 900;
        }

        .nx-analytics-stat-label {
          position: relative;
          z-index: 1;
          color: var(--nx-text-muted);
          font-size: 12px;
          font-weight: 750;
        }

        .nx-analytics-stat-value {
          position: relative;
          z-index: 1;
          margin-top: 5px;
          color: var(--nx-text);
          font-size: 27px;
          font-weight: 900;
          letter-spacing: -.025em;
        }

        .nx-analytics-stat-hint {
          position: relative;
          z-index: 1;
          margin-top: 5px;
          color: var(--nx-text-muted);
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
          padding: 23px;
          border: 1px solid var(--nx-border);
          border-radius: 16px;
          background: var(--nx-surface);
          box-shadow: 0 8px 28px rgba(15,23,42,.045);
        }

        .nx-analytics-panel-header {
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          gap: 16px;
          margin-bottom: 20px;
        }

        .nx-analytics-panel-title {
          margin: 0;
          color: var(--nx-text);
          font-size: 17px;
          font-weight: 850;
          letter-spacing: -.015em;
        }

        .nx-analytics-panel-copy {
          margin: 5px 0 0;
          color: var(--nx-text-muted);
          font-size: 12px;
          line-height: 1.6;
        }

        .nx-analytics-type-row {
          display: grid;
          grid-template-columns: 70px minmax(0, 1fr) 34px;
          align-items: center;
          gap: 12px;
          margin-bottom: 15px;
        }

        .nx-analytics-type-label {
          color: var(--nx-text-secondary);
          font-size: 11px;
          font-weight: 850;
        }

        .nx-analytics-track {
          height: 9px;
          overflow: hidden;
          border-radius: 999px;
          background: var(--nx-border);
        }

        .nx-analytics-track-fill {
          height: 100%;
          border-radius: inherit;
          background: var(--nx-primary);
          transition: width .3s ease;
        }

        .nx-analytics-type-count {
          color: var(--nx-text-secondary);
          font-size: 12px;
          font-weight: 800;
          text-align: right;
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
          padding: 13px 0;
          border-bottom: 1px solid var(--nx-border);
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
          color: var(--nx-text-secondary);
          font-size: 12px;
          font-weight: 700;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .nx-analytics-document-size {
          flex-shrink: 0;
          color: var(--nx-text-muted);
          font-size: 11px;
          font-weight: 700;
        }

        .nx-analytics-empty {
          padding: 30px 10px;
          color: var(--nx-text-muted);
          font-size: 13px;
          text-align: center;
        }

        @media (max-width: 900px) {
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

        @media (max-width: 600px) {
          .nx-analytics-main {
            width: min(100% - 24px, 1440px);
            padding: 26px 0 40px;
          }

          .nx-analytics-panel {
            padding: 18px;
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
                  Workspace Analytics
                </div>

                <h1 className="nx-analytics-title">
                  Analytics
                </h1>

                <p className="nx-analytics-subtitle">
                  A live view of the documents currently available in your
                  NexusAI workspace. Every metric below is calculated from
                  your actual uploaded documents.
                </p>
              </div>

              <div className="nx-analytics-live">
                <span className="nx-analytics-live-dot" />
                Live document data
              </div>
            </header>

            {loading ? (
              <div className="nx-analytics-panel">
                <div className="nx-analytics-empty">
                  Loading your document analytics...
                </div>
              </div>
            ) : (
              <>
                <section className="nx-analytics-stats">
                  <div className="nx-analytics-stat">
                    <div className="nx-analytics-stat-icon">▤</div>
                    <div className="nx-analytics-stat-label">
                      Uploaded Documents
                    </div>
                    <div className="nx-analytics-stat-value">
                      {documents.length}
                    </div>
                    <div className="nx-analytics-stat-hint">
                      Actual files in your workspace
                    </div>
                  </div>

                  <div className="nx-analytics-stat">
                    <div className="nx-analytics-stat-icon">◫</div>
                    <div className="nx-analytics-stat-label">
                      Total Storage
                    </div>
                    <div className="nx-analytics-stat-value">
                      {formatSize(totalSize)}
                    </div>
                    <div className="nx-analytics-stat-hint">
                      Calculated from uploaded file sizes
                    </div>
                  </div>

                  <div className="nx-analytics-stat">
                    <div className="nx-analytics-stat-icon">◈</div>
                    <div className="nx-analytics-stat-label">
                      File Types
                    </div>
                    <div className="nx-analytics-stat-value">
                      {fileTypeStats.length}
                    </div>
                    <div className="nx-analytics-stat-hint">
                      Different extensions actually uploaded
                    </div>
                  </div>
                </section>

                <section className="nx-analytics-grid">
                  <div className="nx-analytics-panel">
                    <div className="nx-analytics-panel-header">
                      <div>
                        <h2 className="nx-analytics-panel-title">
                          Document Types
                        </h2>
                        <p className="nx-analytics-panel-copy">
                          Distribution based on the extensions of your uploaded files.
                        </p>
                      </div>
                    </div>

                    {fileTypeStats.length === 0 ? (
                      <div className="nx-analytics-empty">
                        No documents uploaded yet.
                      </div>
                    ) : (
                      fileTypeStats.map(([type, count]) => (
                        <div className="nx-analytics-type-row" key={type}>
                          <span className="nx-analytics-type-label">
                            {type}
                          </span>

                          <div className="nx-analytics-track">
                            <div
                              className="nx-analytics-track-fill"
                              style={{
                                width: `${(count / documents.length) * 100}%`,
                              }}
                            />
                          </div>

                          <span className="nx-analytics-type-count">
                            {count}
                          </span>
                        </div>
                      ))
                    )}
                  </div>

                  <div className="nx-analytics-panel">
                    <div className="nx-analytics-panel-header">
                      <div>
                        <h2 className="nx-analytics-panel-title">
                          Workspace Summary
                        </h2>
                        <p className="nx-analytics-panel-copy">
                          Real-time totals from the document service.
                        </p>
                      </div>
                    </div>

                    <div className="nx-analytics-document-list">
                      <div className="nx-analytics-document">
                        <span className="nx-analytics-document-name">
                          Documents
                        </span>
                        <span className="nx-analytics-document-size">
                          {documents.length}
                        </span>
                      </div>

                      <div className="nx-analytics-document">
                        <span className="nx-analytics-document-name">
                          Storage used
                        </span>
                        <span className="nx-analytics-document-size">
                          {formatSize(totalSize)}
                        </span>
                      </div>

                      <div className="nx-analytics-document">
                        <span className="nx-analytics-document-name">
                          File formats
                        </span>
                        <span className="nx-analytics-document-size">
                          {fileTypeStats.length}
                        </span>
                      </div>

                      <div className="nx-analytics-document">
                        <span className="nx-analytics-document-name">
                          Documents available
                        </span>
                        <span className="nx-analytics-document-size">
                          {documents.length > 0 ? "Yes" : "No"}
                        </span>
                      </div>
                    </div>
                  </div>
                </section>

                <section className="nx-analytics-panel">
                  <div className="nx-analytics-panel-header">
                    <div>
                      <h2 className="nx-analytics-panel-title">
                        Uploaded Documents
                      </h2>
                      <p className="nx-analytics-panel-copy">
                        Files currently returned by your NexusAI document service.
                      </p>
                    </div>
                  </div>

                  {documents.length === 0 ? (
                    <div className="nx-analytics-empty">
                      No documents uploaded yet.
                    </div>
                  ) : (
                    <div className="nx-analytics-document-list">
                      {documents.map((document) => (
                        <div
                          className="nx-analytics-document"
                          key={document.filename}
                        >
                          <span
                            className="nx-analytics-document-name"
                            title={document.filename}
                          >
                            📄 {document.filename}
                          </span>

                          <span className="nx-analytics-document-size">
                            {formatSize(document.size)}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
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