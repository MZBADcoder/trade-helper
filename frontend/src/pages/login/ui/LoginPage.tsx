import { Link, Navigate } from "react-router-dom";

import { useSession } from "@/entities/session";
import { useAuthForm } from "@/features/auth-form";

export function LoginPage() {
  const { status } = useSession();
  const {
    mode,
    email,
    password,
    confirmPassword,
    busy,
    localError,
    sessionError,
    setMode,
    setEmail,
    setPassword,
    setConfirmPassword,
    submit,
  } = useAuthForm();

  if (status === "authenticated") {
    return <Navigate to="/terminal" replace />;
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

        <form onSubmit={submit} className="authForm">
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
          {sessionError ? <div className="errorText">{sessionError}</div> : null}

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
