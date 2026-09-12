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
      const response = await api.post(
        "/forgot-password",
        {
          email: email.trim().toLowerCase(),
        }
      );

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
      const response = await api.post(
        "/reset-password",
        {
          email: email.trim().toLowerCase(),
          otp: otp.trim(),
          new_password: newPassword,
        }
      );

      saveAuth(response.data);

      setMessage(
        response.data?.message ||
          "Password reset successful."
      );

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
    padding: "30px 20px",
    boxSizing: "border-box",
    background:
      "radial-gradient(circle at 15% 10%, rgba(37,99,235,0.10), transparent 30%), #f8fafc",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  };

  const cardStyle = {
    width: "100%",
    maxWidth: "560px",
    padding: "42px 48px",
    boxSizing: "border-box",
    background: "#ffffff",
    border: "1px solid #e2e8f0",
    borderRadius: "24px",
    boxShadow: "0 20px 50px rgba(15,23,42,0.10)",
  };

  const inputStyle = {
    width: "100%",
    boxSizing: "border-box",
    padding: "15px 16px",
    border: "1px solid #dbe3ef",
    borderRadius: "10px",
    outline: "none",
    fontSize: "16px",
    color: "#0f172a",
    background: "#ffffff",
  };

  const primaryButtonStyle = {
    width: "100%",
    padding: "14px 16px",
    marginTop: "8px",
    border: "none",
    borderRadius: "10px",
    background: loading ? "#94a3b8" : "#2563eb",
    color: "#ffffff",
    fontSize: "16px",
    fontWeight: 700,
    cursor: loading ? "wait" : "pointer",
  };

  return (
    <div style={pageStyle}>
      <div style={cardStyle}>
        <div style={{ textAlign: "center" }}>
          <h1
            style={{
              margin: 0,
              color: "#0f172a",
              fontSize: "38px",
              fontWeight: 800,
            }}
          >
            {forgotMode
              ? "Reset Password"
              : isRegister
              ? "Create Account"
              : "Login"}
          </h1>

          <p
            style={{
              margin: "14px 0 30px",
              color: "#334155",
              fontSize: "18px",
            }}
          >
            {forgotMode
              ? otpSent
                ? "Enter the OTP and your new password 🔐"
                : "We'll send a password reset OTP 📧"
              : isRegister
              ? "Create your NexusAI account 🚀"
              : "Welcome Back 👋"}
          </p>
        </div>

        {message && (
          <div
            style={{
              marginBottom: "18px",
              padding: "12px 14px",
              borderRadius: "9px",
              background: "#ecfdf5",
              border: "1px solid #a7f3d0",
              color: "#047857",
              fontSize: "14px",
              lineHeight: 1.5,
            }}
          >
            {message}
          </div>
        )}

        {error && (
          <div
            style={{
              marginBottom: "18px",
              padding: "12px 14px",
              borderRadius: "9px",
              background: "#fef2f2",
              border: "1px solid #fecaca",
              color: "#b91c1c",
              fontSize: "14px",
              lineHeight: 1.5,
            }}
          >
            {error}
          </div>
        )}

        {forgotMode ? (
          <form
            onSubmit={
              otpSent
                ? handleResetPassword
                : handleForgotPassword
            }
          >
            <label
              style={{
                display: "block",
                marginBottom: "8px",
                color: "#334155",
                fontSize: "14px",
                fontWeight: 600,
              }}
            >
              Email Address
            </label>

            <input
              type="email"
              placeholder="Enter Email"
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
                <label
                  style={{
                    display: "block",
                    marginTop: "20px",
                    marginBottom: "8px",
                    color: "#334155",
                    fontSize: "14px",
                    fontWeight: 600,
                  }}
                >
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

                <label
                  style={{
                    display: "block",
                    marginTop: "20px",
                    marginBottom: "8px",
                    color: "#334155",
                    fontSize: "14px",
                    fontWeight: 600,
                  }}
                >
                  New Password
                </label>

                <input
                  type="password"
                  placeholder="Enter New Password"
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
                marginTop: "16px",
                padding: "12px",
                border: "none",
                background: "transparent",
                color: "#2563eb",
                cursor: "pointer",
                fontSize: "14px",
                fontWeight: 600,
              }}
            >
              ← Back to Login
            </button>
          </form>
        ) : (
          <form
            onSubmit={
              isRegister ? handleRegister : handleLogin
            }
          >
            <label
              style={{
                display: "block",
                marginBottom: "8px",
                color: "#334155",
                fontSize: "14px",
                fontWeight: 600,
              }}
            >
              Email Address
            </label>

            <input
              type="email"
              placeholder="Enter Email"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                clearStatus();
              }}
              style={inputStyle}
              autoComplete="email"
            />

            <label
              style={{
                display: "block",
                marginTop: "18px",
                marginBottom: "8px",
                color: "#334155",
                fontSize: "14px",
                fontWeight: 600,
              }}
            >
              Password
            </label>

            <input
              type="password"
              placeholder="Enter Password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                clearStatus();
              }}
              style={inputStyle}
              autoComplete={
                isRegister ? "new-password" : "current-password"
              }
            />

            {!isRegister && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginTop: "18px",
                  marginBottom: "20px",
                  fontSize: "14px",
                }}
              >
                <label
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    color: "#0f172a",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(event) =>
                      setRememberMe(event.target.checked)
                    }
                  />
                  Remember
                </label>

                <button
                  type="button"
                  onClick={openForgotPassword}
                  style={{
                    border: "none",
                    background: "transparent",
                    padding: 0,
                    color: "#0f172a",
                    textDecoration: "underline",
                    cursor: "pointer",
                    fontSize: "14px",
                  }}
                >
                  Forgot Password?
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
              marginTop: "26px",
              textAlign: "center",
              color: "#475569",
              fontSize: "14px",
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
                fontSize: "14px",
                fontWeight: 700,
              }}
            >
              {isRegister ? "Login" : "Create Account"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default Login;
