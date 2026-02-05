import React from "react";
import { Route, Routes } from "react-router-dom";

import { DashboardPage } from "@/pages/dashboard";
import { SettingsPage } from "@/pages/settings";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/settings" element={<SettingsPage />} />
    </Routes>
  );
}
