import { useEffect, useMemo, useState } from "react";
import api, { API_BASE_URL } from "../api/client";

import Sidebar from "../components/Sidebar";
import Navbar from "../components/Navbar";

function Documents() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [deleting, setDeleting] = useState("");
  const [selectedDocuments, setSelectedDocuments] = useState([]);

  const fetchDocuments = async () => {
    try {
      const response = await api.get("/documents");
      setDocuments(response.data.documents || []);
    } catch (error) {
      console.error("Error fetching documents:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();

    try {
      const savedSelection = localStorage.getItem(
        "nexusai_selected_documents"
      );

      if (savedSelection) {
        const parsed = JSON.parse(savedSelection);
        if (Array.isArray(parsed)) {
          setSelectedDocuments(parsed);
        }
      }
    } catch (error) {
      console.error("Error restoring selected documents:", error);
    }
  }, []);

  const handleDocumentSelect = (filename) => {
    setSelectedDocuments((previous) => {
      const updated = previous.includes(filename)
        ? previous.filter((item) => item !== filename)
        : [...previous, filename];

      localStorage.setItem(
        "nexusai_selected_documents",
        JSON.stringify(updated)
      );

      return updated;
    });
  };

  const handleClearSelection = () => {
    setSelectedDocuments([]);
    localStorage.removeItem("nexusai_selected_documents");
    localStorage.removeItem("nexusai_selected_document");
  };

  const handleStartChat = () => {
    if (selectedDocuments.length === 0) {
      alert("Please select at least one document.");
      return;
    }

    localStorage.setItem(
      "nexusai_selected_documents",
      JSON.stringify(selectedDocuments)
    );

    if (selectedDocuments.length === 1) {
      localStorage.setItem(
        "nexusai_selected_document",
        selectedDocuments[0]
      );
    } else {
      localStorage.removeItem("nexusai_selected_document");
    }

    localStorage.setItem("nexusai_new_chat", "true");
    window.location.href = "/chat";
  };

  const handleView = async (filename) => {
    try {
      const response = await api.get(
        `/documents/${encodeURIComponent(filename)}/file?download=false`,
        { responseType: "blob" }
      );
      const url = window.URL.createObjectURL(response.data);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => window.URL.revokeObjectURL(url), 60000);
    } catch (error) {
      console.error("View Error:", error);
      alert("Failed to open document.");
    }
  };

  const handleDownload = async (filename) => {
    try {
      const response = await api.get(
        `/documents/${encodeURIComponent(
          filename
        )}/file?download=true`,
        { responseType: "blob" }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");

      link.href = url;
      link.setAttribute("download", filename);
      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Download Error:", error);
      alert("Failed to download document.");
    }
  };

  const handleDelete = async (filename) => {
    const confirmDelete = window.confirm(
      `Are you sure you want to delete "${filename}"?`
    );

    if (!confirmDelete) return;

    try {
      setDeleting(filename);

      await api.delete(
        `/documents/${encodeURIComponent(filename)}`
      );

      setSelectedDocuments((previous) => {
        const updated = previous.filter((item) => item !== filename);
        localStorage.setItem(
          "nexusai_selected_documents",
          JSON.stringify(updated)
        );
        return updated;
      });

      localStorage.removeItem("nexusai_selected_document");

      await fetchDocuments();
    } catch (error) {
      console.error("Delete Error:", error);
      alert("Failed to delete document.");
    } finally {
      setDeleting("");
    }
  };

  const filteredDocuments = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) return documents;

    return documents.filter((item) =>
      item.filename?.toLowerCase().includes(query)
    );
  }, [documents, search]);

  const formatSize = (bytes = 0) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024)
      return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const getExtension = (filename = "") => {
    const parts = filename.split(".");
    return parts.length > 1 ? parts.pop().toUpperCase() : "FILE";
  };

  return (
    <div className="nx-documents-page">
      <style>{`
        .nx-documents-page {
          min-height: 100vh;
          background: var(--nx-bg);
          color: var(--nx-text);
        }

        .nx-documents-main {
          flex: 1;
          min-width: 0;
        }

        .nx-documents-content {
          max-width: 1380px;
          margin: 0 auto;
          padding: 34px 30px 50px;
        }

        .nx-documents-hero {
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          gap: 24px;
          flex-wrap: wrap;
          margin-bottom: 28px;
        }

        .nx-eyebrow {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          padding: 7px 12px;
          border-radius: 999px;
          border: 1px solid var(--nx-primary-border);
          background: var(--nx-primary-soft);
          color: var(--nx-primary);
          font-size: 12px;
          font-weight: 800;
          letter-spacing: .08em;
          text-transform: uppercase;
          margin-bottom: 14px;
        }

        .nx-documents-title {
          margin: 0;
          font-size: clamp(30px, 4vw, 42px);
          line-height: 1.05;
          letter-spacing: -0.03em;
          color: var(--nx-text);
        }

        .nx-documents-subtitle {
          margin: 10px 0 0;
          max-width: 720px;
          color: var(--nx-text-muted);
          font-size: 15px;
          line-height: 1.6;
        }

        .nx-document-count {
          min-width: 150px;
          padding: 15px 18px;
          border: 1px solid var(--nx-border);
          border-radius: 16px;
          background: var(--nx-surface);
          box-shadow: 0 8px 28px rgba(0,0,0,.06);
        }

        .nx-document-count-label {
          color: var(--nx-text-muted);
          font-size: 12px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: .07em;
        }

        .nx-document-count-value {
          margin-top: 4px;
          color: var(--nx-primary);
          font-size: 28px;
          line-height: 1;
          font-weight: 800;
        }

        .nx-selection-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          flex-wrap: wrap;
          margin-bottom: 22px;
          padding: 15px 17px;
          border: 1px solid var(--nx-primary-border);
          border-radius: 16px;
          background: var(--nx-primary-soft);
        }

        .nx-selection-info {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .nx-selection-icon {
          width: 38px;
          height: 38px;
          display: grid;
          place-items: center;
          border-radius: 11px;
          background: var(--nx-primary);
          color: white;
          font-size: 17px;
          font-weight: 800;
        }

        .nx-selection-title {
          font-weight: 800;
          color: var(--nx-text);
        }

        .nx-selection-help {
          margin-top: 3px;
          color: var(--nx-text-muted);
          font-size: 12px;
        }

        .nx-selection-actions {
          display: flex;
          gap: 9px;
          flex-wrap: wrap;
        }

        .nx-btn {
          min-height: 40px;
          border: 0;
          border-radius: 10px;
          padding: 9px 14px;
          font-weight: 750;
          cursor: pointer;
          transition: transform .15s ease, opacity .15s ease, box-shadow .15s ease;
        }

        .nx-btn:hover {
          transform: translateY(-1px);
        }

        .nx-btn-primary {
          background: var(--nx-primary);
          color: white;
          box-shadow: 0 6px 18px rgba(37,99,235,.20);
        }

        .nx-btn-secondary {
          background: var(--nx-surface);
          color: var(--nx-text);
          border: 1px solid var(--nx-border);
        }

        .nx-btn-danger {
          background: #ef4444;
          color: white;
        }

        .nx-toolbar {
          display: flex;
          align-items: center;
          gap: 14px;
          margin-bottom: 18px;
          padding: 14px;
          border: 1px solid var(--nx-border);
          border-radius: 16px;
          background: var(--nx-surface);
        }

        .nx-search-wrap {
          position: relative;
          flex: 1;
        }

        .nx-search-icon {
          position: absolute;
          left: 14px;
          top: 50%;
          transform: translateY(-50%);
          pointer-events: none;
          font-size: 17px;
        }

        .nx-search {
          width: 100%;
          box-sizing: border-box;
          padding: 13px 15px 13px 42px;
          border: 1px solid var(--nx-border);
          border-radius: 11px;
          outline: none;
          background: var(--nx-bg);
          color: var(--nx-text);
          font-size: 14px;
        }

        .nx-search:focus {
          border-color: var(--nx-primary);
          box-shadow: 0 0 0 3px var(--nx-primary-soft);
        }

        .nx-results {
          color: var(--nx-text-muted);
          font-size: 13px;
          white-space: nowrap;
        }

        .nx-list-card {
          overflow: hidden;
          border: 1px solid var(--nx-border);
          border-radius: 18px;
          background: var(--nx-surface);
          box-shadow: 0 10px 32px rgba(0,0,0,.06);
        }

        .nx-list-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 15px;
          padding: 19px 20px;
          border-bottom: 1px solid var(--nx-border);
        }

        .nx-list-title {
          margin: 0;
          font-size: 18px;
          color: var(--nx-text);
        }

        .nx-list-subtitle {
          margin: 4px 0 0;
          color: var(--nx-text-muted);
          font-size: 12px;
        }

        .nx-document-row {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 18px;
          align-items: center;
          padding: 16px 20px;
          border-bottom: 1px solid var(--nx-border);
          transition: background .15s ease, border-color .15s ease;
        }

        .nx-document-row:last-child {
          border-bottom: 0;
        }

        .nx-document-row:hover {
          background: var(--nx-primary-soft);
        }

        .nx-document-row.selected {
          background: var(--nx-primary-soft);
          box-shadow: inset 3px 0 0 var(--nx-primary);
        }

        .nx-document-info {
          display: flex;
          align-items: center;
          gap: 13px;
          min-width: 0;
        }

        .nx-checkbox {
          width: 18px;
          height: 18px;
          accent-color: var(--nx-primary);
          cursor: pointer;
          flex: 0 0 auto;
        }

        .nx-file-icon {
          width: 42px;
          height: 42px;
          display: grid;
          place-items: center;
          flex: 0 0 auto;
          border: 1px solid var(--nx-primary-border);
          border-radius: 12px;
          background: var(--nx-primary-soft);
          color: var(--nx-primary);
          font-size: 13px;
          font-weight: 850;
        }

        .nx-file-name {
          color: var(--nx-text);
          font-size: 14px;
          font-weight: 750;
          overflow-wrap: anywhere;
        }

        .nx-file-meta {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-top: 5px;
          color: var(--nx-text-muted);
          font-size: 12px;
        }

        .nx-dot {
          opacity: .6;
        }

        .nx-status {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 5px 9px;
          border-radius: 999px;
          background: #dcfce7;
          color: #166534;
          font-size: 11px;
          font-weight: 800;
        }

        .nx-status-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #16a34a;
        }

        .nx-document-actions {
          display: flex;
          align-items: center;
          justify-content: flex-end;
          gap: 7px;
          flex-wrap: wrap;
        }

        .nx-action {
          border: 1px solid var(--nx-border);
          border-radius: 9px;
          padding: 8px 11px;
          background: var(--nx-bg);
          color: var(--nx-text);
          cursor: pointer;
          font-size: 12px;
          font-weight: 750;
          transition: transform .15s ease, opacity .15s ease;
        }

        .nx-action:hover {
          transform: translateY(-1px);
        }

        .nx-action-view {
          border-color: var(--nx-primary-border);
          color: var(--nx-primary);
        }

        .nx-action-download {
          border-color: #bbf7d0;
          color: #15803d;
        }

        .nx-action-delete {
          border-color: #fecaca;
          color: #dc2626;
        }

        .nx-action:disabled {
          cursor: not-allowed;
          opacity: .55;
          transform: none;
        }

        .nx-empty {
          padding: 58px 24px;
          text-align: center;
        }

        .nx-empty-icon {
          width: 56px;
          height: 56px;
          margin: 0 auto 13px;
          display: grid;
          place-items: center;
          border-radius: 16px;
          background: var(--nx-primary-soft);
          color: var(--nx-primary);
          font-size: 23px;
        }

        .nx-empty-title {
          margin: 0;
          color: var(--nx-text);
          font-size: 16px;
          font-weight: 800;
        }

        .nx-empty-text {
          margin: 7px 0 0;
          color: var(--nx-text-muted);
          font-size: 13px;
        }

        @media (max-width: 850px) {
          .nx-documents-content {
            padding: 24px 18px 40px;
          }

          .nx-document-row {
            grid-template-columns: 1fr;
          }

          .nx-document-actions {
            justify-content: flex-start;
            padding-left: 43px;
          }

          .nx-toolbar {
            align-items: stretch;
            flex-direction: column;
          }

          .nx-results {
            white-space: normal;
          }
        }

        @media (max-width: 520px) {
          .nx-documents-hero {
            align-items: stretch;
          }

          .nx-document-count {
            width: 100%;
            box-sizing: border-box;
          }

          .nx-selection-actions,
          .nx-selection-actions .nx-btn {
            width: 100%;
          }

          .nx-document-actions {
            padding-left: 0;
          }

          .nx-action {
            flex: 1;
          }

          .nx-list-header {
            align-items: flex-start;
            flex-direction: column;
          }
        }
      `}</style>

      <div style={{ display: "flex", minHeight: "100vh" }}>
        <Sidebar />

        <main className="nx-documents-main">
          <Navbar />

          <div className="nx-documents-content">
            <section className="nx-documents-hero">
              <div>
                <div className="nx-eyebrow">✦ NexusAI Workspace</div>
                <h1 className="nx-documents-title">Documents</h1>
                <p className="nx-documents-subtitle">
                  Manage your workspace files, search documents quickly, and
                  select the documents you want to use with NexusAI.
                </p>
              </div>

              <div className="nx-document-count">
                <div className="nx-document-count-label">Total documents</div>
                <div className="nx-document-count-value">{documents.length}</div>
              </div>
            </section>

            {selectedDocuments.length > 0 && (
              <section className="nx-selection-bar">
                <div className="nx-selection-info">
                  <div className="nx-selection-icon">✓</div>
                  <div>
                    <div className="nx-selection-title">
                      {selectedDocuments.length} document
                      {selectedDocuments.length > 1 ? "s" : ""} selected
                    </div>
                    <div className="nx-selection-help">
                      Only selected documents will be used in your AI chat.
                    </div>
                  </div>
                </div>

                <div className="nx-selection-actions">
                  <button
                    className="nx-btn nx-btn-secondary"
                    onClick={handleClearSelection}
                  >
                    Clear selection
                  </button>
                  <button
                    className="nx-btn nx-btn-primary"
                    onClick={handleStartChat}
                  >
                    💬 Start AI Chat
                  </button>
                </div>
              </section>
            )}

            <section className="nx-toolbar">
              <div className="nx-search-wrap">
                <span className="nx-search-icon">🔍</span>
                <input
                  className="nx-search"
                  type="text"
                  placeholder="Search by document name..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>

              <div className="nx-results">
                Showing {filteredDocuments.length} of {documents.length}
              </div>
            </section>

            <section className="nx-list-card">
              <div className="nx-list-header">
                <div>
                  <h2 className="nx-list-title">All Documents</h2>
                  <p className="nx-list-subtitle">
                    Select a document to start a focused AI conversation.
                  </p>
                </div>

                {selectedDocuments.length > 0 && (
                  <div className="nx-status">
                    <span className="nx-status-dot" />
                    Selection active
                  </div>
                )}
              </div>

              {loading ? (
                <div className="nx-empty">
                  <div className="nx-empty-icon">⏳</div>
                  <p className="nx-empty-title">Loading documents</p>
                  <p className="nx-empty-text">
                    Fetching your workspace files...
                  </p>
                </div>
              ) : filteredDocuments.length === 0 ? (
                <div className="nx-empty">
                  <div className="nx-empty-icon">
                    {search ? "🔎" : "📄"}
                  </div>
                  <p className="nx-empty-title">
                    {search ? "No matching documents" : "No documents yet"}
                  </p>
                  <p className="nx-empty-text">
                    {search
                      ? "Try a different document name."
                      : "Upload a document from the Dashboard to see it here."}
                  </p>
                </div>
              ) : (
                filteredDocuments.map((item, index) => {
                  const isSelected = selectedDocuments.includes(item.filename);

                  return (
                    <div
                      key={`${item.filename}-${index}`}
                      className={`nx-document-row ${
                        isSelected ? "selected" : ""
                      }`}
                    >
                      <div className="nx-document-info">
                        <input
                          className="nx-checkbox"
                          type="checkbox"
                          checked={isSelected}
                          aria-label={`Select ${item.filename}`}
                          onChange={() =>
                            handleDocumentSelect(item.filename)
                          }
                        />

                        <div className="nx-file-icon">
                          {getExtension(item.filename)}
                        </div>

                        <div style={{ minWidth: 0 }}>
                          <div className="nx-file-name">{item.filename}</div>

                          <div className="nx-file-meta">
                            <span>{formatSize(item.size)}</span>
                            <span className="nx-dot">•</span>
                            <span>Ready for AI</span>
                          </div>
                        </div>
                      </div>

                      <div className="nx-document-actions">
                        <span className="nx-status">
                          <span className="nx-status-dot" />
                          Ready
                        </span>

                        <button
                          className="nx-action nx-action-view"
                          onClick={() => handleView(item.filename)}
                        >
                          👁 View
                        </button>

                        <button
                          className="nx-action nx-action-download"
                          onClick={() => handleDownload(item.filename)}
                        >
                          ⬇ Download
                        </button>

                        <button
                          className="nx-action nx-action-delete"
                          onClick={() => handleDelete(item.filename)}
                          disabled={deleting === item.filename}
                        >
                          {deleting === item.filename
                            ? "Deleting..."
                            : "🗑 Delete"}
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </section>
          </div>
        </main>
      </div>
    </div>
  );
}

export default Documents;
