import React from "react";

import { AppRoutes } from "@/app/routes";
import { Topbar } from "@/widgets/topbar";

export function App() {
  return (
    <div className="shell">
      <Topbar />
      <AppRoutes />
    </div>
  );
}
