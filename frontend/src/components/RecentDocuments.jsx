function RecentDocuments({ documents }) {
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
              Ready
            </span>
          </div>
        ))
      )}
    </div>
  );
}

export default RecentDocuments;