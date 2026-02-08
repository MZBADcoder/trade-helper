import React from "react";

import { getCurrentUser, login as loginApi, register as registerApi } from "../api/sessionApi";
import { type AuthPayload, type SessionStatus, type SessionUser } from "./types";

type SessionContextValue = {
  status: SessionStatus;
  token: string | null;
  user: SessionUser | null;
  error: string | null;
  login: (payload: AuthPayload) => Promise<void>;
  register: (payload: AuthPayload) => Promise<void>;
  logout: () => void;
  clearError: () => void;
};

const TOKEN_KEY = "trader_helper_access_token";

const SessionContext = React.createContext<SessionContextValue | undefined>(undefined);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = React.useState<SessionStatus>("checking");
  const [token, setToken] = React.useState<string | null>(null);
  const [user, setUser] = React.useState<SessionUser | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    const storedToken = window.localStorage.getItem(TOKEN_KEY);

    if (!storedToken) {
      setStatus("anonymous");
      return;
    }

    setToken(storedToken);

    getCurrentUser(storedToken)
      .then((currentUser) => {
        if (cancelled) return;
        setUser(currentUser);
        setStatus("authenticated");
      })
      .catch(() => {
        if (cancelled) return;
        window.localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
        setStatus("anonymous");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = React.useCallback(async (payload: AuthPayload) => {
    setError(null);
    const access = await loginApi(payload);
    window.localStorage.setItem(TOKEN_KEY, access.access_token);

    setToken(access.access_token);

    const currentUser = await getCurrentUser(access.access_token);
    setUser(currentUser);
    setStatus("authenticated");
  }, []);

  const register = React.useCallback(
    async (payload: AuthPayload) => {
      setError(null);
      await registerApi(payload);
      await login(payload);
    },
    [login]
  );

  const logout = React.useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setStatus("anonymous");
    setToken(null);
    setUser(null);
    setError(null);
  }, []);

  const clearError = React.useCallback(() => {
    setError(null);
  }, []);

  const value = React.useMemo<SessionContextValue>(
    () => ({
      status,
      token,
      user,
      error,
      login: async (payload) => {
        try {
          await login(payload);
        } catch (e: any) {
          setError(e?.message ?? "Login failed");
          throw e;
        }
      },
      register: async (payload) => {
        try {
          await register(payload);
        } catch (e: any) {
          setError(e?.message ?? "Register failed");
          throw e;
        }
      },
      logout,
      clearError
    }),
    [clearError, error, login, logout, register, status, token, user]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = React.useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within SessionProvider");
  }
  return context;
}
