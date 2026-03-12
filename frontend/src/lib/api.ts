const BASE_URL = import.meta.env.DEV ? "" : "";

export interface HealthResponse {
  status: string;
  database: boolean;
  redis: boolean;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await fetch(`${BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}

// ── Request types ────────────────────────────────────────────────────────────

export interface ProxyRequest {
  id: string;
  server_id: string | null;
  protocol: string;
  method: string;
  path: string;
  model: string | null;
  response_status: number | null;
  is_streaming: boolean;
  duration_ms: number | null;
  ttfb_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  error: string | null;
  parent_id: string | null;
  created_at: string;
}

export interface ProxyRequestDetail extends ProxyRequest {
  request_headers: string | null;
  request_body: string | null;
  response_headers: string | null;
  response_body: string | null;
}

export type RequestStatus = "pending" | "streaming" | "complete" | "error";

export function deriveStatus(req: ProxyRequest): RequestStatus {
  if (req.error) return "error";
  if (req.response_status !== null) return "complete";
  if (req.is_streaming) return "streaming";
  return "pending";
}

export interface ListRequestsParams {
  limit?: number;
  offset?: number;
  protocol?: string;
  model?: string;
}

export async function listRequests(
  params: ListRequestsParams = {},
): Promise<ProxyRequest[]> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  if (params.protocol) query.set("protocol", params.protocol);
  if (params.model) query.set("model", params.model);
  const qs = query.toString();
  const response = await fetch(`${BASE_URL}/api/requests${qs ? `?${qs}` : ""}`);
  if (!response.ok)
    throw new Error(`Failed to list requests: ${response.status}`);
  return response.json();
}

export async function getRequest(id: string): Promise<ProxyRequestDetail> {
  const response = await fetch(`${BASE_URL}/api/requests/${id}`);
  if (!response.ok)
    throw new Error(`Failed to get request: ${response.status}`);
  return response.json();
}

export async function deleteRequest(id: string): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/requests/${id}`, {
    method: "DELETE",
  });
  if (!response.ok && response.status !== 204)
    throw new Error(`Failed to delete request: ${response.status}`);
}

// ── SSE event type ───────────────────────────────────────────────────────────

export interface ProxyEvent {
  type: string;
  request_id: string;
  data: Record<string, unknown> | null;
  timestamp: string;
}
