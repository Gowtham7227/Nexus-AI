import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/client";

function Login() {
  const navigate = useNavigate();

  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [forgotMode, setForgotMode] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");

  const [rememberMe, setRememberMe] = useState(true);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const clearStatus = () => {
    setMessage("");
    setError("");
  };

  const saveAuth = (data) => {
    if (data?.token) {
      localStorage.setItem("token", data.token);
      localStorage.setItem("authToken", data.token);
    }

    if (data?.user) {
      localStorage.setItem("user", JSON.stringify(data.user));
      localStorage.setItem("currentUser", JSON.stringify(data.user));
    }
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    clearStatus();

    if (!email.trim() || !password) {
      setError("Please enter your email and password.");
      return;
    }

    setLoading(true);

    try {
      const response = await api.post("/login", {
        email: email.trim().toLowerCase(),
        password,
      });

      saveAuth(response.data);
      navigate("/dashboard", { replace: true });
    } catch (requestError) {
      console.error("Login error:", requestError);
      setError(
        requestError.response?.data?.detail ||
          "Login failed. Please check your email and password."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (event) => {
    event.preventDefault();
    clearStatus();

    if (!email.trim() || !password) {
      setError("Please enter an email and password.");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setLoading(true);

    try {
      const response = await api.post("/register", {
        email: email.trim().toLowerCase(),
        password,
      });

      saveAuth(response.data);
      navigate("/dashboard", { replace: true });
    } catch (requestError) {
      console.error("Registration error:", requestError);
      setError(
        requestError.response?.data?.detail ||
          "Registration failed. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (event) => {
    event.preventDefault();
    clearStatus();

    if (!email.trim()) {
      setError("Please enter your email address.");
      return;
    }

    setLoading(true);

    try {
      const response = await api.post("/forgot-password", {
        email: email.trim().toLowerCase(),
      });

      setOtpSent(true);
      setMessage(
        response.data?.message ||
          "If an account exists for this email, an OTP has been sent."
      );
    } catch (requestError) {
      console.error("Forgot password error:", requestError);
      setError(
        requestError.response?.data?.detail ||
          "Unable to send OTP right now. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (event) => {
    event.preventDefault();
    clearStatus();

    if (!email.trim() || !otp.trim() || !newPassword) {
      setError("Please enter the OTP and your new password.");
      return;
    }

    if (!/^\d{6}$/.test(otp.trim())) {
      setError("OTP must be 6 digits.");
      return;
    }

    if (newPassword.length < 6) {
      setError("New password must be at least 6 characters.");
      return;
    }

    setLoading(true);

    try {
      const response = await api.post("/reset-password", {
        email: email.trim().toLowerCase(),
        otp: otp.trim(),
        new_password: newPassword,
      });

      saveAuth(response.data);
      setMessage(response.data?.message || "Password reset successful.");

      setTimeout(() => {
        navigate("/dashboard", { replace: true });
      }, 700);
    } catch (requestError) {
      console.error("Password reset error:", requestError);
      setError(
        requestError.response?.data?.detail ||
          "Unable to reset your password. Please check the OTP and try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const openForgotPassword = () => {
    clearStatus();
    setForgotMode(true);
    setOtpSent(false);
    setOtp("");
    setNewPassword("");
  };

  const backToLogin = () => {
    clearStatus();
    setForgotMode(false);
    setOtpSent(false);
    setOtp("");
    setNewPassword("");
  };

  const switchAuthMode = () => {
    clearStatus();
    setIsRegister((previous) => !previous);
    setPassword("");
  };

  const pageStyle = {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "32px 20px",
    boxSizing: "border-box",
    background:
      "radial-gradient(circle at 12% 8%, rgba(37,99,235,0.14), transparent 30%), radial-gradient(circle at 90% 92%, rgba(99,102,241,0.10), transparent 30%), #f8fafc",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  };

  const cardStyle = {
    width: "100%",
    maxWidth: "980px",
    minHeight: "650px",
    display: "grid",
    gridTemplateColumns: "0.9fr 1.1fr",
    overflow: "hidden",
    background: "#ffffff",
    border: "1px solid #e2e8f0",
    borderRadius: "28px",
    boxShadow: "0 24px 70px rgba(15,23,42,0.12)",
  };

  const brandPanelStyle = {
    padding: "58px 48px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    background:
      "linear-gradient(145deg, #0f172a 0%, #172554 58%, #1d4ed8 100%)",
    color: "#ffffff",
  };

  const formPanelStyle = {
    padding: "48px 58px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
  };

  const inputStyle = {
    width: "100%",
    boxSizing: "border-box",
    padding: "14px 15px",
    border: "1px solid #dbe3ef",
    borderRadius: "11px",
    outline: "none",
    fontSize: "15px",
    color: "#0f172a",
    background: "#ffffff",
  };

  const primaryButtonStyle = {
    width: "100%",
    padding: "14px 16px",
    marginTop: "8px",
    border: "none",
    borderRadius: "11px",
    background: loading ? "#94a3b8" : "#2563eb",
    color: "#ffffff",
    fontSize: "15px",
    fontWeight: 750,
    cursor: loading ? "wait" : "pointer",
    boxShadow: loading ? "none" : "0 10px 22px rgba(37,99,235,0.20)",
  };

  const labelStyle = {
    display: "block",
    marginBottom: "8px",
    color: "#334155",
    fontSize: "13px",
    fontWeight: 700,
  };

  return (
    <div style={pageStyle}>
      <div className="nexus-login-card" style={cardStyle}>
        <section className="nexus-login-brand" style={brandPanelStyle}>
          <div
            style={{
              width: "50px",
              height: "50px",
              display: "grid",
              placeItems: "center",
              borderRadius: "15px",
              background: "rgba(255,255,255,0.14)",
              border: "1px solid rgba(255,255,255,0.20)",
              fontSize: "24px",
              fontWeight: 800,
              marginBottom: "26px",
            }}
          >
            N
          </div>

          <div
            style={{
              display: "inline-flex",
              alignSelf: "flex-start",
              padding: "7px 11px",
              marginBottom: "17px",
              borderRadius: "999px",
              background: "rgba(255,255,255,0.11)",
              border: "1px solid rgba(255,255,255,0.15)",
              color: "#dbeafe",
              fontSize: "11px",
              fontWeight: 800,
              letterSpacing: "0.05em",
            }}
          >
            NEXUSAI WORKSPACE
          </div>

          <h1
            style={{
              margin: 0,
              fontSize: "42px",
              lineHeight: 1.05,
              letterSpacing: "-0.035em",
              fontWeight: 850,
            }}
          >
            Work smarter
            <br />
            with your documents.
          </h1>

          <p
            style={{
              margin: "20px 0 0",
              color: "#dbeafe",
              fontSize: "15px",
              lineHeight: 1.7,
            }}
          >
            Securely upload documents, ask questions, compare files, and get
            AI-powered answers from your own workspace.
          </p>

          <div style={{ marginTop: "30px", display: "grid", gap: "12px" }}>
            {[
              ["01", "Document intelligence", "Understand long files faster."],
              ["02", "Grounded AI answers", "Ask questions using your documents."],
              ["03", "One secure workspace", "Keep your AI workflow organized."],
            ].map(([number, title, text]) => (
              <div
                key={number}
                style={{
                  display: "flex",
                  gap: "12px",
                  alignItems: "flex-start",
                }}
              >
                <span
                  style={{
                    minWidth: "29px",
                    height: "29px",
                    display: "grid",
                    placeItems: "center",
                    borderRadius: "9px",
                    background: "rgba(255,255,255,0.10)",
                    color: "#bfdbfe",
                    fontSize: "10px",
                    fontWeight: 800,
                  }}
                >
                  {number}
                </span>
                <div>
                  <div style={{ fontSize: "13px", fontWeight: 750 }}>{title}</div>
                  <div
                    style={{
                      marginTop: "2px",
                      color: "#bfdbfe",
                      fontSize: "12px",
                    }}
                  >
                    {text}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="nexus-login-form" style={formPanelStyle}>
          <div style={{ marginBottom: "26px" }}>
            <div
              style={{
                display: "inline-flex",
                padding: "7px 11px",
                borderRadius: "999px",
                background: "#eff6ff",
                color: "#2563eb",
                fontSize: "11px",
                fontWeight: 800,
                letterSpacing: "0.04em",
                marginBottom: "15px",
              }}
            >
              {forgotMode
                ? "ACCOUNT RECOVERY"
                : isRegister
                ? "NEW ACCOUNT"
                : "SECURE SIGN IN"}
            </div>

            <h2
              style={{
                margin: 0,
                color: "#0f172a",
                fontSize: "34px",
                lineHeight: 1.15,
                letterSpacing: "-0.03em",
                fontWeight: 800,
              }}
            >
              {forgotMode
                ? "Reset your password"
                : isRegister
                ? "Create your account"
                : "Welcome back"}
            </h2>

            <p
              style={{
                margin: "10px 0 0",
                color: "#64748b",
                fontSize: "14px",
                lineHeight: 1.6,
              }}
            >
              {forgotMode
                ? otpSent
                  ? "Enter the OTP and choose a new password."
                  : "We'll send a password reset OTP to your email."
                : isRegister
                ? "Start building your personal NexusAI workspace."
                : "Sign in to continue to your NexusAI workspace."}
            </p>
          </div>

          {message && (
            <div
              style={{
                marginBottom: "17px",
                padding: "11px 13px",
                borderRadius: "10px",
                background: "#ecfdf5",
                border: "1px solid #a7f3d0",
                color: "#047857",
                fontSize: "13px",
                lineHeight: 1.5,
              }}
            >
              {message}
            </div>
          )}

          {error && (
            <div
              style={{
                marginBottom: "17px",
                padding: "11px 13px",
                borderRadius: "10px",
                background: "#fef2f2",
                border: "1px solid #fecaca",
                color: "#b91c1c",
                fontSize: "13px",
                lineHeight: 1.5,
              }}
            >
              {error}
            </div>
          )}

          {forgotMode ? (
            <form
              onSubmit={otpSent ? handleResetPassword : handleForgotPassword}
            >
              <label style={labelStyle}>Email Address</label>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  clearStatus();
                }}
                style={inputStyle}
                disabled={otpSent || loading}
                autoComplete="email"
              />

              {!otpSent ? (
                <button
                  type="submit"
                  disabled={loading}
                  style={primaryButtonStyle}
                >
                  {loading ? "Sending OTP..." : "Send OTP"}
                </button>
              ) : (
                <>
                  <label style={{ ...labelStyle, marginTop: "18px" }}>
                    6-Digit OTP
                  </label>
                  <input
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="Enter OTP"
                    value={otp}
                    onChange={(event) => {
                      const value = event.target.value
                        .replace(/\D/g, "")
                        .slice(0, 6);
                      setOtp(value);
                      clearStatus();
                    }}
                    style={inputStyle}
                    autoComplete="one-time-code"
                  />

                  <label style={{ ...labelStyle, marginTop: "18px" }}>
                    New Password
                  </label>
                  <input
                    type="password"
                    placeholder="Enter new password"
                    value={newPassword}
                    onChange={(event) => {
                      setNewPassword(event.target.value);
                      clearStatus();
                    }}
                    style={inputStyle}
                    autoComplete="new-password"
                  />

                  <button
                    type="submit"
                    disabled={loading}
                    style={primaryButtonStyle}
                  >
                    {loading ? "Resetting Password..." : "Reset Password"}
                  </button>
                </>
              )}

              <button
                type="button"
                onClick={backToLogin}
                style={{
                  width: "100%",
                  marginTop: "15px",
                  padding: "11px",
                  border: "none",
                  background: "transparent",
                  color: "#2563eb",
                  cursor: "pointer",
                  fontSize: "13px",
                  fontWeight: 700,
                }}
              >
                ← Back to Login
              </button>
            </form>
          ) : (
            <form onSubmit={isRegister ? handleRegister : handleLogin}>
              <label style={labelStyle}>Email Address</label>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  clearStatus();
                }}
                style={inputStyle}
                autoComplete="email"
              />

              <label style={{ ...labelStyle, marginTop: "18px" }}>
                Password
              </label>
              <input
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value);
                  clearStatus();
                }}
                style={inputStyle}
                autoComplete={isRegister ? "new-password" : "current-password"}
              />

              {!isRegister && (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: "12px",
                    marginTop: "16px",
                    marginBottom: "18px",
                    fontSize: "13px",
                  }}
                >
                  <label
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      color: "#475569",
                      cursor: "pointer",
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={rememberMe}
                      onChange={(event) => setRememberMe(event.target.checked)}
                    />
                    Remember me
                  </label>

                  <button
                    type="button"
                    onClick={openForgotPassword}
                    style={{
                      border: "none",
                      background: "transparent",
                      padding: 0,
                      color: "#2563eb",
                      cursor: "pointer",
                      fontSize: "13px",
                      fontWeight: 650,
                    }}
                  >
                    Forgot password?
                  </button>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                style={primaryButtonStyle}
              >
                {loading
                  ? isRegister
                    ? "Creating Account..."
                    : "Logging in..."
                  : isRegister
                  ? "Create Account"
                  : "Login"}
              </button>
            </form>
          )}

          {!forgotMode && (
            <div
              style={{
                marginTop: "23px",
                paddingTop: "20px",
                borderTop: "1px solid #eef2f7",
                textAlign: "center",
                color: "#64748b",
                fontSize: "13px",
              }}
            >
              {isRegister
                ? "Already have an account?"
                : "Don't have an account?"}

              <button
                type="button"
                onClick={switchAuthMode}
                style={{
                  marginLeft: "6px",
                  border: "none",
                  background: "transparent",
                  color: "#2563eb",
                  cursor: "pointer",
                  fontSize: "13px",
                  fontWeight: 750,
                }}
              >
                {isRegister ? "Login" : "Create Account"}
              </button>
            </div>
          )}
        </section>
      </div>

      <style>{`
        @media (max-width: 780px) {
          .nexus-login-card {
            grid-template-columns: 1fr !important;
            max-width: 620px !important;
          }

          .nexus-login-brand {
            padding: 40px 32px !important;
          }

          .nexus-login-form {
            padding: 40px 32px !important;
          }
        }

        @media (max-width: 480px) {
          .nexus-login-brand,
          .nexus-login-form {
            padding: 32px 22px !important;
          }
        }
      `}</style>
    </div>
  );
}

export default Login;
