function RecentDocuments({ documents }) {
  const getStatusBadge = (doc) => {
    const status = doc?.processing_status || doc?.status || "ready";
    if (status === "processing") {
      return (
        <span
          style={{
            background: "#fef3c7",
            color: "#92400e",
            padding: "5px 10px",
            borderRadius: "20px",
            fontSize: "12px",
            fontWeight: "600",
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
          }}
        >
          <span style={{ animation: "spin 1.5s linear infinite", display: "inline-block" }}>🔄</span> Indexing...
        </span>
      );
    }
    if (status === "failed") {
      return (
        <span
          style={{
            background: "#fee2e2",
            color: "#991b1b",
            padding: "5px 10px",
            borderRadius: "20px",
            fontSize: "12px",
            fontWeight: "600",
          }}
        >
          ❌ Failed
        </span>
      );
    }
    return (
      <span
        style={{
          background: "#dcfce7",
          color: "#166534",
          padding: "5px 10px",
          borderRadius: "20px",
          fontSize: "12px",
          fontWeight: "600",
        }}
      >
        ✓ Ready
      </span>
    );
  };

  return (
    <div
      style={{
        background: "#ffffff",
        padding: "20px",
        marginTop: "30px",
        borderRadius: "12px",
        boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
      }}
    >
      <h2
        style={{
          color: "#0f172a",
          marginTop: 0,
        }}
      >
        📄 Recent Documents
      </h2>

      {!documents || documents.length === 0 ? (
        <p style={{ color: "#64748b" }}>
          No documents uploaded yet.
        </p>
      ) : (
        documents.map((document, index) => (
          <div
            key={`${document.filename}-${index}`}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "14px",
              marginTop: "10px",
              background: "#f8fafc",
              borderRadius: "8px",
              border: "1px solid #e2e8f0",
            }}
          >
            <div>
              <div
                style={{
                  color: "#0f172a",
                  fontWeight: "600",
                  fontSize: "16px",
                }}
              >
                📄 {document.filename}
              </div>

              <div
                style={{
                  marginTop: "5px",
                  color: "#64748b",
                  fontSize: "13px",
                }}
              >
                {(document.size / 1024).toFixed(1)} KB
              </div>
            </div>

            {getStatusBadge(document)}
          </div>
        ))
      )}
    </div>
  );
}

export default RecentDocuments;