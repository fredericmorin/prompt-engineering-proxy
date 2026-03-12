<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Plus, Trash2, Send, RefreshCw, Loader2 } from "lucide-vue-next";
import { useServersStore } from "@/stores/servers";
import {
  listServerModels,
  sendRequest,
  getRequest,
  type ModelInfo,
  type SendResponse,
} from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

interface Message {
  role: "system" | "user" | "assistant";
  content: string;
}

// ── State ──────────────────────────────────────────────────────────────────

const route = useRoute();
const router = useRouter();
const serversStore = useServersStore();

const selectedServerId = ref("");
const model = ref("");
const messages = ref<Message[]>([{ role: "user", content: "" }]);
const temperature = ref(1.0);
const maxTokens = ref<number | null>(null);
const topP = ref<number | null>(null);
const systemPrompt = ref("");

const models = ref<ModelInfo[]>([]);
const loadingModels = ref(false);
const modelsError = ref("");

const sending = ref(false);
const sendError = ref("");
const response = ref<SendResponse | null>(null);
const clonedFrom = ref<string | null>(null);

// ── Computed ──────────────────────────────────────────────────────────────

const responseText = computed(() => {
  if (!response.value) return null;
  const body = response.value.body;
  // OpenAI Chat format
  const choices = body.choices;
  if (Array.isArray(choices) && choices.length > 0) {
    const first = choices[0] as Record<string, unknown>;
    const msg = first.message as Record<string, string> | undefined;
    if (msg?.content) return msg.content;
    // streaming delta fallback
    const delta = first.delta as Record<string, string> | undefined;
    if (delta?.content) return delta.content;
  }
  // Anthropic format
  const content = body.content;
  if (Array.isArray(content)) {
    return content
      .filter(
        (c): c is Record<string, unknown> =>
          typeof c === "object" && c !== null,
      )
      .map((c) => (c.type === "text" ? String(c.text ?? "") : ""))
      .join("");
  }
  return JSON.stringify(body, null, 2);
});

// ── Methods ──────────────────────────────────────────────────────────────

async function fetchModels() {
  if (!selectedServerId.value) return;
  loadingModels.value = true;
  modelsError.value = "";
  models.value = [];
  try {
    models.value = await listServerModels(selectedServerId.value);
  } catch (e) {
    modelsError.value =
      e instanceof Error ? e.message : "Failed to fetch models";
  } finally {
    loadingModels.value = false;
  }
}

function addMessage() {
  const lastRole = messages.value.at(-1)?.role ?? "user";
  const nextRole: Message["role"] = lastRole === "user" ? "assistant" : "user";
  messages.value.push({ role: nextRole, content: "" });
}

function removeMessage(idx: number) {
  messages.value.splice(idx, 1);
}

async function submit() {
  if (!selectedServerId.value) {
    sendError.value = "Please select a server";
    return;
  }
  if (!model.value.trim()) {
    sendError.value = "Please enter a model name";
    return;
  }

  sending.value = true;
  sendError.value = "";
  response.value = null;

  const body: Record<string, unknown> = {
    model: model.value.trim(),
    messages: buildMessages(),
  };
  if (temperature.value !== 1.0) body.temperature = temperature.value;
  if (maxTokens.value !== null) body.max_tokens = maxTokens.value;
  if (topP.value !== null) body.top_p = topP.value;

  try {
    response.value = await sendRequest(selectedServerId.value, body);
  } catch (e) {
    sendError.value = e instanceof Error ? e.message : "Request failed";
  } finally {
    sending.value = false;
  }
}

function buildMessages(): Message[] {
  const result: Message[] = [];
  if (systemPrompt.value.trim()) {
    result.push({ role: "system", content: systemPrompt.value.trim() });
  }
  result.push(...messages.value.filter((m) => m.content.trim() !== ""));
  return result;
}

function viewInDashboard() {
  if (response.value) {
    router.push({
      name: "request-detail",
      params: { id: response.value.request_id },
    });
  }
}

// ── Clone from captured request ──────────────────────────────────────────

async function loadFromRequest(id: string) {
  try {
    const req = await getRequest(id);
    if (!req.request_body) return;
    const body = JSON.parse(req.request_body) as Record<string, unknown>;
    if (typeof body.model === "string") model.value = body.model;

    const rawMessages = body.messages;
    if (Array.isArray(rawMessages)) {
      const sys = rawMessages.find(
        (m): m is Record<string, string> =>
          typeof m === "object" && m !== null && m.role === "system",
      );
      if (sys?.content) systemPrompt.value = String(sys.content);
      messages.value = rawMessages
        .filter(
          (m): m is Record<string, string> =>
            typeof m === "object" && m !== null && m.role !== "system",
        )
        .map((m) => ({
          role: m.role as Message["role"],
          content: String(m.content ?? ""),
        }));
      if (messages.value.length === 0)
        messages.value = [{ role: "user", content: "" }];
    }

    if (typeof body.temperature === "number")
      temperature.value = body.temperature;
    if (typeof body.max_tokens === "number") maxTokens.value = body.max_tokens;
    if (typeof body.top_p === "number") topP.value = body.top_p;

    // Try to match server
    if (req.server_id) selectedServerId.value = req.server_id;

    clonedFrom.value = id;
  } catch {
    // silently ignore if request not found
  }
}

// ── Lifecycle ─────────────────────────────────────────────────────────────

onMounted(async () => {
  await serversStore.fetchServers();
  // Pre-select default server
  const def = serversStore.servers.find((s) => s.is_default);
  if (def) selectedServerId.value = def.id;
  else if (serversStore.servers.length > 0)
    selectedServerId.value = serversStore.servers[0].id;

  // Load from captured request if query param provided
  const fromId = route.query.from as string | undefined;
  if (fromId) await loadFromRequest(fromId);
});

watch(selectedServerId, () => {
  models.value = [];
  modelsError.value = "";
});
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden">
    <!-- Header bar -->
    <div class="flex items-center gap-3 border-b px-4 py-3 shrink-0">
      <h2 class="text-base font-semibold">Editor</h2>
      <span
        v-if="clonedFrom"
        class="rounded-full bg-blue-100 px-2 py-0.5 text-xs text-blue-700"
      >
        cloned from {{ clonedFrom.slice(0, 10) }}…
      </span>
    </div>

    <!-- Main content -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Left: messages + system prompt -->
      <div class="flex flex-1 flex-col overflow-y-auto p-4 gap-4 border-r">
        <!-- Server + model row -->
        <div class="flex gap-3 flex-wrap">
          <div class="flex-1 min-w-40">
            <label class="mb-1 block text-xs font-medium text-gray-600"
              >Server</label
            >
            <select
              v-model="selectedServerId"
              class="w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
            >
              <option value="" disabled>Select server…</option>
              <option
                v-for="s in serversStore.servers"
                :key="s.id"
                :value="s.id"
              >
                {{ s.name }}
              </option>
            </select>
            <div
              v-if="serversStore.servers.length === 0"
              class="mt-1 text-xs text-amber-600"
            >
              No servers.
              <RouterLink to="/settings" class="underline">Add one</RouterLink>.
            </div>
          </div>
          <div class="flex-1 min-w-40">
            <label class="mb-1 block text-xs font-medium text-gray-600"
              >Model</label
            >
            <div class="flex gap-1">
              <input
                v-if="models.length === 0"
                v-model="model"
                class="flex-1 rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
                placeholder="gpt-4o"
              />
              <select
                v-else
                v-model="model"
                class="flex-1 rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
              >
                <option value="" disabled>Select model…</option>
                <option v-for="m in models" :key="m.id" :value="m.id">
                  {{ m.id }}
                </option>
              </select>
              <button
                class="rounded-md border border-gray-300 p-1.5 text-gray-500 hover:bg-gray-50 disabled:opacity-40"
                :disabled="!selectedServerId || loadingModels"
                title="Fetch models from server"
                @click="fetchModels"
              >
                <Loader2 v-if="loadingModels" class="h-4 w-4 animate-spin" />
                <RefreshCw v-else class="h-4 w-4" />
              </button>
            </div>
            <div v-if="modelsError" class="mt-1 text-xs text-red-500">
              {{ modelsError }}
            </div>
          </div>
        </div>

        <!-- System prompt -->
        <div>
          <label class="mb-1 block text-xs font-medium text-gray-600"
            >System Prompt</label
          >
          <textarea
            v-model="systemPrompt"
            rows="3"
            class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400 resize-none"
            placeholder="You are a helpful assistant."
          />
        </div>

        <!-- Messages -->
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <label class="text-xs font-medium text-gray-600">Messages</label>
            <button
              class="flex items-center gap-1 rounded-md border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
              @click="addMessage"
            >
              <Plus class="h-3 w-3" /> Add message
            </button>
          </div>
          <div
            v-for="(msg, idx) in messages"
            :key="idx"
            class="rounded-lg border border-gray-200 bg-gray-50 p-3"
          >
            <div class="mb-2 flex items-center gap-2">
              <select
                v-model="msg.role"
                class="rounded border border-gray-300 bg-white px-2 py-1 text-xs focus:outline-none"
              >
                <option value="user">user</option>
                <option value="assistant">assistant</option>
              </select>
              <button
                v-if="messages.length > 1"
                class="ml-auto rounded p-1 text-gray-400 hover:text-red-500 hover:bg-red-50"
                @click="removeMessage(idx)"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </button>
            </div>
            <textarea
              v-model="msg.content"
              rows="3"
              class="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400 resize-y"
              :placeholder="
                msg.role === 'user'
                  ? 'Enter user message…'
                  : 'Enter assistant message…'
              "
            />
          </div>
        </div>

        <!-- Response -->
        <div v-if="response || sendError" class="mt-2">
          <div class="mb-1 flex items-center justify-between">
            <label class="text-xs font-medium text-gray-600">Response</label>
            <div class="flex items-center gap-3 text-xs text-gray-400">
              <span v-if="response">{{ response.duration_ms }}ms</span>
              <span v-if="response?.prompt_tokens">
                {{ response.prompt_tokens }}+{{ response.completion_tokens }}
                tokens
              </span>
              <button
                v-if="response"
                class="underline hover:text-gray-700"
                @click="viewInDashboard"
              >
                View in dashboard
              </button>
            </div>
          </div>
          <div
            v-if="sendError"
            class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {{ sendError }}
          </div>
          <div
            v-else-if="response"
            class="rounded-lg border border-gray-200 bg-white px-4 py-3 text-sm"
          >
            <div
              v-if="response.status >= 400"
              class="mb-2 text-xs font-medium text-red-600"
            >
              HTTP {{ response.status }}
            </div>
            <pre
              v-if="responseText"
              class="whitespace-pre-wrap break-words font-sans leading-relaxed"
              >{{ responseText }}</pre
            >
            <pre v-else class="whitespace-pre-wrap text-xs text-gray-600">{{
              JSON.stringify(response.body, null, 2)
            }}</pre>
          </div>
        </div>
      </div>

      <!-- Right: parameters + send -->
      <div class="w-52 shrink-0 flex flex-col gap-4 p-4 bg-gray-50">
        <div>
          <label class="mb-1 block text-xs font-medium text-gray-600">
            Temperature
            <span class="font-normal text-gray-400">({{ temperature }})</span>
          </label>
          <input
            v-model.number="temperature"
            type="range"
            min="0"
            max="2"
            step="0.05"
            class="w-full"
          />
          <div class="flex justify-between text-xs text-gray-400">
            <span>0</span><span>2</span>
          </div>
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-gray-600"
            >Max Tokens</label
          >
          <input
            v-model.number="maxTokens"
            type="number"
            min="1"
            class="w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
            placeholder="default"
          />
        </div>

        <div>
          <label class="mb-1 block text-xs font-medium text-gray-600"
            >Top P</label
          >
          <input
            v-model.number="topP"
            type="number"
            min="0"
            max="1"
            step="0.05"
            class="w-full rounded-md border border-gray-300 bg-white px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-gray-400"
            placeholder="default"
          />
        </div>

        <div class="mt-auto">
          <button
            :disabled="sending || !selectedServerId"
            class="flex w-full items-center justify-center gap-2 rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-40"
            @click="submit"
          >
            <Loader2 v-if="sending" class="h-4 w-4 animate-spin" />
            <Send v-else class="h-4 w-4" />
            {{ sending ? "Sending…" : "Send Request" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
