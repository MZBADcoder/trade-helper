import React from "react";
import { NavLink, Route, Routes } from "react-router-dom";

import { Dashboard } from "./pages/Dashboard";
import { Settings } from "./pages/Settings";

export function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="brandTitle">Trader Helper</div>
          <div className="brandSubtitle">IV Percentile alerts · FastAPI + Celery</div>
        </div>
        <nav className="nav">
          <NavChip to="/">Dashboard</NavChip>
          <NavChip to="/settings">Settings</NavChip>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </div>
  );
}

function NavChip({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) => `chip ${isActive ? "chipActive" : ""}`}
      end
    >
      {children}
    </NavLink>
  );
}

