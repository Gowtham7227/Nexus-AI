import { useEffect, useState } from "react";

function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [theme, setTheme] = useState(() =>
    localStorage.getItem("nexusai_theme") === "dark" ? "dark" : "light"
  );

  useEffect(() => {
    const root = document.documentElement;
    const dark = theme === "dark";

    const values = dark
      ? {
          "--nx-bg": "#0f172a",
          "--nx-surface": "#1e293b",
          "--nx-surface-2": "#334155",
          "--nx-text": "#f8fafc",
          "--nx-text-secondary": "#cbd5e1",
          "--nx-text-muted": "#94a3b8",
          "--nx-border": "#334155",
          "--nx-primary": "#60a5fa",
          "--nx-primary-soft": "rgba(96,165,250,0.14)",
          "--nx-primary-border": "rgba(96,165,250,0.30)",
        }
      : {
          "--nx-bg": "#f8fafc",
          "--nx-surface": "#ffffff",
          "--nx-surface-2": "#f1f5f9",
          "--nx-text": "#0f172a",
          "--nx-text-secondary": "#334155",
          "--nx-text-muted": "#64748b",
          "--nx-border": "#e2e8f0",
          "--nx-primary": "#2563eb",
          "--nx-primary-soft": "rgba(37,99,235,0.10)",
          "--nx-primary-border": "rgba(37,99,235,0.25)",
        };

    Object.entries(values).forEach(([key, value]) => root.style.setProperty(key, value));
    root.style.setProperty("color-scheme", dark ? "dark" : "light");
    document.body.style.backgroundColor = dark ? "#0f172a" : "#f8fafc";
    document.body.style.color = dark ? "#f8fafc" : "#0f172a";

    localStorage.setItem("nexusai_theme", theme);
    window.dispatchEvent(new Event("nexusai-theme-change"));
  }, [theme]);

  useEffect(() => {
    const closeMenu = (event) => {
      if (!event.target.closest("[data-nexusai-profile]")) setMenuOpen(false);
    };
    document.addEventListener("click", closeMenu);
    return () => document.removeEventListener("click", closeMenu);
  }, []);

  const toggleTheme = () => {
    setTheme((previous) => (previous === "light" ? "dark" : "light"));
  };

  const isDark = theme === "dark";

  return (
    <div
      style={{
        position: "sticky",
        top: 0,
        zIndex: 1000,
        background: "var(--nx-surface)",
        padding: "16px 24px",
        borderBottom: "1px solid var(--nx-border)",
        boxShadow: isDark
          ? "0 2px 10px rgba(0,0,0,0.20)"
          : "0 2px 10px rgba(15,23,42,0.04)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "20px",
          maxWidth: "1400px",
          margin: "0 auto",
        }}
      >
        <div>
          <h2 style={{ margin: 0, color: "var(--nx-text)", fontSize: "22px", fontWeight: 800 }}>
            Welcome back 👋
          </h2>
          <p style={{ margin: "5px 0 0", color: "var(--nx-text-muted)", fontSize: "13px" }}>
            AI Powered Document Intelligence Assistant
          </p>
        </div>

        <div data-nexusai-profile style={{ position: "relative" }}>
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              setMenuOpen((previous) => !previous);
            }}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "9px",
              padding: "10px 14px",
              border: "1px solid var(--nx-border)",
              borderRadius: "12px",
              background: "var(--nx-surface)",
              color: "var(--nx-text)",
              cursor: "pointer",
              fontSize: "13px",
              fontWeight: 700,
            }}
          >
            <span style={{ fontSize: "16px" }}>
              {isDark ? "☀️" : "🌙"}
            </span>

            <span>
              {isDark ? "Light Mode" : "Dark Mode"}
            </span>

            <span style={{ fontSize: "10px" }}>
              {menuOpen ? "▲" : "▼"}
            </span>
          </button>

          {menuOpen && (
            <div
              style={{
                position: "absolute",
                top: "calc(100% + 8px)",
                right: 0,
                width: "240px",
                padding: "8px",
                background: "var(--nx-surface)",
                border: "1px solid var(--nx-border)",
                borderRadius: "12px",
                boxShadow: isDark
                  ? "0 14px 35px rgba(0,0,0,0.35)"
                  : "0 14px 35px rgba(15,23,42,0.14)",
              }}
            >
              <div
                style={{
                  padding: "10px 11px",
                  marginBottom: "5px",
                  color: "var(--nx-text-muted)",
                  fontSize: "11px",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                Appearance
              </div>

              <button
                type="button"
                onClick={toggleTheme}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: "12px",
                  padding: "11px",
                  border: 0,
                  borderRadius: "9px",
                  background: "var(--nx-bg)",
                  color: "var(--nx-text)",
                  cursor: "pointer",
                  textAlign: "left",
                  fontSize: "14px",
                  fontWeight: 700,
                }}
              >
                <span>{isDark ? "☀️  Light Mode" : "🌙  Dark Mode"}</span>
                <span style={{ color: "var(--nx-text-muted)", fontSize: "11px" }}>
                  {isDark ? "Dark" : "Light"}
                </span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default Navbar;
