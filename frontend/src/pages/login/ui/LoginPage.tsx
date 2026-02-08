import React from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { useSession } from "@/entities/session";

type AuthMode = "login" | "register";

export function LoginPage() {
  const { status, error, clearError, login, register } = useSession();
  const navigate = useNavigate();
  const location = useLocation();

  const [mode, setMode] = React.useState<AuthMode>("login");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [confirmPassword, setConfirmPassword] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [localError, setLocalError] = React.useState<string | null>(null);

  React.useEffect(() => {
    clearError();
    setLocalError(null);
  }, [mode, clearError]);

  if (status === "authenticated") {
    return <Navigate to="/terminal" replace />;
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLocalError(null);
    const trimmedEmail = email.trim();

    if (!trimmedEmail) {
      setLocalError("Email is required.");
      return;
    }

    if (password.length < 8) {
      setLocalError("Password must be at least 8 characters.");
      return;
    }

    if (mode === "register" && password !== confirmPassword) {
      setLocalError("Confirm password does not match.");
      return;
    }

    setBusy(true);
    try {
      if (mode === "login") {
        await login({ email: trimmedEmail, password });
      } else {
        await register({ email: trimmedEmail, password });
      }
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from || "/terminal", { replace: true });
    } catch {
      // handled by session context error
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="authPage">
      <section className="authCard">
        <div className="authModeBar">
          <button
            className={`chip ${mode === "login" ? "chipActive" : ""}`}
            type="button"
            onClick={() => setMode("login")}
          >
            Login
          </button>
          <button
            className={`chip ${mode === "register" ? "chipActive" : ""}`}
            type="button"
            onClick={() => setMode("register")}
          >
            Register
          </button>
        </div>

        <h1 className="authTitle">{mode === "login" ? "Enter Trading Terminal" : "Create Trading Account"}</h1>
        <p className="authHint">Use your account to access watchlist, charting and indicator analysis.</p>

        <form onSubmit={onSubmit} className="authForm">
          <label className="fieldLabel" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            className="input"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            required
          />

          <label className="fieldLabel" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            className="input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
          />

          {mode === "register" ? (
            <>
              <label className="fieldLabel" htmlFor="confirmPassword">
                Confirm Password
              </label>
              <input
                id="confirmPassword"
                className="input"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
                required
              />
            </>
          ) : null}

          {localError ? <div className="errorText">{localError}</div> : null}
          {error ? <div className="errorText">{error}</div> : null}

          <button className="btn authSubmit" type="submit" disabled={busy}>
            {busy ? "Processing..." : mode === "login" ? "Login" : "Register"}
          </button>

          <Link to="/demo" className="btn btnSecondary">
            Continue With Demo
          </Link>
        </form>

        <p className="muted">
          Prefer to browse first? <Link to="/">Back to home</Link>
        </p>
      </section>
    </main>
  );
}
