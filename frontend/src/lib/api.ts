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
