export const getApiBaseUrl = () => {
  const envUrl = process.env.REACT_APP_BASE_URL;
  if (envUrl && envUrl.trim()) {
    return envUrl.trim().replace(/\/+$/, "");
  }

  if (typeof window !== "undefined" && window.location) {
    const { hostname, protocol, port, origin } = window.location;
    if (hostname !== "localhost" && hostname !== "127.0.0.1") {
      if (port === "3000" || port === "3001" || port === "3002" || port === "5173") {
        return `${protocol}//${hostname}:8000`;
      }
      return origin;
    }
  }

  return "http://localhost:8000";
};

export const APP_URL = getApiBaseUrl();

export const resolveImageUrl = (rawUrl) => {
  if (!rawUrl || typeof rawUrl !== "string") return "";
  const trimmed = rawUrl.trim();
  if (!trimmed || trimmed === "null" || trimmed === "undefined" || trimmed === "None") return "";
  if (trimmed.startsWith("data:")) return trimmed;

  const apiBase = getApiBaseUrl().replace(/\/+$/, "");

  // Match /storage/images/... or /storage/pdf_images/... (handles old domains, localhost, or prod domains)
  const storageMatch = trimmed.match(/(\/storage\/(?:images|pdf_images)\/[^?\s]+)/i);
  if (storageMatch) {
    return `${apiBase}${storageMatch[1]}`;
  }

  // Match /images/... or /pdf_images/... without /storage
  const imgFolderMatch = trimmed.match(/(\/(?:images|pdf_images)\/[^?\s]+)/i);
  if (imgFolderMatch) {
    return `${apiBase}/storage${imgFolderMatch[1]}`;
  }

  // Match /api/storage/...
  const apiStorageMatch = trimmed.match(/(\/api\/storage\/[^?\s]+)/i);
  if (apiStorageMatch) {
    return `${apiBase}${apiStorageMatch[1]}`;
  }

  // If absolute HTTP/HTTPS URL from external domain without storage/images
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return trimmed;
  }

  // If path starts with /api/ or /pdf_thumbnail
  if (trimmed.startsWith("/api/") || trimmed.startsWith("/pdf_thumbnail")) {
    return `${apiBase}${trimmed}`;
  }

  // If path starts with /
  if (trimmed.startsWith("/")) {
    if (trimmed.startsWith("/storage/")) {
      return `${apiBase}${trimmed}`;
    }
    return `${apiBase}/storage${trimmed}`;
  }

  // Raw filename, UUID, or PDF extracted image name (e.g. "abc.png" or "c1f7535b-..." or "uuid_img_0_Im0.png")
  if (trimmed.includes("_img_") || trimmed.startsWith("pdf_")) {
    return `${apiBase}/storage/pdf_images/${trimmed}`;
  }

  return `${apiBase}/storage/images/${trimmed}`;
};

