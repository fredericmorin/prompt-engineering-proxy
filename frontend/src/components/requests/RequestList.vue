<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import { useRequestsStore } from "@/stores/requests";
import RequestListItem from "./RequestListItem.vue";

const store = useRequestsStore();
const listEl = ref<HTMLElement | null>(null);
const userScrolled = ref(false);

watch(
  () => store.requests.length,
  async () => {
    if (!userScrolled.value) {
      await nextTick();
      if (listEl.value) listEl.value.scrollTop = 0;
    }
  },
);

function onScroll() {
  if (!listEl.value) return;
  userScrolled.value = listEl.value.scrollTop > 10;
}
</script>

<template>
  <div ref="listEl" class="flex-1 overflow-y-auto" @scroll="onScroll">
    <div v-if="store.loading && store.requests.length === 0" class="p-8 text-center text-sm text-muted-foreground">
      Loading…
    </div>
    <div v-else-if="store.requests.length === 0" class="p-8 text-center text-sm text-muted-foreground">
      No requests captured yet. Send a request through the proxy to get started.
    </div>
    <RequestListItem
      v-for="req in store.requests"
      :key="req.id"
      :request="req"
    />
  </div>
</template>
