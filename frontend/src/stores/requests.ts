import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { listRequests, getRequest, type ProxyRequest, type ProxyRequestDetail, type ProxyEvent } from "@/lib/api";

export const useRequestsStore = defineStore("requests", () => {
  const requests = ref<ProxyRequest[]>([]);
  const loading = ref(false);
  const filters = ref<{ protocol?: string; model?: string }>({});

  const protocols = computed(() => [...new Set(requests.value.map((r) => r.protocol))].sort());
  const models = computed(() =>
    [...new Set(requests.value.map((r) => r.model).filter(Boolean) as string[])].sort(),
  );

  async function fetchRequests() {
    loading.value = true;
    try {
      requests.value = await listRequests({ limit: 100, ...filters.value });
    } finally {
      loading.value = false;
    }
  }

  async function refreshRequest(id: string) {
    const detail: ProxyRequestDetail = await getRequest(id);
    const idx = requests.value.findIndex((r) => r.id === id);
    if (idx >= 0) {
      // Merge updated fields into the list item (list items don't carry body fields)
      requests.value[idx] = { ...requests.value[idx], ...detail };
    }
  }

  function handleSSEEvent(event: ProxyEvent) {
    if (event.type === "request.started") {
      // Optimistically prepend a stub; refreshRequest fills in full data
      const existing = requests.value.find((r) => r.id === event.request_id);
      if (!existing) {
        refreshRequest(event.request_id).catch(() => {});
      }
    } else if (event.type === "request.completed" || event.type === "request.error") {
      refreshRequest(event.request_id).catch(() => {});
    }
  }

  function setFilters(f: { protocol?: string; model?: string }) {
    filters.value = f;
    fetchRequests();
  }

  return { requests, loading, filters, protocols, models, fetchRequests, handleSSEEvent, setFilters };
});
