import "../styles/Sidebar.css";
import { NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import axios from "axios";

function Sidebar() {
  const [processingMode, setProcessingMode] =
    useState("cloud");

  const [toast, setToast] = useState("");

  const [warmingUp, setWarmingUp] =
    useState(false);

  // --------------------------------------------------
  // Load current AI mode
  // --------------------------------------------------

  useEffect(() => {
    const savedMode = localStorage.getItem(
      "nexusai_processing_mode"
    );

    if (
      savedMode === "local" ||
      savedMode === "cloud"
    ) {
      setProcessingMode(savedMode);
    }
  }, []);

  // --------------------------------------------------
  // Show Toast
  // --------------------------------------------------

  const showToast = (message, duration = 2500) => {
    setToast(message);

    setTimeout(() => {
      setToast("");
    }, duration);
  };

  // --------------------------------------------------
  // Warm Up Local AI
  // --------------------------------------------------

  const warmupLocalAI = async () => {
    try {
      setWarmingUp(true);

      showToast(
        "🖥️ Starting Local AI...",
        5000
      );

      console.log(
        "🔥 Starting Qwen3 Local AI warm-up..."
      );

      const response = await axios.post(
        "http://127.0.0.1:8000/local-warmup"
      );

      console.log(
        "Local warm-up response:",
        response.data
      );

      if (
        response.data.status === "ready"
      ) {
        showToast(
          "✓ Local AI ready · Qwen3 4B",
          3000
        );
      } else {
        showToast(
          "⚠️ Local AI warm-up failed",
          3500
        );
      }

    } catch (error) {
      console.error(
        "❌ Local AI warm-up error:",
        error
      );

      showToast(
        "❌ Local AI unavailable",
        3500
      );

    } finally {
      setWarmingUp(false);
    }
  };

  // --------------------------------------------------
  // Cloud <-> Local Switch
  // --------------------------------------------------

  const toggleProcessingMode = async () => {

    // Prevent multiple clicks while warming up
    if (warmingUp) {
      return;
    }

    const newMode =
      processingMode === "cloud"
        ? "local"
        : "cloud";

    // --------------------------------------------------
    // Switch to Local
    // --------------------------------------------------

    if (newMode === "local") {

      setProcessingMode("local");

      localStorage.setItem(
        "nexusai_processing_mode",
        "local"
      );

      // Notify other components
      window.dispatchEvent(
        new Event(
          "nexusai-mode-change"
        )
      );

      // Warm up Qwen
      await warmupLocalAI();

      return;
    }

    // --------------------------------------------------
    // Switch to Cloud
    // --------------------------------------------------

    setProcessingMode("cloud");

    localStorage.setItem(
      "nexusai_processing_mode",
      "cloud"
    );

    // Notify other components
    window.dispatchEvent(
      new Event(
        "nexusai-mode-change"
      )
    );

    showToast(
      "☁️ Cloud AI enabled · Gemini",
      3000
    );
  };

  return (
    <>
      {/* --------------------------------------------------
          Top-right Notification
      -------------------------------------------------- */}

      {toast && (
        <div
          style={{
            position: "fixed",
            top: "20px",
            right: "25px",
            zIndex: 9999,

            padding: "10px 16px",

            background:
              toast.includes("❌")
                ? "#fef2f2"
                : toast.includes("⚠️")
                ? "#fffbeb"
                : "var(--nx-surface)",

            color:
              toast.includes("❌")
                ? "#b91c1c"
                : toast.includes("⚠️")
                ? "#92400e"
                : "var(--nx-text)",

            border:
              toast.includes("❌")
                ? "1px solid #fecaca"
                : toast.includes("⚠️")
                ? "1px solid #fde68a"
                : "1px solid var(--nx-border)",

            borderRadius: "8px",

            boxShadow:
              "0 4px 12px rgba(0,0,0,0.12)",

            fontSize: "14px",
            fontWeight: "600",

            transition:
              "all 0.2s ease",
          }}
        >
          {toast}
        </div>
      )}

      {/* --------------------------------------------------
          Sidebar
      -------------------------------------------------- */}

      <div
        className="sidebar"
        style={{
          display: "flex",
          flexDirection: "column",
          minHeight: "100vh",
        }}
      >

        {/* Logo */}

        <h2 className="logo">
          NexusAI
        </h2>

        {/* Menu */}

        <ul className="menu">

          <li>
            <NavLink to="/dashboard">
              🏠 Dashboard
            </NavLink>
          </li>

          <li>
            <NavLink to="/documents">
              📄 Documents
            </NavLink>
          </li>

          <li>
            <NavLink to="/chat">
              💬 AI Chat
            </NavLink>
          </li>

          <li>
            <NavLink to="/analytics">
              📊 Analytics
            </NavLink>
          </li>

          <li>
            <NavLink to="/settings">
              ⚙️ Settings
            </NavLink>
          </li>

        </ul>

        {/* --------------------------------------------------
            Spacer
        -------------------------------------------------- */}

        <div
          style={{
            flex: 1,
          }}
        />

        {/* --------------------------------------------------
            AI Mode Switch
        -------------------------------------------------- */}

        <div
          style={{
            padding: "18px 15px",
          }}
        >

          <button
            onClick={
              toggleProcessingMode
            }
            disabled={warmingUp}
            style={{
              width: "100%",

              padding:
                "12px 14px",

              border:
                "1px solid rgba(255,255,255,0.25)",

              borderRadius: "9px",

              background:
                warmingUp
                  ? "var(--nx-text-muted)"
                  : processingMode ===
                    "cloud"
                  ? "var(--nx-primary)"
                  : "#16a34a",

              color: "#ffffff",

              fontSize: "14px",

              fontWeight: "600",

              cursor:
                warmingUp
                  ? "wait"
                  : "pointer",

              textAlign: "center",

              transition:
                "all 0.2s ease",

              opacity:
                warmingUp ? 0.8 : 1,
            }}
          >

            {warmingUp
              ? "⏳ Starting Local AI..."
              : processingMode ===
                "cloud"
              ? "☁️ Switch to Local"
              : "🖥️ Switch to Cloud"}

          </button>

          {/* Current Mode */}

          <div
            style={{
              marginTop: "8px",

              textAlign: "center",

              color:
                "rgba(255,255,255,0.65)",

              fontSize: "11px",
            }}
          >

            {processingMode ===
            "cloud"
              ? "Current: Cloud · Gemini"
              : "Current: Local · Qwen3 4B"}

          </div>

        </div>

      </div>
    </>
  );
}

export default Sidebar;