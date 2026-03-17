<script setup lang="ts">
import { ref, onMounted, onUnmounted } from "vue";
import { Square } from "lucide-vue-next";
import { stopStream } from "@/lib/api";

const props = defineProps<{ requestId: string }>();
const emit = defineEmits<{ done: []; stopped: [] }>();

const tokens = ref("");
const done = ref(false);
const stopped = ref(false);
const error = ref(false);
const stopping = ref(false);
let es: EventSource | null = null;

function extractDelta(data: string): string {
  if (data === "[DONE]") return "";
  try {
    const obj = JSON.parse(data) as Record<string, unknown>;
    // OpenAI Chat SSE: choices[0].delta.content
    const choices = obj.choices as
      | Array<{ delta?: { content?: string } }>
      | undefined;
    if (choices?.[0]?.delta?.content !== undefined) {
      return choices[0].delta.content ?? "";
    }
    // Ollama Chat NDJSON: message.content
    const message = obj.message as { content?: string } | undefined;
    if (message?.content !== undefined) return message.content;
    // Ollama Generate NDJSON: response (string token)
    if (typeof obj.response === "string") return obj.response;
    return "";
  } catch {
    return "";
  }
}

async function handleStop() {
  stopping.value = true;
  try {
    await stopStream(props.requestId);
  } catch {
    // ignore — the stream may have already finished
  } finally {
    stopping.value = false;
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
        emit("done");
        return;
      }
      if (payload.type === "stopped") {
        stopped.value = true;
        es?.close();
        emit("stopped");
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
  <div class="space-y-2">
    <div
      class="rounded bg-muted p-3 text-xs font-mono leading-relaxed max-h-96 overflow-auto"
    >
      <span v-if="tokens">{{ tokens }}</span>
      <span v-else class="text-muted-foreground">Waiting for tokens…</span>
      <span
        v-if="!done && !stopped && !error"
        class="inline-block w-1.5 h-3 bg-current animate-pulse ml-0.5 align-middle"
      />
      <div v-if="done" class="mt-2 text-muted-foreground">Stream complete</div>
      <div v-if="stopped" class="mt-2 text-yellow-600 dark:text-yellow-400">
        Stream stopped — partial response saved
      </div>
      <div v-if="error" class="mt-2 text-red-500">Stream error</div>
    </div>
    <div v-if="!done && !stopped && !error" class="flex justify-end">
      <button
        type="button"
        :disabled="stopping"
        class="inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium border border-destructive text-destructive hover:bg-destructive hover:text-destructive-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        @click="handleStop"
      >
        <Square class="h-3 w-3" />
        {{ stopping ? "Stopping…" : "Stop" }}
      </button>
    </div>
  </div>
</template>
