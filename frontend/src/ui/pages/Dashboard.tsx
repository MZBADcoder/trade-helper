import React from "react";

import { enqueueScan, listAlerts, listWatchlist } from "../api";

export function Dashboard() {
  const [alerts, setAlerts] = React.useState<any[]>([]);
  const [watchlist, setWatchlist] = React.useState<any[]>([]);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const refresh = React.useCallback(async () => {
    setError(null);
    try {
      const [a, w] = await Promise.all([listAlerts(), listWatchlist()]);
      setAlerts(a);
      setWatchlist(w);
    } catch (e: any) {
      setError(e?.message ?? "Failed to load");
    }
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  async function onScanNow() {
    setBusy(true);
    setError(null);
    try {
      await enqueueScan();
      await refresh();
    } catch (e: any) {
      setError(e?.message ?? "Failed to enqueue scan");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid">
      <section className="panel">
        <div className="panelHeader">
          <div className="panelTitle">Alerts</div>
          <div className="row">
            <button className="btn btnSecondary" onClick={refresh}>
              Refresh
            </button>
            <button className="btn" onClick={onScanNow} disabled={busy}>
              {busy ? "Enqueue…" : "Scan Now"}
            </button>
          </div>
        </div>
        <div className="panelBody">
          {error ? <div className="muted">{error}</div> : null}
          <table className="table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Priority</th>
                <th>Rule</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {alerts.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">
                    No alerts yet. Add tickers in Settings, then wait for the 15m schedule or click Scan Now.
                  </td>
                </tr>
              ) : (
                alerts.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <span className="pill">
                        <span className="pillDot" />
                        {a.ticker}
                      </span>
                    </td>
                    <td>
                      <span className="pill">
                        <span className={a.priority === "p95" ? "pillDot pillDotP95" : "pillDot"} />
                        {a.priority.toUpperCase()}
                      </span>
                    </td>
                    <td className="muted">
                      <code>{a.rule_key}</code>
                    </td>
                    <td>{a.message || <span className="muted">—</span>}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <aside className="panel">
        <div className="panelHeader">
          <div className="panelTitle">Watchlist</div>
          <div className="panelMeta">{watchlist.length} tickers</div>
        </div>
        <div className="panelBody">
          <div className="row">
            {watchlist.length === 0 ? (
              <div className="muted">No tickers configured.</div>
            ) : (
              watchlist.map((w) => (
                <span key={w.ticker} className="pill">
                  <span className="pillDot" />
                  {w.ticker}
                </span>
              ))
            )}
          </div>
          <div style={{ height: 12 }} />
          <div className="muted">
            Schedule: every <code>15m</code> via Celery Beat.
          </div>
        </div>
      </aside>
    </div>
  );
}

