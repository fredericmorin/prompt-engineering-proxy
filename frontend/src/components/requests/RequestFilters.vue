<script setup lang="ts">
import { ref, watch } from "vue";
import { useRequestsStore } from "@/stores/requests";

const store = useRequestsStore();

const protocol = ref(store.filters.protocol ?? "");
const model = ref(store.filters.model ?? "");

watch([protocol, model], () => {
  store.setFilters({
    protocol: protocol.value || undefined,
    model: model.value || undefined,
  });
});
</script>

<template>
  <div class="flex flex-wrap gap-2 p-3 border-b bg-muted/30">
    <select
      v-model="protocol"
      class="rounded border px-2 py-1 text-sm bg-background"
    >
      <option value="">All protocols</option>
      <option v-for="p in store.protocols" :key="p" :value="p">{{ p }}</option>
    </select>

    <select
      v-model="model"
      class="rounded border px-2 py-1 text-sm bg-background"
    >
      <option value="">All models</option>
      <option v-for="m in store.models" :key="m" :value="m">{{ m }}</option>
    </select>

    <span class="ml-auto text-xs text-muted-foreground self-center">
      {{ store.requests.length }} request{{
        store.requests.length !== 1 ? "s" : ""
      }}
    </span>
  </div>
</template>
