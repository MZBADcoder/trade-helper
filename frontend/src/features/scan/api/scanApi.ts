import { API_BASE, readJson } from "@/shared/api";

type ScanResponse = { task_id: string };

export async function enqueueScan(): Promise<ScanResponse> {
  const resp = await fetch(`${API_BASE}/scans/enqueue`, { method: "POST" });
  if (!resp.ok) throw new Error("Failed to enqueue scan");
  return (await readJson<ScanResponse>(resp)) ?? { task_id: "" };
}
