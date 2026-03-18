<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { GitFork } from "lucide-vue-next";
import { type ProxyRequestDetail, deriveStatus } from "@/lib/api";
import StatusBadge from "@/components/common/StatusBadge.vue";
import TimingDisplay from "@/components/common/TimingDisplay.vue";
import RequestHeaders from "./RequestHeaders.vue";
import RequestBody from "./RequestBody.vue";
import StreamingView from "./StreamingView.vue";

const props = defineProps<{ request: ProxyRequestDetail }>();
const router = useRouter();

const status = computed(() => deriveStatus(props.request));
const isActivelyStreaming = computed(
  () =>
    props.request.is_streaming &&
    props.request.response_body === null &&
    !props.request.error,
);

type RawTab = "request" | "response";
const activeTab = ref<RawTab>("request");

// ── Message parsing ──────────────────────────────────────────────────────────

interface ParsedMessage {
  role: string;
  content: string;
}

function extractTextContent(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return (content as Record<string, unknown>[])
      .filter((b) => b.type === "text")
      .map((b) => String(b.text ?? ""))
      .join("\n");
  }
  return String(content ?? "");
}

const systemPrompt = computed<string | null>(() => {
  if (!props.request.request_body) return null;
  try {
    const body = JSON.parse(props.request.request_body) as Record<
      string,
      unknown
    >;
    // Anthropic: body.system (string or content array)
    if (body.system) return extractTextContent(body.system);
    // OpenAI: messages[].role === "system"
    const msgs = body.messages;
    if (Array.isArray(msgs)) {
      const sysMsg = (msgs as Record<string, unknown>[]).find(
        (m) => m.role === "system",
      );
      if (sysMsg) return extractTextContent(sysMsg.content);
    }
    return null;
  } catch {
    return null;
  }
});

const conversationMessages = computed<ParsedMessage[]>(() => {
  if (!props.request.request_body) return [];
  try {
    const body = JSON.parse(props.request.request_body) as Record<
      string,
      unknown
    >;
    const msgs = body.messages;
    if (!Array.isArray(msgs)) return [];
    return (msgs as Record<string, unknown>[])
      .filter((m) => m.role !== "system")
      .map((m) => ({
        role: String(m.role ?? ""),
        content: extractTextContent(m.content),
      }));
  } catch {
    return [];
  }
});

const assistantResponse = computed<string | null>(() => {
  if (!props.request.response_body) return null;
  try {
    const body = JSON.parse(props.request.response_body) as Record<
      string,
      unknown
    >;
    // OpenAI Chat: choices[0].message.content
    const choices = body.choices as
      | Array<{ message?: { content?: unknown } }>
      | undefined;
    if (choices?.[0]?.message?.content !== undefined) {
      return extractTextContent(choices[0].message.content);
    }
    // Anthropic: content[].text
    if (Array.isArray(body.content)) {
      const text = (body.content as Record<string, unknown>[])
        .filter((b) => b.type === "text")
        .map((b) => String(b.text ?? ""))
        .join("\n");
      if (text) return text;
    }
    return null;
  } catch {
    return null;
  }
});

const isMultiTurn = computed(() => conversationMessages.value.length > 1);

function forkAt(msgIndex: number) {
  router.push({
    name: "editor",
    query: { from: props.request.id, fork_at: String(msgIndex) },
  });
}
</script>

<template>
  <div class="flex overflow-hidden">
    <!-- ── Left panel: Rendered conversation ──────────────────────────────── -->
    <div class="flex min-w-0 flex-1 flex-col overflow-hidden border-r">
      <!-- Summary bar -->
      <div
        class="flex shrink-0 flex-wrap items-center gap-3 border-b bg-muted/30 px-4 py-2.5"
      >
        <StatusBadge :status="status" />
        <span class="font-mono text-xs font-medium text-muted-foreground"
          >{{ request.method }} {{ request.path }}</span
        >
        <span
          v-if="request.model"
          class="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground"
        >
          {{ request.model }}
        </span>
        <div class="ml-auto flex items-center gap-3 text-xs text-muted-foreground">
          <span v-if="request.prompt_tokens != null">
            ↑ {{ request.prompt_tokens }} / ↓
            {{ request.completion_tokens ?? "?" }} tokens
          </span>
          <TimingDisplay
            :duration-ms="request.duration_ms"
            :ttfb-ms="request.ttfb_ms"
          />
        </div>
      </div>

      <!-- Conversation thread -->
      <div class="flex-1 overflow-y-auto px-4 py-5 space-y-4">
        <!-- Error banner -->
        <div
          v-if="request.error"
          class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {{ request.error }}
        </div>

        <!-- System prompt -->
        <div
          v-if="systemPrompt"
          class="rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 px-4 py-3"
        >
          <div
            class="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground"
          >
            System
          </div>
          <pre
            class="whitespace-pre-wrap break-words font-sans text-xs leading-relaxed text-muted-foreground"
            >{{ systemPrompt }}</pre
          >
        </div>

        <!-- No messages placeholder -->
        <div
          v-if="conversationMessages.length === 0 && !systemPrompt"
          class="py-12 text-center text-sm text-muted-foreground"
        >
          No conversation messages
        </div>

        <!-- Message bubbles -->
        <div
          v-for="(msg, idx) in conversationMessages"
          :key="idx"
          class="group flex gap-3"
          :class="msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'"
        >
          <!-- Avatar -->
          <div
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold uppercase"
            :class="
              msg.role === 'user'
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
            "
          >
            {{
              msg.role === "user"
                ? "U"
                : msg.role === "assistant"
                  ? "A"
                  : msg.role[0].toUpperCase()
            }}
          </div>

          <!-- Bubble + fork button -->
          <div
            class="flex max-w-[80%] flex-col gap-1"
            :class="msg.role === 'user' ? 'items-end' : 'items-start'"
          >
            <div
              class="rounded-2xl px-4 py-2.5 text-sm leading-relaxed"
              :class="
                msg.role === 'user'
                  ? 'rounded-tr-sm bg-blue-500 text-white'
                  : 'rounded-tl-sm bg-muted text-foreground'
              "
            >
              <pre class="whitespace-pre-wrap break-words font-sans">{{
                msg.content
              }}</pre>
            </div>
            <!-- Fork button shown on hover for user turns in multi-turn conversations -->
            <button
              v-if="isMultiTurn && msg.role === 'user'"
              class="flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-muted-foreground opacity-0 transition-opacity hover:bg-purple-50 hover:text-purple-600 group-hover:opacity-100"
              title="Fork conversation from this turn"
              @click="forkAt(idx)"
            >
              <GitFork class="h-3 w-3" />
              Fork from here
            </button>
          </div>
        </div>

        <!-- Assistant response / streaming output -->
        <div
          v-if="isActivelyStreaming || assistantResponse !== null || request.response_body !== null"
          class="flex flex-row gap-3"
        >
          <!-- Avatar -->
          <div
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gray-200 text-[10px] font-bold text-gray-600 dark:bg-gray-700 dark:text-gray-300"
          >
            A
          </div>
          <!-- Bubble -->
          <div class="flex max-w-[80%] flex-col items-start gap-1">
            <div
              class="min-w-[120px] rounded-2xl rounded-tl-sm bg-muted px-4 py-2.5 text-sm leading-relaxed"
            >
              <template v-if="isActivelyStreaming">
                <StreamingView :request-id="request.id" />
              </template>
              <template v-else-if="assistantResponse !== null">
                <pre class="whitespace-pre-wrap break-words font-sans">{{
                  assistantResponse
                }}</pre>
              </template>
              <template v-else>
                <span class="text-xs text-muted-foreground"
                  >No response yet</span
                >
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Right panel: Raw request / response ────────────────────────────── -->
    <div class="flex w-[400px] shrink-0 flex-col overflow-hidden">
      <!-- Tab bar -->
      <div class="flex shrink-0 border-b bg-muted/20">
        <button
          class="border-b-2 px-4 py-2.5 text-xs font-medium transition-colors"
          :class="
            activeTab === 'request'
              ? 'border-foreground text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          "
          @click="activeTab = 'request'"
        >
          Request
        </button>
        <button
          class="border-b-2 px-4 py-2.5 text-xs font-medium transition-colors"
          :class="
            activeTab === 'response'
              ? 'border-foreground text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          "
          @click="activeTab = 'response'"
        >
          Response
          <span
            v-if="isActivelyStreaming"
            class="ml-1 text-[10px] text-blue-500 animate-pulse"
            >live</span
          >
        </button>
      </div>

      <!-- Tab content -->
      <div class="flex-1 overflow-y-auto">
        <!-- Request tab -->
        <template v-if="activeTab === 'request'">
          <div class="border-b px-4 py-3">
            <h4
              class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
            >
              Headers
            </h4>
            <RequestHeaders :headers="request.request_headers" />
          </div>
          <div class="px-4 py-3">
            <h4
              class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
            >
              Body
            </h4>
            <RequestBody :body="request.request_body" />
          </div>
        </template>

        <!-- Response tab -->
        <template v-else>
          <div class="border-b px-4 py-3">
            <h4
              class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
            >
              Headers
            </h4>
            <RequestHeaders :headers="request.response_headers" />
          </div>
          <div class="px-4 py-3">
            <h4
              class="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
            >
              Body
            </h4>
            <div
              v-if="isActivelyStreaming"
              class="rounded bg-muted px-3 py-2 text-xs text-muted-foreground animate-pulse"
            >
              Streaming response in progress…
            </div>
            <RequestBody
              v-else
              :body="request.response_body"
              label="No response body yet"
            />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
