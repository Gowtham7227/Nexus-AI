import axios from "axios";

// NexusAI API configuration. Override with VITE_API_BASE_URL in .env for deployment.
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001"
).replace(/\/$/, "");

export function getAuthToken() {
  return localStorage.getItem("token") || localStorage.getItem("authToken");
}

export function getAuthHeaders(extraHeaders = {}) {
  const token = getAuthToken();
  return token
    ? { ...extraHeaders, Authorization: `Bearer ${token}` }
    : extraHeaders;
}

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

api.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("authToken");
      localStorage.removeItem("user");
      localStorage.removeItem("currentUser");
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  }
);

export default api;
