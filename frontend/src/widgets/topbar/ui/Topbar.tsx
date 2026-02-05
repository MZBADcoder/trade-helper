import React from "react";
import { NavLink } from "react-router-dom";

export function Topbar() {
  return (
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
