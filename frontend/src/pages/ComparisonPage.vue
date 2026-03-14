<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getRequest, type ProxyRequestDetail } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

type DiffLineType = "same" | "removed" | "added";

interface DiffLine {
  type: DiffLineType;
  text: string;
  lineA: number | null;
  lineB: number | null;
}

// ── State ──────────────────────────────────────────────────────────────────

const route = useRoute();
const router = useRouter();

const reqA = ref<ProxyRequestDetail | null>(null);
const reqB = ref<ProxyRequestDetail | null>(null);
const error = ref("");
const loading = ref(true);

// ── Diff algorithm ─────────────────────────────────────────────────────────

/** Simple LCS-based line diff. Returns an array of DiffLine entries. */
function computeLineDiff(textA: string, textB: string): DiffLine[] {
  const linesA = textA.split("\n");
  const linesB = textB.split("\n");
  const m = linesA.length;
  const n = linesB.length;

  // Build LCS table
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    new Array<number>(n + 1).fill(0),
  );
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (linesA[i - 1] === linesB[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  // Traceback
  const result: DiffLine[] = [];
  let i = m;
  let j = n;
  let lineA = m;
  let lineB = n;

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && linesA[i - 1] === linesB[j - 1]) {
      result.unshift({
        type: "same",
        text: linesA[i - 1],
        lineA: lineA--,
        lineB: lineB--,
      });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({
        type: "added",
        text: linesB[j - 1],
        lineA: null,
        lineB: lineB--,
      });
      j--;
    } else {
      result.unshift({
        type: "removed",
        text: linesA[i - 1],
        lineA: lineA--,
        lineB: null,
      });
      i--;
    }
  }

  return result;
}

// ── Response text extraction ───────────────────────────────────────────────

function extractResponseText(req: ProxyRequestDetail): string {
  if (!req.response_body) return "(no response)";
  try {
    const body = JSON.parse(req.response_body) as Record<string, unknown>;
    // OpenAI Chat format
    const choices = body.choices;
    if (Array.isArray(choices) && choices.length > 0) {
      const first = choices[0] as Record<string, unknown>;
      const msg = first.message as Record<string, string> | undefined;
      if (msg?.content) return msg.content;
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
  } catch {
    return req.response_body;
  }
}

function extractRequestText(req: ProxyRequestDetail): string {
  if (!req.request_body) return "(no request body)";
  try {
    return JSON.stringify(JSON.parse(req.request_body), null, 2);
  } catch {
    return req.request_body;
  }
}

// ── Computed ───────────────────────────────────────────────────────────────

const responseDiff = computed<DiffLine[]>(() => {
  if (!reqA.value || !reqB.value) return [];
  return computeLineDiff(
    extractResponseText(reqA.value),
    extractResponseText(reqB.value),
  );
});

const requestDiff = computed<DiffLine[]>(() => {
  if (!reqA.value || !reqB.value) return [];
  return computeLineDiff(
    extractRequestText(reqA.value),
    extractRequestText(reqB.value),
  );
});

const hasResponseDiff = computed(() =>
  responseDiff.value.some((l) => l.type !== "same"),
);

const hasRequestDiff = computed(() =>
  requestDiff.value.some((l) => l.type !== "same"),
);

const linesA = computed(() =>
  responseDiff.value.filter((l) => l.type !== "added"),
);
const linesB = computed(() =>
  responseDiff.value.filter((l) => l.type !== "removed"),
);

const reqLinesA = computed(() =>
  requestDiff.value.filter((l) => l.type !== "added"),
);
const reqLinesB = computed(() =>
  requestDiff.value.filter((l) => l.type !== "removed"),
);

// ── Lifecycle ──────────────────────────────────────────────────────────────

onMounted(async () => {
  const a = route.query.a as string | undefined;
  const b = route.query.b as string | undefined;
  if (!a || !b) {
    error.value = "Missing query params: a and b (request IDs)";
    loading.value = false;
    return;
  }
  try {
    [reqA.value, reqB.value] = await Promise.all([
      getRequest(a),
      getRequest(b),
    ]);
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Failed to load requests";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden">
    <!-- Header -->
    <div class="flex items-center gap-3 border-b px-4 py-3 shrink-0">
      <button
        class="text-sm text-muted-foreground hover:text-foreground"
        @click="router.back()"
      >
        ← Back
      </button>
      <h2 class="text-base font-semibold">Response Comparison</h2>
      <span v-if="reqA && reqB" class="text-xs text-muted-foreground">
        {{ reqA.id.slice(0, 10) }}… vs {{ reqB.id.slice(0, 10) }}…
      </span>
    </div>

    <!-- Error / loading -->
    <div v-if="error" class="p-8 text-center text-sm text-red-600">
      {{ error }}
    </div>
    <div
      v-else-if="loading"
      class="p-8 text-center text-sm text-muted-foreground"
    >
      Loading…
    </div>

    <!-- Content -->
    <div v-else-if="reqA && reqB" class="flex flex-1 flex-col overflow-y-auto">
      <!-- Meta summary row -->
      <div
        class="grid grid-cols-2 gap-4 border-b px-4 py-2 text-xs text-muted-foreground bg-gray-50"
      >
        <div class="space-y-0.5">
          <div class="font-medium text-gray-700">Original</div>
          <div>{{ reqA.model ?? "–" }} · {{ reqA.duration_ms ?? "?" }}ms</div>
          <div v-if="reqA.prompt_tokens != null">
            ↑ {{ reqA.prompt_tokens }} / ↓
            {{ reqA.completion_tokens ?? "?" }} tokens
          </div>
        </div>
        <div class="space-y-0.5">
          <div class="font-medium text-gray-700">Modified</div>
          <div>{{ reqB.model ?? "–" }} · {{ reqB.duration_ms ?? "?" }}ms</div>
          <div v-if="reqB.prompt_tokens != null">
            ↑ {{ reqB.prompt_tokens }} / ↓
            {{ reqB.completion_tokens ?? "?" }} tokens
          </div>
        </div>
      </div>

      <!-- Request diff -->
      <div class="border-b">
        <div class="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b">
          <span class="text-xs font-semibold text-gray-700">Request Body</span>
          <span v-if="!hasRequestDiff" class="text-xs text-green-600"
            >identical</span
          >
          <span v-else class="text-xs text-amber-600">differs</span>
        </div>
        <div
          v-if="hasRequestDiff"
          class="grid grid-cols-2 divide-x overflow-x-auto"
        >
          <!-- Left (A) -->
          <pre
            class="p-3 text-xs leading-5 bg-white overflow-x-auto"
          ><template v-for="(line, idx) in reqLinesA" :key="idx"><span
              :class="{
                'bg-red-100 block -mx-3 px-3': line.type === 'removed',
              }"
            >{{ line.text }}</span
          ></template></pre>
          <!-- Right (B) -->
          <pre
            class="p-3 text-xs leading-5 bg-white overflow-x-auto"
          ><template v-for="(line, idx) in reqLinesB" :key="idx"><span
              :class="{
                'bg-green-100 block -mx-3 px-3': line.type === 'added',
              }"
            >{{ line.text }}</span
          ></template></pre>
        </div>
        <div v-else class="px-4 py-3 text-xs text-gray-400 italic">
          Requests are identical
        </div>
      </div>

      <!-- Response diff -->
      <div class="flex-1">
        <div class="flex items-center gap-2 px-4 py-2 bg-gray-50 border-b">
          <span class="text-xs font-semibold text-gray-700">Response</span>
          <span v-if="!hasResponseDiff" class="text-xs text-green-600"
            >identical</span
          >
          <span v-else class="text-xs text-amber-600">differs</span>
        </div>
        <div class="grid grid-cols-2 divide-x overflow-x-auto">
          <!-- Left (A) -->
          <pre
            class="p-3 text-xs leading-5 bg-white overflow-x-auto whitespace-pre-wrap break-words"
          ><template v-for="(line, idx) in linesA" :key="idx"><span
              :class="{
                'bg-red-100 block -mx-3 px-3': line.type === 'removed',
              }"
            >{{ line.text }}</span
          ></template></pre>
          <!-- Right (B) -->
          <pre
            class="p-3 text-xs leading-5 bg-white overflow-x-auto whitespace-pre-wrap break-words"
          ><template v-for="(line, idx) in linesB" :key="idx"><span
              :class="{
                'bg-green-100 block -mx-3 px-3': line.type === 'added',
              }"
            >{{ line.text }}</span
          ></template></pre>
        </div>
      </div>
    </div>
  </div>
</template>
