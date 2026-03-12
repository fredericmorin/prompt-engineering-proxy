<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ headers: string | null }>();

const parsed = computed<Record<string, string> | null>(() => {
  if (!props.headers) return null;
  try {
    return JSON.parse(props.headers) as Record<string, string>;
  } catch {
    return null;
  }
});
</script>

<template>
  <div v-if="parsed && Object.keys(parsed).length">
    <table class="w-full text-xs font-mono">
      <tbody>
        <tr v-for="(value, key) in parsed" :key="key" class="border-b last:border-0">
          <td class="py-1 pr-4 align-top font-medium text-muted-foreground w-48 truncate">{{ key }}</td>
          <td class="py-1 break-all">{{ value }}</td>
        </tr>
      </tbody>
    </table>
  </div>
  <p v-else class="text-xs text-muted-foreground">No headers</p>
</template>
