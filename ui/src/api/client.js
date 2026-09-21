import APP_URL from "../config/apiConfig";

const normalizeUrl = (url) => {
  if (!url) return APP_URL;
  if (/^https?:\/\//i.test(url)) return url;
  const base = APP_URL.replace(/\/+$/, "");
  const path = String(url).replace(/^\/+/, "");
  return `${base}/${path}`;
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

  const response = await fetch(requestUrl, config);

  if (!response.ok) {
    const message = await readErrorMessage(response, `${method} request failed`);
    throw new Error(message);
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
