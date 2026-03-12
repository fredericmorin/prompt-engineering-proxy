<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";

const props = defineProps<{ requestId: string }>();

const tokens = ref("");
const done = ref(false);
const error = ref(false);
let es: EventSource | null = null;

function extractDelta(data: string): string {
  if (data === "[DONE]") return "";
  try {
    const obj = JSON.parse(data) as Record<string, unknown>;
    const choices = obj.choices as
      | Array<{ delta?: { content?: string } }>
      | undefined;
    return choices?.[0]?.delta?.content ?? "";
  } catch {
    return "";
  }
}

onMounted(() => {
  es = new EventSource(`/api/requests/${props.requestId}/stream`);

  es.onmessage = (evt) => {
    try {
      const payload = JSON.parse(evt.data) as Record<string, unknown>;
      if (payload.type === "done") {
        done.value = true;
        es?.close();
        return;
      }
      if (payload.type === "chunk") {
        const chunk = (payload.data as Record<string, string>)?.chunk ?? "";
        tokens.value += extractDelta(chunk);
      }
    } catch {
      // ignore
    }
  };

  es.onerror = () => {
    error.value = true;
    es?.close();
  };
});

onUnmounted(() => {
  es?.close();
});
</script>

<template>
  <div
    class="rounded bg-muted p-3 text-xs font-mono leading-relaxed max-h-96 overflow-auto"
  >
    <span v-if="tokens">{{ tokens }}</span>
    <span v-else class="text-muted-foreground">Waiting for tokens…</span>
    <span
      v-if="!done && !error"
      class="inline-block w-1.5 h-3 bg-current animate-pulse ml-0.5 align-middle"
    />
    <div v-if="done" class="mt-2 text-muted-foreground">Stream complete</div>
    <div v-if="error" class="mt-2 text-red-500">Stream error</div>
  </div>
</template>
