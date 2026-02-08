import React from "react";
import { Link } from "react-router-dom";

import { useSession } from "@/entities/session";

export function HomePage() {
  const { status } = useSession();
  const canOpenTerminal = status === "authenticated";

  return (
    <main className="homePage">
      <section className="heroCard">
        <div className="heroEyebrow">PRE-MARKET TO CLOSE</div>
        <h1 className="heroTitle">Trade The Tape With A Focused Signal Console</h1>
        <p className="heroText">
          Build a watchlist, inspect K-lines fast, and keep core indicators in one screen before IV modules are
          introduced.
        </p>
        <div className="heroActions">
          <Link to={canOpenTerminal ? "/terminal" : "/login"} className="btn heroPrimary">
            {canOpenTerminal ? "Open Terminal" : "Login"}
          </Link>
          <Link to="/demo" className="btn btnSecondary heroSecondary">
            Try Demo
          </Link>
          <a href="#overview" className="btn btnSecondary heroSecondary">
            Overview
          </a>
        </div>
      </section>

      <section id="overview" className="featureGrid">
        <article className="featurePanel">
          <h2>Watchlist-first Workflow</h2>
          <p>Add symbols quickly and jump to per-ticker detail without leaving the main terminal.</p>
        </article>
        <article className="featurePanel">
          <h2>Chart + Indicators</h2>
          <p>See MA, MACD, BOLL, RSI and VOL generated from market bars in one compact layout.</p>
        </article>
        <article className="featurePanel">
          <h2>5-slot Detail Tabs</h2>
          <p>Pin up to five symbols, switch instantly, and keep context between candidates.</p>
        </article>
      </section>
    </main>
  );
}
