<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { PenTool, GitCompare } from "lucide-vue-next";
import { getRequest, type ProxyRequestDetail } from "@/lib/api";
import { useSSE } from "@/composables/useSSE";
import RequestDetail from "@/components/requests/RequestDetail.vue";

const route = useRoute();
const router = useRouter();

const request = ref<ProxyRequestDetail | null>(null);
const notFound = ref(false);

async function load(id: string) {
  try {
    request.value = await getRequest(id);
    notFound.value = false;
  } catch {
    notFound.value = true;
  }
}

// Reload when a completion/error event arrives for this request
const sse = useSSE("/api/events");
sse.on("request.completed", (evt) => {
  if (evt.request_id === route.params.id) load(evt.request_id as string);
});
sse.on("request.error", (evt) => {
  if (evt.request_id === route.params.id) load(evt.request_id as string);
});

onMounted(() => load(route.params.id as string));

watch(
  () => route.params.id,
  (id) => {
    if (id) load(id as string);
  },
);
</script>

<template>
  <div class="h-full overflow-y-auto">
    <div class="flex items-center gap-3 px-4 py-3 border-b">
      <button
        class="text-sm text-muted-foreground hover:text-foreground"
        @click="router.push({ name: 'dashboard' })"
      >
        ← Back
      </button>
      <h2 class="text-lg font-semibold">Request Detail</h2>
      <span class="font-mono text-xs text-muted-foreground">{{
        route.params.id
      }}</span>
      <div class="ml-auto flex items-center gap-2">
        <button
          v-if="request?.parent_id"
          class="flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium hover:bg-gray-50"
          @click="
            router.push({
              name: 'compare',
              query: { a: request!.parent_id, b: route.params.id },
            })
          "
        >
          <GitCompare class="h-3.5 w-3.5" />
          Compare with original
        </button>
        <button
          v-if="request"
          class="flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium hover:bg-gray-50"
          @click="
            router.push({ name: 'editor', query: { from: route.params.id } })
          "
        >
          <PenTool class="h-3.5 w-3.5" />
          Edit in Editor
        </button>
      </div>
    </div>

    <div v-if="notFound" class="p-8 text-center text-sm text-muted-foreground">
      Request not found.
    </div>
    <div
      v-else-if="!request"
      class="p-8 text-center text-sm text-muted-foreground"
    >
      Loading…
    </div>
    <RequestDetail v-else :request="request" />
  </div>
</template>
