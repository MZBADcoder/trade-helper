export type OptionExpiration = {
  date: string;
  days_to_expiration: number;
  contract_count: number;
};

export type OptionExpirationsPayload = {
  underlying: string;
  expirations: OptionExpiration[];
  source: string;
  updated_at: string;
};

export type OptionType = "call" | "put";

export type OptionChainItem = {
  option_ticker: string;
  option_type: OptionType;
  strike: number;
  bid: number | null;
  ask: number | null;
  last: number | null;
  iv: number | null;
  volume: number | null;
  open_interest: number | null;
  updated_at: string;
  source: string;
};

export type OptionChainPayload = {
  underlying: string;
  expiration: string;
  items: OptionChainItem[];
  next_cursor: string | null;
};

export type OptionContractQuote = {
  bid: number | null;
  ask: number | null;
  last: number | null;
  updated_at: string;
};

export type OptionContractSession = {
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  open_interest: number | null;
};

export type OptionContractGreeks = {
  delta: number | null;
  gamma: number | null;
  theta: number | null;
  vega: number | null;
  iv: number | null;
};

export type OptionContract = {
  option_ticker: string;
  underlying: string;
  expiration: string;
  option_type: OptionType;
  strike: number;
  multiplier: number;
  quote: OptionContractQuote;
  session: OptionContractSession;
  greeks: OptionContractGreeks | null;
  source: string;
};
