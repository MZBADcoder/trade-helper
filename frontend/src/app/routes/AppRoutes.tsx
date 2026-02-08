import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { useSession } from "@/entities/session";
import { DemoTerminalPage } from "@/pages/demo-terminal";
import { HomePage } from "@/pages/home";
import { LoginPage } from "@/pages/login";
import { TerminalPage } from "@/pages/terminal";

import { ProtectedRoute } from "./ProtectedRoute";

export function AppRoutes() {
  const { status } = useSession();
  const fallbackPath = status === "authenticated" ? "/terminal" : "/";

  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/demo" element={<DemoTerminalPage />} />
      <Route
        path="/terminal"
        element={
          <ProtectedRoute>
            <TerminalPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to={fallbackPath} replace />} />
    </Routes>
  );
}
