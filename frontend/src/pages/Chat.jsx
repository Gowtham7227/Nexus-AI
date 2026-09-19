import { Component } from "react";
import Sidebar from "../components/Sidebar";
import Navbar from "../components/Navbar";
import ChatWindow from "../components/ChatWindow";

class ChatErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Chat page error caught by boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: "40px 24px",
            background: "var(--nx-surface)",
            border: "1px solid #fecaca",
            borderRadius: "16px",
            color: "#b91c1c",
            textAlign: "center",
            maxWidth: "600px",
            margin: "40px auto",
            boxShadow: "0 10px 30px rgba(0,0,0,0.06)",
          }}
        >
          <div style={{ fontSize: "36px", marginBottom: "12px" }}>⚠️</div>
          <h2 style={{ fontSize: "20px", fontWeight: 800, margin: "0 0 8px" }}>
            NexusAI Chat Encountered an Issue
          </h2>
          <p style={{ color: "var(--nx-text-muted)", fontSize: "14px", margin: "0 0 20px" }}>
            {this.state.error?.message || "An unexpected rendering error occurred in the chat window."}
          </p>
          <button
            type="button"
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
            style={{
              padding: "10px 20px",
              background: "var(--nx-primary)",
              color: "#ffffff",
              border: "none",
              borderRadius: "10px",
              fontWeight: 700,
              fontSize: "14px",
              cursor: "pointer",
            }}
          >
            Reload Chat Interface
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function Chat() {
  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        maxHeight: "100vh",
        overflow: "hidden",
        background: "var(--nx-bg)",
      }}
    >
      <Sidebar />

      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          height: "100vh",
          maxHeight: "100vh",
          overflow: "hidden",
          minWidth: 0,
        }}
      >
        <Navbar />

        <div
          style={{
            flex: 1,
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
            padding: "16px 24px 20px",
            overflow: "hidden",
          }}
        >
          <ChatErrorBoundary>
            <ChatWindow />
          </ChatErrorBoundary>
        </div>
      </div>
    </div>
  );
}

export default Chat;