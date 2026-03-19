import { describe, it, expect } from "vitest";
import { deriveStatus, type ProxyRequest } from "../api";

function makeRequest(overrides: Partial<ProxyRequest> = {}): ProxyRequest {
  return {
    id: "test-id",
    server_id: null,
    protocol: "openai_chat",
    method: "POST",
    path: "/v1/chat/completions",
    model: null,
    response_status: null,
    is_streaming: false,
    duration_ms: null,
    ttfb_ms: null,
    prompt_tokens: null,
    completion_tokens: null,
    error: null,
    client_ip: null,
    parent_id: null,
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("deriveStatus", () => {
  it("returns 'pending' for a fresh request", () => {
    expect(deriveStatus(makeRequest())).toBe("pending");
  });

  it("returns 'streaming' when is_streaming is true and no response yet", () => {
    expect(deriveStatus(makeRequest({ is_streaming: true }))).toBe("streaming");
  });

  it("returns 'complete' when response_status is set", () => {
    expect(deriveStatus(makeRequest({ response_status: 200 }))).toBe(
      "complete",
    );
  });

  it("returns 'error' when error is set, even if response_status exists", () => {
    expect(
      deriveStatus(makeRequest({ response_status: 500, error: "timeout" })),
    ).toBe("error");
  });

  it("error takes priority over streaming", () => {
    expect(
      deriveStatus(
        makeRequest({ is_streaming: true, error: "connection reset" }),
      ),
    ).toBe("error");
  });
});
