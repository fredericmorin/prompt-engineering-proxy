<script setup lang="ts">
const props = defineProps<{
  durationMs?: number | null;
  ttfbMs?: number | null;
}>();

function fmt(ms: number) {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}
</script>

<template>
  <span
    v-if="props.durationMs != null"
    class="text-xs text-muted-foreground tabular-nums"
  >
    <template v-if="props.ttfbMs != null">
      TTFB {{ fmt(props.ttfbMs) }} / {{ fmt(props.durationMs) }}
    </template>
    <template v-else>{{ fmt(props.durationMs) }}</template>
  </span>
  <span v-else class="text-xs text-muted-foreground">—</span>
</template>
