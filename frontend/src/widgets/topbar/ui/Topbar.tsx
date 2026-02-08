import React from "react";
import { NavLink } from "react-router-dom";

import { useSession } from "@/entities/session";

export function Topbar() {
  const { status, user, logout } = useSession();

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brandTitle">Trader Helper</div>
        <div className="brandSubtitle">market cockpit for signals, watchlists and execution context</div>
      </div>
      <div className="topbarRight">
        <nav className="nav">
          <NavChip to="/" end>
            Home
          </NavChip>
          <NavChip to="/demo">Demo</NavChip>
          <NavChip to={status === "authenticated" ? "/terminal" : "/login"}>
            {status === "authenticated" ? "Terminal" : "Login"}
          </NavChip>
        </nav>
        {status === "authenticated" ? (
          <div className="userSlot">
            <span className="userEmail">{user?.email}</span>
            <button className="btn btnSecondary" type="button" onClick={logout}>
              Logout
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}

type NavChipProps = {
  to: string;
  children: React.ReactNode;
  end?: boolean;
};

function NavChip({ to, children, end }: NavChipProps) {
  return (
    <NavLink to={to} className={({ isActive }) => `chip ${isActive ? "chipActive" : ""}`} end={end}>
      {children}
    </NavLink>
  );
}
