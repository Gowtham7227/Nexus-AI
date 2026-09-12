import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import Navbar from "../components/Navbar";

function Settings() {
  const [mode, setMode] = useState("cloud");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const savedMode = localStorage.getItem("nexusai_processing_mode");
    if (savedMode === "local" || savedMode === "cloud") {
      setMode(savedMode);
    }
  }, []);

  const handleModeChange = (newMode) => {
    setMode(newMode);
    setSaved(false);
  };

  const saveSettings = () => {
    localStorage.setItem("nexusai_processing_mode", mode);
    window.dispatchEvent(new Event("nexusai-mode-change"));
    setSaved(true);

    setTimeout(() => setSaved(false), 2500);
  };

  const handleLogout = () => {
    const confirmed = window.confirm(
      "Are you sure you want to log out of NexusAI?"
    );

    if (!confirmed) return;

    localStorage.removeItem("token");
    localStorage.removeItem("authToken");
    localStorage.removeItem("user");
    localStorage.removeItem("currentUser");
    sessionStorage.clear();

    window.location.href = "/login";
  };

  const cardStyle = {
    background: "var(--nx-surface)",
    border: "1px solid var(--nx-border)",
    borderRadius: "18px",
    padding: "26px",
    marginBottom: "22px",
    boxShadow: "0 10px 30px rgba(0,0,0,0.06)",
  };

  const iconStyle = {
    width: "44px",
    height: "44px",
    borderRadius: "13px",
    display: "grid",
    placeItems: "center",
    background: "var(--nx-primary-soft)",
    fontSize: "21px",
    flexShrink: 0,
  };

  const rowStyle = {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "20px",
    padding: "18px 0",
    borderTop: "1px solid var(--nx-border)",
  };

  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        background: "var(--nx-bg)",
      }}
    >
      <Sidebar />

      <div style={{ flex: 1, minWidth: 0 }}>
        <Navbar />

        <main
          style={{
            padding: "34px clamp(20px, 4vw, 52px)",
            maxWidth: "1180px",
            margin: "0 auto",
            width: "100%",
            boxSizing: "border-box",
          }}
        >
          {/* Page header */}
          <header style={{ marginBottom: "28px" }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "7px 12px",
                borderRadius: "999px",
                background: "var(--nx-primary-soft)",
                color: "var(--nx-primary)",
                fontSize: "12px",
                fontWeight: 800,
                letterSpacing: "0.05em",
              }}
            >
              ⚙️ NEXUSAI PREFERENCES
            </div>

            <h1
              style={{
                margin: "13px 0 6px",
                color: "var(--nx-text)",
                fontSize: "clamp(30px, 4vw, 42px)",
                lineHeight: 1.1,
                fontWeight: 850,
                letterSpacing: "-0.035em",
              }}
            >
              Settings
            </h1>

            <p
              style={{
                margin: 0,
                color: "var(--nx-text-muted)",
                fontSize: "16px",
                lineHeight: 1.6,
              }}
            >
              Control your AI workspace, privacy preferences, and account.
            </p>
          </header>

          {/* General */}
          <section style={cardStyle}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "13px",
                marginBottom: "8px",
              }}
            >
              <div style={iconStyle}>✨</div>
              <div>
                <h2
                  style={{
                    margin: 0,
                    color: "var(--nx-text)",
                    fontSize: "20px",
                  }}
                >
                  General Preferences
                </h2>
                <p
                  style={{
                    margin: "4px 0 0",
                    color: "var(--nx-text-muted)",
                    fontSize: "14px",
                  }}
                >
                  Your workspace defaults and experience.
                </p>
              </div>
            </div>

            <div style={rowStyle}>
              <div>
                <div
                  style={{
                    color: "var(--nx-text)",
                    fontWeight: 750,
                    marginBottom: "5px",
                  }}
                >
                  Appearance
                </div>
                <div
                  style={{
                    color: "var(--nx-text-muted)",
                    fontSize: "14px",
                    lineHeight: 1.5,
                  }}
                >
                  Use the Light / Dark control in the top-right to change the
                  workspace theme.
                </div>
              </div>

              <span
                style={{
                  flexShrink: 0,
                  padding: "7px 11px",
                  borderRadius: "999px",
                  background: "var(--nx-primary-soft)",
                  color: "var(--nx-primary)",
                  fontSize: "12px",
                  fontWeight: 800,
                }}
              >
                Available
              </span>
            </div>

            <div style={{ ...rowStyle, borderTop: "none", paddingBottom: 0 }}>
              <div>
                <div
                  style={{
                    color: "var(--nx-text)",
                    fontWeight: 750,
                    marginBottom: "5px",
                  }}
                >
                  Document-focused answers
                </div>
                <div
                  style={{
                    color: "var(--nx-text-muted)",
                    fontSize: "14px",
                    lineHeight: 1.5,
                  }}
                >
                  Chat responses use the document selected for the current
                  conversation.
                </div>
              </div>

              <span
                style={{
                  flexShrink: 0,
                  padding: "7px 11px",
                  borderRadius: "999px",
                  background: "#dcfce7",
                  color: "#166534",
                  fontSize: "12px",
                  fontWeight: 800,
                }}
              >
                Enabled
              </span>
            </div>
          </section>

          {/* AI Processing */}
          <section style={cardStyle}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "13px",
                marginBottom: "7px",
              }}
            >
              <div style={iconStyle}>🧠</div>
              <div>
                <h2
                  style={{
                    margin: 0,
                    color: "var(--nx-text)",
                    fontSize: "20px",
                  }}
                >
                  AI Processing Mode
                </h2>
                <p
                  style={{
                    margin: "4px 0 0",
                    color: "var(--nx-text-muted)",
                    fontSize: "14px",
                  }}
                >
                  Choose how NexusAI processes your document workloads.
                </p>
              </div>
            </div>

            {[
              {
                id: "cloud",
                icon: "☁️",
                title: "Cloud Mode",
                description:
                  "Use cloud-based AI services for document analysis.",
                status: "Cloud AI connected · Gemini",
              },
              {
                id: "local",
                icon: "🖥️",
                title: "Local Mode",
                description:
                  "Process documents locally for enhanced privacy.",
                status: "Local AI · Qwen3 4B Instruct + Ollama",
              },
            ].map((item) => {
              const active = mode === item.id;

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleModeChange(item.id)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    marginTop: "14px",
                    padding: "19px",
                    border: active
                      ? "2px solid var(--nx-primary)"
                      : "1px solid var(--nx-border)",
                    borderRadius: "15px",
                    cursor: "pointer",
                    background: active
                      ? "var(--nx-primary-soft)"
                      : "var(--nx-surface)",
                    color: "inherit",
                    transition: "all 0.18s ease",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: "16px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "13px",
                      }}
                    >
                      <div style={iconStyle}>{item.icon}</div>

                      <div>
                        <div
                          style={{
                            color: "var(--nx-text)",
                            fontSize: "16px",
                            fontWeight: 800,
                          }}
                        >
                          {item.title}
                        </div>
                        <div
                          style={{
                            marginTop: "5px",
                            color: "var(--nx-text-muted)",
                            fontSize: "14px",
                            lineHeight: 1.5,
                          }}
                        >
                          {item.description}
                        </div>
                      </div>
                    </div>

                    <span
                      style={{
                        width: "22px",
                        height: "22px",
                        borderRadius: "50%",
                        border: active
                          ? "6px solid var(--nx-primary)"
                          : "2px solid var(--nx-border)",
                        boxSizing: "border-box",
                        flexShrink: 0,
                      }}
                    />
                  </div>

                  {active && (
                    <div
                      style={{
                        marginTop: "13px",
                        paddingTop: "12px",
                        borderTop: "1px solid var(--nx-border)",
                        color: "#16a34a",
                        fontSize: "13px",
                        fontWeight: 750,
                      }}
                    >
                      ✓ {item.status}
                    </div>
                  )}
                </button>
              );
            })}

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                marginTop: "20px",
                flexWrap: "wrap",
              }}
            >
              <button
                type="button"
                onClick={saveSettings}
                style={{
                  padding: "12px 20px",
                  border: "none",
                  borderRadius: "10px",
                  background: "var(--nx-primary)",
                  color: "#fff",
                  fontSize: "14px",
                  fontWeight: 800,
                  cursor: "pointer",
                }}
              >
                Save Settings
              </button>

              {saved && (
                <span
                  style={{
                    color: "#16a34a",
                    fontSize: "14px",
                    fontWeight: 750,
                  }}
                >
                  ✓ Settings saved successfully
                </span>
              )}
            </div>
          </section>

          {/* Privacy */}
          <section style={cardStyle}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "13px",
                marginBottom: "18px",
              }}
            >
              <div style={iconStyle}>🔐</div>
              <div>
                <h2
                  style={{
                    margin: 0,
                    color: "var(--nx-text)",
                    fontSize: "20px",
                  }}
                >
                  Privacy & Security
                </h2>
                <p
                  style={{
                    margin: "4px 0 0",
                    color: "var(--nx-text-muted)",
                    fontSize: "14px",
                  }}
                >
                  Understand how your documents are processed.
                </p>
              </div>
            </div>

            {[
              ["🖥️", "Local Processing", "Local Mode uses the local AI runtime with Ollama and Qwen3."],
              ["☁️", "Cloud Processing", "Cloud Mode uses cloud-based AI services for document analysis."],
              ["📄", "Document Context Isolation", "Responses use the selected document and its retrieved context."],
              ["⚙️", "User Control", "You can switch between Local and Cloud processing based on your needs."],
            ].map(([icon, title, description], index) => (
              <div
                key={title}
                style={{
                  display: "flex",
                  gap: "12px",
                  padding: "15px 0",
                  borderTop: "1px solid var(--nx-border)",
                }}
              >
                <span style={{ fontSize: "18px" }}>{icon}</span>
                <div>
                  <div
                    style={{
                      color: "var(--nx-text)",
                      fontWeight: 750,
                      marginBottom: "4px",
                    }}
                  >
                    {title}
                  </div>
                  <div
                    style={{
                      color: "var(--nx-text-muted)",
                      fontSize: "14px",
                      lineHeight: 1.55,
                    }}
                  >
                    {description}
                  </div>
                </div>
              </div>
            ))}

            <div
              style={{
                marginTop: "15px",
                padding: "13px 15px",
                borderRadius: "11px",
                background: "rgba(34,197,94,0.10)",
                border: "1px solid rgba(34,197,94,0.25)",
                color: "#16a34a",
                fontSize: "13px",
                fontWeight: 750,
              }}
            >
              ✓ Privacy controls available
            </div>
          </section>

          {/* Supported formats */}
          <section style={cardStyle}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "13px",
                marginBottom: "18px",
              }}
            >
              <div style={iconStyle}>📁</div>
              <div>
                <h2
                  style={{
                    margin: 0,
                    color: "var(--nx-text)",
                    fontSize: "20px",
                  }}
                >
                  Supported Document Formats
                </h2>
                <p
                  style={{
                    margin: "4px 0 0",
                    color: "var(--nx-text-muted)",
                    fontSize: "14px",
                  }}
                >
                  File formats supported by the NexusAI workspace.
                </p>
              </div>
            </div>

            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              {["PDF", "DOCX", "PPTX", "XLSX"].map((format) => (
                <span
                  key={format}
                  style={{
                    padding: "9px 14px",
                    borderRadius: "10px",
                    background: "var(--nx-primary-soft)",
                    color: "var(--nx-primary)",
                    fontSize: "13px",
                    fontWeight: 800,
                    border: "1px solid var(--nx-border)",
                  }}
                >
                  {format}
                </span>
              ))}
            </div>
          </section>

          {/* Account */}
          <section
            style={{
              ...cardStyle,
              borderColor: "rgba(239,68,68,0.22)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "20px",
                flexWrap: "wrap",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "13px",
                }}
              >
                <div
                  style={{
                    ...iconStyle,
                    background: "rgba(239,68,68,0.10)",
                  }}
                >
                  👤
                </div>
                <div>
                  <h2
                    style={{
                      margin: 0,
                      color: "var(--nx-text)",
                      fontSize: "20px",
                    }}
                  >
                    Account & Session
                  </h2>
                  <p
                    style={{
                      margin: "4px 0 0",
                      color: "var(--nx-text-muted)",
                      fontSize: "14px",
                    }}
                  >
                    End your current NexusAI session.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleLogout}
                style={{
                  padding: "11px 18px",
                  border: "1px solid #ef4444",
                  borderRadius: "10px",
                  background: "rgba(239,68,68,0.10)",
                  color: "#ef4444",
                  fontSize: "14px",
                  fontWeight: 800,
                  cursor: "pointer",
                }}
              >
                🚪 Logout
              </button>
            </div>
          </section>

          {/* Application */}
          <footer
            style={{
              padding: "20px 4px 10px",
              color: "var(--nx-text-muted)",
              fontSize: "13px",
            }}
          >
            <strong style={{ color: "var(--nx-text)" }}>NexusAI</strong>
            <span style={{ margin: "0 8px" }}>•</span>
            AI-Powered Document Intelligence Assistant
          </footer>
        </main>
      </div>
    </div>
  );
}

export default Settings;
