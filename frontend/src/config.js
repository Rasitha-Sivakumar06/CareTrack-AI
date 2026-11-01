/**
 * CareTrack AI frontend configuration & centralized authenticated client
 *
 * SECURITY NOTE & LIMITATIONS:
 * Tokens in this phase are stored in browser localStorage ('caretrack_access_token').
 * While appropriate for single-page applications during development and controlled
 * internal networks, localStorage is vulnerable to cross-site scripting (XSS) if any
 * untrusted script executes in the browser. For enterprise production compliance
 * (HIPAA / GDPR), it is recommended to transition to HttpOnly, SameSite=Strict cookies
 * backed by CSRF tokens or short-lived memory tokens with secure refresh token rotation.
 */

export const API_URL =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) ||
  "http://127.0.0.1:8000";

export const AUTH_TOKEN_KEY = "caretrack_access_token";
export const AUTH_USER_KEY = "caretrack_auth_user";

/**
 * Token & user storage helpers
 */
export function getStoredToken() {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setStoredToken(token) {
  try {
    if (token) {
      localStorage.setItem(AUTH_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(AUTH_TOKEN_KEY);
    }
  } catch {
    // Gracefully handle storage quota or privacy mode exceptions
  }
}

export function removeStoredToken() {
  try {
    localStorage.removeItem(AUTH_TOKEN_KEY);
  } catch {
    // Ignore
  }
}

export function getStoredUser() {
  try {
    const raw = localStorage.getItem(AUTH_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user) {
  try {
    if (user) {
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(AUTH_USER_KEY);
    }
  } catch {
    // Ignore
  }
}

export function removeStoredUser() {
  try {
    localStorage.removeItem(AUTH_USER_KEY);
  } catch {
    // Ignore
  }
}

/**
 * Resolves full API URL if a relative path was provided.
 */
export function resolveApiUrl(path) {
  if (!path) return API_URL;
  if (/^https?:\/\//i.test(path)) return path;
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_URL}${cleanPath}`;
}

/**
 * Centralized authenticated fetch wrapper.
 * - Automatically attaches `Authorization: Bearer <token>` when a token exists.
 * - Preserves custom headers, query params, and body types.
 * - Does NOT override multipart FormData boundaries for file uploads.
 * - Auto-stringifies plain object bodies into JSON and sets Content-Type.
 * - Detects 401 Unauthorized responses on protected endpoints and broadcasts
 *   a 'caretrack:unauthorized' event for graceful session expiry handling.
 */
export async function authFetch(url, options = {}) {
  const fullUrl = resolveApiUrl(url);
  const token = getStoredToken();

  const headers = new Headers(options.headers || {});

  // Attach Bearer token if available and not explicitly provided
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  // Handle request body serialization
  let body = options.body;
  const isSpecialBody =
    (typeof FormData !== "undefined" && body instanceof FormData) ||
    body?.constructor?.name === "FormData" ||
    (typeof Blob !== "undefined" && body instanceof Blob) ||
    body?.constructor?.name === "Blob" ||
    (typeof URLSearchParams !== "undefined" && body instanceof URLSearchParams) ||
    body?.constructor?.name === "URLSearchParams";

  if (body && typeof body === "object" && !isSpecialBody) {
    body = JSON.stringify(body);
    if (!headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
  }

  const mergedOptions = {
    ...options,
    headers,
    body,
  };

  const response = await fetch(fullUrl, mergedOptions);

  // If unauthorized on any endpoint other than /auth/login, notify auth context
  if (response.status === 401 && !fullUrl.includes("/auth/login")) {
    window.dispatchEvent(
      new CustomEvent("caretrack:unauthorized", {
        detail: { url: fullUrl, status: 401 },
      })
    );
  }

  return response;
}

/**
 * Convenience wrapper for JSON API responses with structured error extraction.
 */
export async function authFetchJson(url, options = {}) {
  const response = await authFetch(url, options);

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const errorBody = await response.json();
      if (errorBody && errorBody.detail) {
        if (typeof errorBody.detail === "string") {
          message = errorBody.detail;
        } else if (Array.isArray(errorBody.detail)) {
          message = errorBody.detail
            .map((item) => item.msg || JSON.stringify(item))
            .join("; ");
        } else {
          message = JSON.stringify(errorBody.detail);
        }
      }
    } catch {
      // Non-JSON error body fallback
    }
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }

  return response.json();
}

/**
 * Authenticated file/blob download helper.
 * Fetches the binary document with Authorization header, creates an object URL,
 * triggers an invisible download link, and immediately revokes the object URL.
 */
export async function authDownloadBlob(url, fallbackFilename = "document.pdf") {
  const response = await authFetch(url);

  if (!response.ok) {
    let detailMsg = `Download failed (${response.status})`;
    try {
      const err = await response.json();
      if (err.detail) detailMsg = err.detail;
    } catch {
      // ignore
    }
    throw new Error(detailMsg);
  }

  // Try extracting filename from Content-Disposition header
  let filename = fallbackFilename;
  const disposition = response.headers.get("content-disposition");
  if (disposition && disposition.includes("filename=")) {
    const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (match && match[1]) {
      filename = match[1].replace(/['"]/g, "").trim();
    }
  }

  const blob = await response.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.URL.revokeObjectURL(blobUrl);
}
