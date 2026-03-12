<script setup lang="ts">
import { onMounted } from "vue";
import { useRequestsStore } from "@/stores/requests";
import { useSSE } from "@/composables/useSSE";
import RequestFilters from "@/components/requests/RequestFilters.vue";
import RequestList from "@/components/requests/RequestList.vue";

const store = useRequestsStore();
const sse = useSSE("/api/events");

sse.on("request.started", store.handleSSEEvent);
sse.on("request.completed", store.handleSSEEvent);
sse.on("request.error", store.handleSSEEvent);

onMounted(() => {
  store.fetchRequests();
});
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex items-center justify-between px-4 py-3 border-b">
      <h2 class="text-lg font-semibold">Live Request Feed</h2>
      <span
        :class="[
          'flex items-center gap-1.5 text-xs',
          sse.connected.value ? 'text-green-600' : 'text-muted-foreground',
        ]"
      >
        <span
          :class="['inline-block h-1.5 w-1.5 rounded-full', sse.connected.value ? 'bg-green-500' : 'bg-gray-400']"
        />
        {{ sse.connected.value ? "Live" : "Connecting…" }}
      </span>
    </div>

    <RequestFilters />
    <RequestList />
  </div>
</template>
