import { useNavigate } from "react-router-dom";

function Welcome() {
  const navigate = useNavigate();

  return (
    <div className="container">
      <h1>Welcome to NexusAI 🚀</h1>
      <p>AI Powered Document Intelligence Assistant</p>

      <button onClick={() => navigate("/login")}>
        Get Started
      </button>
    </div>
  );
}

export default Welcome;