import { apiRequest } from "@/shared/api";

import {
  type OptionChainPayload,
  type OptionContract,
  type OptionExpirationsPayload
} from "../model/types";

type OptionChainQuery = {
  token: string;
  underlying: string;
  expiration: string;
  strike_from?: number;
  strike_to?: number;
  option_type?: "call" | "put" | "all";
  limit?: number;
  cursor?: string;
};

export async function listOptionExpirations(
  token: string,
  underlying: string,
  limit = 12,
  includeExpired = false
): Promise<OptionExpirationsPayload> {
  return apiRequest<OptionExpirationsPayload>("/options/expirations", {
    token,
    query: {
      underlying,
      limit,
      include_expired: includeExpired
    }
  });
}

export async function listOptionChain(params: OptionChainQuery): Promise<OptionChainPayload> {
  return apiRequest<OptionChainPayload>("/options/chain", {
    token: params.token,
    query: {
      underlying: params.underlying,
      expiration: params.expiration,
      strike_from: params.strike_from,
      strike_to: params.strike_to,
      option_type: params.option_type,
      limit: params.limit,
      cursor: params.cursor
    }
  });
}

export async function getOptionContract(
  token: string,
  optionTicker: string,
  includeGreeks = true
): Promise<OptionContract> {
  return apiRequest<OptionContract>(`/options/contracts/${encodeURIComponent(optionTicker)}`, {
    token,
    query: {
      include_greeks: includeGreeks
    }
  });
}
