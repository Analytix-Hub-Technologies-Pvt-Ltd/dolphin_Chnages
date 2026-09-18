/**
 * Dynamic API Base URL resolver.
 * Handles both local development and production server environments seamlessly.
 */
export const getBaseUrl = () => {
  // 1. Explicitly configured environment variable
  const envUrl =
    (typeof import.meta !== "undefined" && import.meta.env && (import.meta.env.VITE_BASE_URL || import.meta.env.REACT_APP_BASE_URL)) ||
    (typeof process !== "undefined" && process.env && (process.env.VITE_BASE_URL || process.env.REACT_APP_BASE_URL));

  if (envUrl) {
    return envUrl.replace(/\/+$/, "");
  }

  // 2. Dynamic browser environment detection
  if (typeof window !== "undefined" && window.location) {
    const { protocol, hostname, port } = window.location;

    // Localhost development -> Local FastAPI at port 8000
    if (hostname === "localhost" || hostname === "127.0.0.1") {
      return "http://localhost:8000";
    }

    // Production Server IP -> Server Uvicorn at port 8001
    if (hostname === "203.88.119.83") {
      return "http://203.88.119.83:8001";
    }

    // Production Server Domain -> Server Uvicorn at port 8001
    if (hostname.includes("compunnet.com") || hostname.includes("mmt")) {
      return `${protocol}//${hostname}:8001`;
    }

    // If already connecting on custom port
    if (port === "8000" || port === "8001") {
      return `${protocol}//${hostname}:${port}`;
    }

    // Fallback for any remote server IP/domain
    return `${protocol}//${hostname}:8001`;
  }

  // Default fallback
  return "http://localhost:8000";
};

export const APP_URL = getBaseUrl();
export default APP_URL;
