export const API_BASE = "/api/v1";

export async function readJson<T>(resp: Response): Promise<T | null> {
  try {
    return (await resp.json()) as T;
  } catch {
    return null;
  }
}
