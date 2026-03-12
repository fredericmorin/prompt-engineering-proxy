<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Plus, Pencil, Trash2, Star, StarOff, Copy } from "lucide-vue-next";
import { useServersStore } from "@/stores/servers";
import type { ServerCreate, ServerUpdate } from "@/lib/api";

/** Mirror of the Python name_to_slug() function. */
function nameToSlug(name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "server";
}

function proxyPrefix(name: string): string {
  return `${window.location.origin}/${nameToSlug(name)}/v1`;
}

async function copyToClipboard(text: string) {
  await navigator.clipboard.writeText(text).catch(() => {});
}

const store = useServersStore();

const PROTOCOLS = [
  { value: "openai_chat", label: "OpenAI Chat Completions" },
  { value: "openai_responses", label: "OpenAI Responses" },
  { value: "anthropic", label: "Anthropic Messages" },
];

// Form state
const showForm = ref(false);
const editingId = ref<string | null>(null);
const saving = ref(false);
const errorMsg = ref("");

const form = ref<ServerCreate>({
  name: "",
  base_url: "",
  protocol: "openai_chat",
  api_key: "",
  is_default: false,
});

function openCreate() {
  editingId.value = null;
  form.value = { name: "", base_url: "", protocol: "openai_chat", api_key: "", is_default: false };
  errorMsg.value = "";
  showForm.value = true;
}

function openEdit(server: (typeof store.servers)[0]) {
  editingId.value = server.id;
  form.value = {
    name: server.name,
    base_url: server.base_url,
    protocol: server.protocol,
    api_key: "",
    is_default: server.is_default,
  };
  errorMsg.value = "";
  showForm.value = true;
}

async function saveForm() {
  saving.value = true;
  errorMsg.value = "";
  try {
    if (editingId.value) {
      const update: ServerUpdate = {
        name: form.value.name,
        base_url: form.value.base_url,
        protocol: form.value.protocol,
        is_default: form.value.is_default,
      };
      if (form.value.api_key) update.api_key = form.value.api_key;
      await store.editServer(editingId.value, update);
    } else {
      const create: ServerCreate = { ...form.value };
      if (!create.api_key) delete create.api_key;
      await store.addServer(create);
    }
    showForm.value = false;
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : "Failed to save";
  } finally {
    saving.value = false;
  }
}

async function removeServer(id: string, name: string) {
  if (!confirm(`Delete server "${name}"?`)) return;
  try {
    await store.removeServer(id);
  } catch (e) {
    alert(e instanceof Error ? e.message : "Failed to delete");
  }
}

async function setDefault(id: string) {
  try {
    await store.editServer(id, { is_default: true });
  } catch (e) {
    alert(e instanceof Error ? e.message : "Failed to update");
  }
}

onMounted(() => store.fetchServers());
</script>

<template>
  <div class="h-full overflow-y-auto p-6">
    <div class="mx-auto max-w-2xl">
      <div class="mb-6 flex items-center justify-between">
        <h2 class="text-xl font-semibold">Upstream Servers</h2>
        <button
          class="flex items-center gap-2 rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-700"
          @click="openCreate"
        >
          <Plus class="h-4 w-4" />
          Add Server
        </button>
      </div>

      <!-- Server list -->
      <div v-if="store.loading" class="py-12 text-center text-sm text-gray-500">Loading…</div>
      <div
        v-else-if="store.servers.length === 0"
        class="rounded-lg border border-dashed border-gray-300 py-12 text-center text-sm text-gray-500"
      >
        No servers configured. Add one to start proxying requests.
      </div>
      <ul v-else class="space-y-2">
        <li
          v-for="server in store.servers"
          :key="server.id"
          class="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-4"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium text-sm truncate">{{ server.name }}</span>
              <span
                v-if="server.is_default"
                class="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"
              >
                default
              </span>
            </div>
            <div class="mt-0.5 text-xs text-gray-500 truncate">{{ server.base_url }}</div>
            <div class="mt-0.5 text-xs text-gray-400">{{ server.protocol }}</div>
            <div class="mt-1.5 flex items-center gap-1">
              <code class="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-600 truncate max-w-xs">
                {{ proxyPrefix(server.name) }}
              </code>
              <button
                class="rounded p-0.5 text-gray-400 hover:text-gray-600"
                title="Copy proxy base URL"
                @click="copyToClipboard(proxyPrefix(server.name))"
              >
                <Copy class="h-3 w-3" />
              </button>
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <button
              v-if="!server.is_default"
              class="rounded p-1.5 text-gray-400 hover:text-amber-500 hover:bg-amber-50"
              title="Set as default"
              @click="setDefault(server.id)"
            >
              <StarOff class="h-4 w-4" />
            </button>
            <button
              v-else
              class="rounded p-1.5 text-amber-500 hover:bg-amber-50"
              title="Default server"
            >
              <Star class="h-4 w-4" />
            </button>
            <button
              class="rounded p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100"
              title="Edit"
              @click="openEdit(server)"
            >
              <Pencil class="h-4 w-4" />
            </button>
            <button
              class="rounded p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50"
              title="Delete"
              @click="removeServer(server.id, server.name)"
            >
              <Trash2 class="h-4 w-4" />
            </button>
          </div>
        </li>
      </ul>
    </div>

    <!-- Modal form -->
    <div
      v-if="showForm"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      @click.self="showForm = false"
    >
      <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-lg">
        <h3 class="mb-4 text-base font-semibold">
          {{ editingId ? "Edit Server" : "Add Server" }}
        </h3>
        <form class="space-y-4" @submit.prevent="saveForm">
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">Name</label>
            <input
              v-model="form.name"
              required
              class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
              placeholder="OpenAI Production"
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">Base URL</label>
            <input
              v-model="form.base_url"
              required
              class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
              placeholder="https://api.openai.com"
            />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">Protocol</label>
            <select
              v-model="form.protocol"
              class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
            >
              <option v-for="p in PROTOCOLS" :key="p.value" :value="p.value">
                {{ p.label }}
              </option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700">
              API Key
              <span v-if="editingId" class="font-normal text-gray-400">(leave blank to keep current)</span>
            </label>
            <input
              v-model="form.api_key"
              type="password"
              autocomplete="off"
              class="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-400"
              placeholder="sk-..."
            />
          </div>
          <div class="flex items-center gap-2">
            <input id="is_default" v-model="form.is_default" type="checkbox" class="rounded" />
            <label for="is_default" class="text-sm text-gray-700">Set as default server</label>
          </div>
          <div v-if="errorMsg" class="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">
            {{ errorMsg }}
          </div>
          <div class="flex justify-end gap-2">
            <button
              type="button"
              class="rounded-md border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
              @click="showForm = false"
            >
              Cancel
            </button>
            <button
              type="submit"
              :disabled="saving"
              class="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50"
            >
              {{ saving ? "Saving…" : editingId ? "Save Changes" : "Add Server" }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
