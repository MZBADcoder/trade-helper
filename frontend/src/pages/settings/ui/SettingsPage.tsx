import React from "react";

import {
  type WatchlistItem,
  addWatchlist,
  deleteWatchlist,
  listWatchlist
} from "@/entities/watchlist";

export function SettingsPage() {
  const [ticker, setTicker] = React.useState("");
  const [items, setItems] = React.useState<WatchlistItem[]>([]);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    setError(null);
    try {
      setItems(await listWatchlist());
    } catch (e: any) {
      setError(e?.message ?? "Failed to load watchlist");
    }
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  async function onAdd() {
    const t = ticker.trim().toUpperCase();
    if (!t) return;
    setError(null);
    try {
      await addWatchlist(t);
      setTicker("");
      await refresh();
    } catch (e: any) {
      setError(e?.message ?? "Failed to add");
    }
  }

  async function onDelete(t: string) {
    setError(null);
    try {
      await deleteWatchlist(t);
      await refresh();
    } catch (e: any) {
      setError(e?.message ?? "Failed to delete");
    }
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <div className="panelTitle">Settings</div>
        <div className="panelMeta">Watchlist</div>
      </div>
      <div className="panelBody">
        <div className="row">
          <input
            className="input"
            placeholder="Add ticker (e.g. AAPL)"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onAdd();
            }}
          />
          <button className="btn" onClick={onAdd}>
            Add
          </button>
          <button className="btn btnSecondary" onClick={refresh}>
            Refresh
          </button>
        </div>

        {error ? (
          <div style={{ marginTop: 12 }} className="muted">
            {error}
          </div>
        ) : null}

        <div style={{ height: 14 }} />
        <table className="table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={2} className="muted">
                  No tickers configured yet.
                </td>
              </tr>
            ) : (
              items.map((it) => (
                <tr key={it.ticker}>
                  <td>
                    <span className="pill">
                      <span className="pillDot" />
                      {it.ticker}
                    </span>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button className="btn btnSecondary" onClick={() => onDelete(it.ticker)}>
                      Remove
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        <div style={{ height: 12 }} />
        <div className="muted">
          Backend API: <code>/api/v1</code> (proxied by Vite in dev).
        </div>
      </div>
    </section>
  );
}
