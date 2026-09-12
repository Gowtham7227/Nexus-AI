import Sidebar from "../components/Sidebar";
import Navbar from "../components/Navbar";
import ChatWindow from "../components/ChatWindow";

function Chat() {
  return (
    <div
      style={{
        display: "flex",
        minHeight: "100vh",
        background: "var(--nx-bg)",
      }}
    >
      <Sidebar />

      <div
        style={{
          flex: 1,
          minWidth: 0,
        }}
      >
        <Navbar />

        <div
          style={{
            padding: "30px",
          }}
        >
          <ChatWindow />
        </div>
      </div>
    </div>
  );
}

export default Chat;