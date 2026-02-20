import { type IndicatorBundle, type MarketBar, type MarketSnapshot } from "@/entities/market";
import { type WatchlistItem } from "@/entities/watchlist";

export type TimeframeKey = "5m" | "15m" | "60m" | "day" | "week" | "month";
export type StreamStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "degraded"
  | "disconnected";
export type StreamSource = "WS" | "REST";
export type DataLatency = "real-time" | "delayed";

export type DetailSnapshot = {
  bars: MarketBar[];
  indicators: IndicatorBundle | null;
  timeframe: TimeframeKey | null;
  loading: boolean;
  error: string | null;
  updatedAt: string | null;
  source: string | null;
  barsDataSource: string | null;
};

export type ExpirationItem = {
  date: string;
  days_to_expiration: number;
};

export type TimeframeOption = {
  key: TimeframeKey;
  label: string;
};

export type TerminalMarketWatchViewModel = {
  userEmail: string | null;
  isAuthenticated: boolean;
  watchlist: WatchlistItem[];
  watchlistBusy: boolean;
  watchlistError: string | null;
  tickerInput: string;
  setTickerInput: (value: string) => void;
  refreshWatchlist: () => Promise<void>;
  onAddTicker: () => Promise<void>;
  onDeleteTicker: (ticker: string) => Promise<void>;
  onSelectTicker: (ticker: string) => void;

  activeTicker: string | null;
  snapshotMap: Record<string, MarketSnapshot>;
  timeframe: TimeframeKey;
  setTimeframe: (value: TimeframeKey) => void;
  activeDetail: DetailSnapshot | null;
  activeSnapshot: MarketSnapshot | null;
  latestBar: MarketBar | undefined;
  loadTickerDetail: (ticker: string, force?: boolean) => Promise<void>;
  refreshSnapshots: (symbols?: string[]) => Promise<void>;

  streamStatus: StreamStatus;
  streamSource: StreamSource;
  dataLatency: DataLatency;
  realtimeEnabled: boolean;
  delayMinutes: number;
  lastSyncAt: string | null;
  lastError: string | null;
};
