export const API_BASE = "/api/v1";

export type ApiRequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  token?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
};

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const query = buildQueryString(options.query);
  const url = `${API_BASE}${path}${query}`;

  const headers = new Headers();
  if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  const resp = await fetch(url, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  });

  if (!resp.ok) {
    const errorBody = await readJson<{
      detail?: string;
      error?: {
        code?: string;
        message?: string;
      };
    }>(resp);
    const errorMessage = errorBody?.error?.message ?? errorBody?.detail ?? `${method} ${path} failed`;
    if (errorBody?.error?.code) {
      throw new Error(`${errorBody.error.code}: ${errorMessage}`);
    }
    throw new Error(errorMessage);
  }

  if (resp.status === 204) {
    return undefined as T;
  }

  return (await readJson<T>(resp)) as T;
}

function buildQueryString(query: ApiRequestOptions["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    params.set(key, String(value));
  });
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

export async function readJson<T>(resp: Response): Promise<T | null> {
  try {
    return (await resp.json()) as T;
  } catch {
    return null;
  }
}
