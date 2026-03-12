<script setup lang="ts">
import type { RequestStatus } from "@/lib/api";

const props = defineProps<{ status: RequestStatus }>();

const config: Record<RequestStatus, { label: string; cls: string }> = {
  pending: { label: "Pending", cls: "bg-yellow-100 text-yellow-800" },
  streaming: {
    label: "Streaming",
    cls: "bg-blue-100 text-blue-800 animate-pulse",
  },
  complete: { label: "Complete", cls: "bg-green-100 text-green-800" },
  error: { label: "Error", cls: "bg-red-100 text-red-800" },
};
</script>

<template>
  <span
    :class="[
      'inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium',
      config[props.status].cls,
    ]"
  >
    {{ config[props.status].label }}
  </span>
</template>
