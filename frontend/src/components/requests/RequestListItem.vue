<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { type ProxyRequest, deriveStatus } from "@/lib/api";
import StatusBadge from "@/components/common/StatusBadge.vue";
import TimingDisplay from "@/components/common/TimingDisplay.vue";

const props = defineProps<{ request: ProxyRequest }>();
const router = useRouter();

const status = computed(() => deriveStatus(props.request));

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString();
}
</script>

<template>
  <div
    class="flex items-center gap-3 px-4 py-2.5 hover:bg-muted/50 cursor-pointer border-b text-sm transition-colors"
    @click="router.push({ name: 'request-detail', params: { id: request.id } })"
  >
    <span class="w-28 shrink-0 rounded bg-muted text-center text-xs font-mono font-medium uppercase">
      {{ request.protocol }}
    </span>
    <span class="w-14 shrink-0 font-mono text-xs text-muted-foreground">{{
      request.method
    }}</span>
    <span class="flex-1 truncate font-mono text-xs" :title="request.path">{{
      request.path
    }}</span>
    <span
      v-if="request.client_ip"
      class="hidden lg:block shrink-0 max-w-28 truncate text-xs font-mono text-muted-foreground"
      :title="request.client_ip"
    >
      {{ request.client_ip }}
    </span>
    <span
      v-if="request.model"
      class="hidden sm:block shrink-0 max-w-32 truncate text-xs text-muted-foreground"
      :title="request.model"
    >
      {{ request.model }}
    </span>
    <StatusBadge :status="status" />
    <TimingDisplay
      :duration-ms="request.duration_ms"
      :ttfb-ms="request.ttfb_ms"
    />
    <span
      class="w-20 shrink-0 text-right text-xs text-muted-foreground tabular-nums"
    >
      {{ formatTime(request.created_at) }}
    </span>
  </div>
</template>
