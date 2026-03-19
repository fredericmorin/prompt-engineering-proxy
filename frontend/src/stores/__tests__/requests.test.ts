import { describe, it, expect, vi, beforeEach } from "vitest";
import { setActivePinia, createPinia } from "pinia";
import { useRequestsStore } from "../requests";
import type { ProxyEvent, ProxyRequest } from "@/lib/api";

// Mock the api module
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    listRequests: vi.fn().mockResolvedValue([]),
    getRequest: vi.fn().mockResolvedValue({
      id: "req-1",
      protocol: "openai_chat",
      method: "POST",
      path: "/v1/chat/completions",
      model: "gpt-4",
      response_status: 200,
      is_streaming: false,
      duration_ms: 100,
      ttfb_ms: 50,
      prompt_tokens: 10,
      completion_tokens: 20,
      error: null,
      client_ip: null,
      parent_id: null,
      created_at: "2026-01-01T00:00:00Z",
      server_id: null,
      request_headers: "{}",
      request_body: "{}",
      response_headers: "{}",
      response_body: "{}",
    }),
  };
});

describe("useRequestsStore", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("starts with empty state", () => {
    const store = useRequestsStore();
    expect(store.requests).toEqual([]);
    expect(store.loading).toBe(false);
    expect(store.filters).toEqual({});
  });

  it("fetchRequests sets loading and populates requests", async () => {
    const { listRequests } = await import("@/lib/api");
    const mockRequests: ProxyRequest[] = [
      {
        id: "r1",
        server_id: null,
        protocol: "openai_chat",
        method: "POST",
        path: "/v1/chat/completions",
        model: "gpt-4",
        response_status: 200,
        is_streaming: false,
        duration_ms: 100,
        ttfb_ms: 50,
        prompt_tokens: 10,
        completion_tokens: 20,
        error: null,
        client_ip: null,
        parent_id: null,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];
    vi.mocked(listRequests).mockResolvedValueOnce(mockRequests);

    const store = useRequestsStore();
    await store.fetchRequests();

    expect(store.loading).toBe(false);
    expect(store.requests).toEqual(mockRequests);
    expect(listRequests).toHaveBeenCalledWith({ limit: 100 });
  });

  it("protocols computed extracts unique sorted protocols", async () => {
    const { listRequests } = await import("@/lib/api");
    vi.mocked(listRequests).mockResolvedValueOnce([
      { id: "1", protocol: "anthropic" } as ProxyRequest,
      { id: "2", protocol: "openai_chat" } as ProxyRequest,
      { id: "3", protocol: "anthropic" } as ProxyRequest,
    ]);

    const store = useRequestsStore();
    await store.fetchRequests();

    expect(store.protocols).toEqual(["anthropic", "openai_chat"]);
  });

  it("models computed extracts unique sorted models, excluding null", async () => {
    const { listRequests } = await import("@/lib/api");
    vi.mocked(listRequests).mockResolvedValueOnce([
      { id: "1", model: "gpt-4" } as ProxyRequest,
      { id: "2", model: null } as ProxyRequest,
      { id: "3", model: "claude-3" } as ProxyRequest,
      { id: "4", model: "gpt-4" } as ProxyRequest,
    ]);

    const store = useRequestsStore();
    await store.fetchRequests();

    expect(store.models).toEqual(["claude-3", "gpt-4"]);
  });

  it("handleSSEEvent triggers getRequest fetch for request.started", async () => {
    const { getRequest } = await import("@/lib/api");
    const store = useRequestsStore();

    const event: ProxyEvent = {
      type: "request.started",
      request_id: "req-1",
      data: null,
      timestamp: "2026-01-01T00:00:00Z",
    };

    store.handleSSEEvent(event);

    // refreshRequest calls getRequest; it merges into the list only if
    // the request already exists (by findIndex), so the store stays empty
    // here — we just verify the fetch was attempted.
    await vi.waitFor(() => {
      expect(getRequest).toHaveBeenCalledWith("req-1");
    });
  });

  it("handleSSEEvent calls refreshRequest for request.completed", async () => {
    const { getRequest } = await import("@/lib/api");
    const store = useRequestsStore();
    // Seed an existing request so the refresh path merges
    store.requests = [{ id: "req-1", protocol: "openai_chat" } as ProxyRequest];

    const event: ProxyEvent = {
      type: "request.completed",
      request_id: "req-1",
      data: null,
      timestamp: "2026-01-01T00:00:00Z",
    };

    store.handleSSEEvent(event);

    await vi.waitFor(() => {
      expect(getRequest).toHaveBeenCalledWith("req-1");
    });
  });

  it("setFilters updates filters and re-fetches", async () => {
    const { listRequests } = await import("@/lib/api");
    vi.mocked(listRequests).mockResolvedValue([]);

    const store = useRequestsStore();
    store.setFilters({ protocol: "anthropic" });

    expect(store.filters).toEqual({ protocol: "anthropic" });
    // setFilters calls fetchRequests without await — use waitFor to
    // handle the case where the mock is called after a microtask tick.
    await vi.waitFor(() => {
      expect(listRequests).toHaveBeenCalledWith({
        limit: 100,
        protocol: "anthropic",
      });
    });
  });
});
