import { APP_URL } from "./config";

const normalizeUrl = (url) => {
  if (!url) return APP_URL;
  if (/^https?:\/\//i.test(url)) return url;
  const base = APP_URL.replace(/\/+$/, "");
  const path = String(url).replace(/^\/+/, "");
  return `${base}/${path}`;
};

// Use the token already persisted by loginApi. Do not change global fetch/axios defaults.
export const sessionFetch = async (url, options = {}) => {
  const requestUrl = new URL(url, APP_URL);
  const apiUrl = new URL(APP_URL);
  const basePath = apiUrl.pathname.replace(/\/+$/, "");
  const isAuthenticatedRequest = requestUrl.origin === apiUrl.origin &&
    ["sessions", "users"].some(resource => {
      const path = `${basePath}/${resource}`;
      return requestUrl.pathname === path || requestUrl.pathname.startsWith(`${path}/`);
    });
  const headers = new Headers(options.headers);
  if (requestUrl.origin !== apiUrl.origin) headers.delete("Authorization");
  let token;
  if (isAuthenticatedRequest) {
    try {
      token = JSON.parse(localStorage.getItem("userData") || "null")?.access_token;
    } catch {
      // Invalid or legacy stored login data has no usable token.
    }
    if (typeof token === "string" && token.trim()) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }
  const response = await fetch(url, {
    ...options,
    headers,
    // Authenticated API calls must not redirect to another destination.
    ...(headers.has("Authorization") && isAuthenticatedRequest ? { redirect: "error" } : {}),
  });

  if (response.status === 401 && isAuthenticatedRequest) {
    if (typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
      window.dispatchEvent(new CustomEvent("dolphin:auth_unauthorized", { detail: { url } }));
    }
  }

  return response;
};

const readBody = async (response) => {
  try {
    if (typeof response.text === "function") {
      const text = await response.text();
      if (!text) return null;

      try {
        return JSON.parse(text);
      } catch {
        return text;
      }
    }

    if (typeof response.json === "function") {
      return await response.json();
    }

    return null;
  } catch {
    return null;
  }
};

const readErrorMessage = async (response, fallbackMessage) => {
  try {
    const payload = await readBody(response);

    if (!payload) {
      return fallbackMessage;
    }

    return (
      payload?.message ||
      payload?.detail ||
      payload?.error ||
      payload?.errors?.[0] ||
      fallbackMessage
    );
  } catch {
    return fallbackMessage;
  }
};

export const apiRequest = async ({
  url,
  method = "GET",
  body,
  headers = {},
  query,
  signal,
  credentials = "include",
  parseJson = true,
  ...rest
} = {}) => {
  const queryString = query
    ? `?${new URLSearchParams(query).toString()}`
    : "";

  const requestUrl = normalizeUrl(`${url}${queryString}`);

  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
  const hasBody = body !== undefined && body !== null;

  const config = {
    method: method.toUpperCase(),
    credentials,
    signal,
    ...rest,
    headers: {
      Accept: "application/json",
      ...(hasBody && !isFormData ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  };

  if (hasBody) {
    config.body = isFormData ? body : JSON.stringify(body);
  }

  const response = await sessionFetch(requestUrl, config);

  if (!response.ok) {
    const message = await readErrorMessage(response, `${method} request failed`);
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  if (!parseJson) {
    return response;
  }

  const payload = await readBody(response);

  if (!payload) {
    return null;
  }

  return payload;
};

export const apiGet = (url, options = {}) => apiRequest({ url, method: "GET", ...options });
export const apiPost = (url, body, options = {}) => apiRequest({ url, method: "POST", body, ...options });
export const apiPut = (url, body, options = {}) => apiRequest({ url, method: "PUT", body, ...options });
export const apiPatch = (url, body, options = {}) => apiRequest({ url, method: "PATCH", body, ...options });
export const apiDelete = (url, options = {}) => apiRequest({ url, method: "DELETE", ...options });
