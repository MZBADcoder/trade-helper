import React from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useSession } from "@/entities/session";

export type AuthMode = "login" | "register";

export type AuthFormModel = {
  mode: AuthMode;
  email: string;
  password: string;
  confirmPassword: string;
  busy: boolean;
  localError: string | null;
  sessionError: string | null;
  setMode: React.Dispatch<React.SetStateAction<AuthMode>>;
  setEmail: React.Dispatch<React.SetStateAction<string>>;
  setPassword: React.Dispatch<React.SetStateAction<string>>;
  setConfirmPassword: React.Dispatch<React.SetStateAction<string>>;
  submit: (event: React.FormEvent<HTMLFormElement>) => Promise<void>;
};

export function useAuthForm(): AuthFormModel {
  const { error, clearError, login, register } = useSession();
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

  const submit = React.useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
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
        // session context handles remote errors
      } finally {
        setBusy(false);
      }
    },
    [confirmPassword, email, location.state, login, mode, navigate, password, register],
  );

  return {
    mode,
    email,
    password,
    confirmPassword,
    busy,
    localError,
    sessionError: error,
    setMode,
    setEmail,
    setPassword,
    setConfirmPassword,
    submit,
  };
}
