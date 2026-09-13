import { useNavigate } from "react-router-dom";

function Welcome() {
  const navigate = useNavigate();

  const pageStyle = {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "32px 20px",
    boxSizing: "border-box",
    background:
      "radial-gradient(circle at 15% 10%, rgba(37,99,235,0.14), transparent 32%), radial-gradient(circle at 85% 90%, rgba(99,102,241,0.10), transparent 30%), #f8fafc",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  };

  const cardStyle = {
    width: "100%",
    maxWidth: "920px",
    minHeight: "560px",
    display: "grid",
    gridTemplateColumns: "1.05fr 0.95fr",
    overflow: "hidden",
    background: "#ffffff",
    border: "1px solid #e2e8f0",
    borderRadius: "28px",
    boxShadow: "0 24px 70px rgba(15,23,42,0.12)",
  };

  return (
    <div style={pageStyle}>
      <div className="nexus-welcome-card" style={cardStyle}>
        <section
          style={{
            padding: "64px 58px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
            background:
              "linear-gradient(145deg, #0f172a 0%, #172554 58%, #1d4ed8 100%)",
            color: "#ffffff",
          }}
        >
          <div
            style={{
              width: "52px",
              height: "52px",
              display: "grid",
              placeItems: "center",
              borderRadius: "15px",
              background: "rgba(255,255,255,0.14)",
              border: "1px solid rgba(255,255,255,0.20)",
              fontSize: "25px",
              fontWeight: 800,
              marginBottom: "28px",
            }}
          >
            N
          </div>

          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              alignSelf: "flex-start",
              padding: "7px 12px",
              marginBottom: "18px",
              borderRadius: "999px",
              background: "rgba(255,255,255,0.12)",
              border: "1px solid rgba(255,255,255,0.16)",
              fontSize: "12px",
              fontWeight: 700,
              letterSpacing: "0.04em",
            }}
          >
            AI DOCUMENT WORKSPACE
          </div>

          <h1
            style={{
              margin: 0,
              fontSize: "clamp(40px, 5vw, 62px)",
              lineHeight: 1.03,
              letterSpacing: "-0.04em",
              fontWeight: 850,
            }}
          >
            Nexus<span style={{ color: "#93c5fd" }}>AI</span>
          </h1>

          <p
            style={{
              margin: "22px 0 0",
              maxWidth: "520px",
              color: "#dbeafe",
              fontSize: "19px",
              lineHeight: 1.65,
            }}
          >
            AI-powered document intelligence for understanding, searching,
            comparing, and chatting with your documents.
          </p>

          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "10px",
              marginTop: "32px",
            }}
          >
            {["Smart document chat", "Secure workspace", "RAG-powered answers"].map(
              (item) => (
                <span
                  key={item}
                  style={{
                    padding: "9px 12px",
                    borderRadius: "10px",
                    background: "rgba(255,255,255,0.09)",
                    border: "1px solid rgba(255,255,255,0.14)",
                    color: "#eff6ff",
                    fontSize: "13px",
                    fontWeight: 600,
                  }}
                >
                  ✓ {item}
                </span>
              )
            )}
          </div>
        </section>

        <section
          style={{
            padding: "64px 52px",
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignSelf: "flex-start",
              padding: "7px 11px",
              borderRadius: "999px",
              background: "#eff6ff",
              color: "#2563eb",
              fontSize: "12px",
              fontWeight: 800,
              marginBottom: "18px",
            }}
          >
            WELCOME
          </div>

          <h2
            style={{
              margin: 0,
              color: "#0f172a",
              fontSize: "36px",
              lineHeight: 1.15,
              letterSpacing: "-0.03em",
              fontWeight: 800,
            }}
          >
            Your documents,
            <br />
            made intelligent.
          </h2>

          <p
            style={{
              margin: "16px 0 30px",
              color: "#64748b",
              fontSize: "16px",
              lineHeight: 1.65,
            }}
          >
            Upload your files and use NexusAI to get fast, grounded answers
            from your own document workspace.
          </p>

          <button
            type="button"
            onClick={() => navigate("/login")}
            style={{
              width: "100%",
              padding: "15px 18px",
              border: "none",
              borderRadius: "12px",
              background: "#2563eb",
              color: "#ffffff",
              fontSize: "16px",
              fontWeight: 750,
              cursor: "pointer",
              boxShadow: "0 10px 24px rgba(37,99,235,0.22)",
            }}
          >
            Get Started →
          </button>

          <p
            style={{
              margin: "18px 0 0",
              textAlign: "center",
              color: "#94a3b8",
              fontSize: "12px",
            }}
          >
            Sign in or create your account to continue
          </p>
        </section>
      </div>

      <style>{`
        @media (max-width: 760px) {
          .nexus-welcome-card {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </div>
  );
}

export default Welcome;
