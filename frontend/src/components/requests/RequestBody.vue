<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ body: string | null; label?: string }>();

const formatted = computed(() => {
  if (!props.body) return null;
  try {
    return JSON.stringify(JSON.parse(props.body), null, 2);
  } catch {
    return props.body;
  }
});
</script>

<template>
  <div v-if="formatted">
    <pre class="overflow-auto rounded bg-muted p-3 text-xs font-mono leading-relaxed max-h-96">{{ formatted }}</pre>
  </div>
  <p v-else class="text-xs text-muted-foreground">{{ props.label ?? "No body" }}</p>
</template>
