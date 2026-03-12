import { onUnmounted, ref } from "vue";
import type { ProxyEvent } from "@/lib/api";

type EventHandler = (event: ProxyEvent) => void;

/**
 * Composable that opens an EventSource connection and calls registered handlers
 * for each parsed ProxyEvent. Reconnects automatically on error.
 */
export function useSSE(url: string) {
  const connected = ref(false);
  const handlers = new Map<string, Set<EventHandler>>();
  let es: EventSource | null = null;
  let retryDelay = 1000;
  let stopped = false;

  function connect() {
    if (stopped) return;
    es = new EventSource(url);

    es.onopen = () => {
      connected.value = true;
      retryDelay = 1000;
    };

    es.onmessage = (evt) => {
      try {
        const event: ProxyEvent = JSON.parse(evt.data);
        const set = handlers.get(event.type);
        if (set) set.forEach((h) => h(event));
        const all = handlers.get("*");
        if (all) all.forEach((h) => h(event));
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      connected.value = false;
      es?.close();
      es = null;
      if (!stopped) {
        setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 30_000);
      }
    };
  }

  function on(type: string, handler: EventHandler) {
    if (!handlers.has(type)) handlers.set(type, new Set());
    handlers.get(type)!.add(handler);
  }

  function off(type: string, handler: EventHandler) {
    handlers.get(type)?.delete(handler);
  }

  function close() {
    stopped = true;
    es?.close();
    es = null;
    connected.value = false;
  }

  connect();
  onUnmounted(close);

  return { connected, on, off, close };
}
