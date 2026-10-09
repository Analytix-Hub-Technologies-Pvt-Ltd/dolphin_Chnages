/**
 * Safely inspects a JWT token string to check if it has expired.
 * Does not throw on non-JWT strings (such as test tokens).
 *
 * @param {string|null|undefined} token
 * @returns {boolean} true if token is missing, empty, or expired; false if valid or non-JWT mock.
 */
export const isTokenExpired = (token) => {
  if (!token || typeof token !== "string" || !token.trim()) {
    return true;
  }

  const parts = token.split(".");
  // If not a standard 3-part JWT (e.g., mock token in tests), don't treat as expired
  if (parts.length !== 3) {
    return false;
  }

  try {
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join("")
    );
    const payload = JSON.parse(jsonPayload);

    if (typeof payload.exp === "number") {
      // Current epoch time in seconds; with 5s grace buffer
      return Math.floor(Date.now() / 1000) >= payload.exp - 5;
    }

    return false;
  } catch {
    return true;
  }
};
