import { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import {
  API_URL,
  getStoredToken,
  setStoredToken,
  removeStoredToken,
  getStoredUser,
  setStoredUser,
  removeStoredUser,
  authFetch,
} from "../config";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getStoredToken());
  const [user, setUser] = useState(() => getStoredUser());
  const [isLoading, setIsLoading] = useState(true);
  const [sessionExpiredNotice, setSessionExpiredNotice] = useState(false);

  // Logout clears all stored tokens, user profile, and session state
  const logout = useCallback(() => {
    removeStoredToken();
    removeStoredUser();
    setToken(null);
    setUser(null);
  }, []);

  // Verify existing token on application startup via GET /auth/me
  useEffect(() => {
    let active = true;

    async function verifyInitialSession() {
      const existingToken = getStoredToken();

      if (!existingToken) {
        if (active) {
          setUser(null);
          setToken(null);
          setIsLoading(false);
        }
        return;
      }

      try {
        const response = await authFetch(`${API_URL}/auth/me`);

        if (response.ok) {
          const profile = await response.json();
          if (active) {
            setUser(profile);
            setToken(existingToken);
            setStoredUser(profile);
          }
        } else if (response.status === 401 || response.status === 403) {
          // Token expired or invalid
          if (active) {
            logout();
          }
        } else {
          // Non-auth backend error: keep cached user state if available to prevent lockout during transient issues
          const cachedUser = getStoredUser();
          if (active && cachedUser) {
            setUser(cachedUser);
            setToken(existingToken);
          }
        }
      } catch {
        // Backend offline: keep cached user for offline inspection if desired
        const cachedUser = getStoredUser();
        if (active && cachedUser) {
          setUser(cachedUser);
          setToken(existingToken);
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }

    verifyInitialSession();

    return () => {
      active = false;
    };
  }, [logout]);

  // Listen for unauthorized 401 events broadcast by authFetch on protected routes
  useEffect(() => {
    function handleUnauthorized() {
      setSessionExpiredNotice(true);
      logout();
    }

    window.addEventListener("caretrack:unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("caretrack:unauthorized", handleUnauthorized);
    };
  }, [logout]);

  /**
   * Log in clinician using JSON payload to POST /auth/login.
   * Never prints, stores, or logs credentials.
   */
  const login = useCallback(async (username, password) => {
    setSessionExpiredNotice(false);

    const cleanUsername = String(username || "").trim();
    const cleanPassword = String(password || "");

    if (!cleanUsername || !cleanPassword) {
      return {
        success: false,
        error: "Both username and password are required.",
      };
    }

    try {
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({
          username: cleanUsername,
          password: cleanPassword,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        let errorMsg = "Authentication failed.";
        if (response.status === 401) {
          errorMsg = data.detail || "Incorrect username or password.";
        } else if (response.status === 422) {
          errorMsg = data.detail || "Invalid login credentials format.";
        } else if (data.detail) {
          errorMsg = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
        }
        return { success: false, error: errorMsg };
      }

      // Successful authentication
      const accessToken = data.access_token;
      const userProfile = data.user;

      if (!accessToken) {
        return { success: false, error: "Server returned an invalid authentication response." };
      }

      setStoredToken(accessToken);
      setStoredUser(userProfile);
      setToken(accessToken);
      setUser(userProfile);

      return { success: true, user: userProfile };
    } catch {
      return {
        success: false,
        error: "Unable to connect to authentication server. Please ensure the backend is running.",
      };
    }
  }, []);

  const clearSessionNotice = useCallback(() => {
    setSessionExpiredNotice(false);
  }, []);

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(user && token),
      isLoading,
      sessionExpiredNotice,
      clearSessionNotice,
      login,
      logout,
    }),
    [user, token, isLoading, sessionExpiredNotice, clearSessionNotice, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
