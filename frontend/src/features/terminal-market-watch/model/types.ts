import { type IndicatorBundle, type MarketBar, type MarketSnapshot } from "@/entities/market";
import { type OptionChainItem, type OptionContract } from "@/entities/options";
import { type WatchlistItem } from "@/entities/watchlist";

export type TimeframeKey = "minute" | "day" | "week" | "month";
export type StreamStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "degraded"
  | "disconnected";
export type StreamSource = "WS" | "REST";
export type DataLatency = "real-time" | "delayed";
export type OptionTypeFilter = "all" | "call" | "put";

export type DetailSnapshot = {
  bars: MarketBar[];
  indicators: IndicatorBundle | null;
  timeframe: TimeframeKey | null;
  loading: boolean;
  error: string | null;
  updatedAt: string | null;
  source: string | null;
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
  lastSyncAt: string | null;
  lastError: string | null;

  expirations: ExpirationItem[];
  expirationsBusy: boolean;
  expirationsError: string | null;
  selectedExpiration: string | null;
  setSelectedExpiration: (value: string | null) => void;

  optionTypeFilter: OptionTypeFilter;
  setOptionTypeFilter: (value: OptionTypeFilter) => void;
  optionChain: OptionChainItem[];
  chainBusy: boolean;
  chainError: string | null;

  selectedContractTicker: string | null;
  setSelectedContractTicker: (value: string | null) => void;
  contractDetail: OptionContract | null;
  contractBusy: boolean;
  contractError: string | null;

  loadExpirations: (underlying: string) => Promise<void>;
  loadOptionChainData: (underlying: string, expiration: string) => Promise<void>;
};
