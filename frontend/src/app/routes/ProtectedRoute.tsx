import React from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useSession } from "@/entities/session";

export function ProtectedRoute({ children }: { children: React.ReactElement }) {
  const { status } = useSession();
  const location = useLocation();

  if (status === "checking") {
    return <div className="authGate">Loading session...</div>;
  }

  if (status !== "authenticated") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
}
