import { API_BASE, readJson } from "@/shared/api";

import { type Alert } from "../model/types";

export async function listAlerts(): Promise<Alert[]> {
  const resp = await fetch(`${API_BASE}/alerts?limit=50`);
  if (!resp.ok) throw new Error("Failed to load alerts");
  return (await readJson<Alert[]>(resp)) ?? [];
}
