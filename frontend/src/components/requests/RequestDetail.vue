<script setup lang="ts">
import { computed } from "vue";
import { type ProxyRequestDetail, deriveStatus } from "@/lib/api";
import StatusBadge from "@/components/common/StatusBadge.vue";
import TimingDisplay from "@/components/common/TimingDisplay.vue";
import RequestHeaders from "./RequestHeaders.vue";
import RequestBody from "./RequestBody.vue";
import StreamingView from "./StreamingView.vue";

const props = defineProps<{ request: ProxyRequestDetail }>();

const status = computed(() => deriveStatus(props.request));
const isActivelyStreaming = computed(
  () =>
    props.request.is_streaming &&
    props.request.response_body === null &&
    !props.request.error,
);
</script>

<template>
  <div class="flex flex-col gap-6 p-4">
    <!-- Summary row -->
    <div class="flex flex-wrap items-center gap-3">
      <StatusBadge :status="status" />
      <span class="font-mono text-sm font-medium"
        >{{ request.method }} {{ request.path }}</span
      >
      <span
        v-if="request.model"
        class="rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground"
      >
        {{ request.model }}
      </span>
      <div
        class="ml-auto flex items-center gap-4 text-xs text-muted-foreground"
      >
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

    <div
      v-if="request.error"
      class="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700"
    >
      {{ request.error }}
    </div>

    <!-- Request section -->
    <section>
      <h3 class="mb-2 text-sm font-semibold">Request Headers</h3>
      <RequestHeaders :headers="request.request_headers" />
    </section>

    <section>
      <h3 class="mb-2 text-sm font-semibold">Request Body</h3>
      <RequestBody :body="request.request_body" />
    </section>

    <!-- Response section -->
    <section>
      <h3 class="mb-2 text-sm font-semibold">Response Headers</h3>
      <RequestHeaders :headers="request.response_headers" />
    </section>

    <section>
      <h3 class="mb-2 text-sm font-semibold">
        Response Body
        <span
          v-if="isActivelyStreaming"
          class="ml-2 text-xs font-normal text-blue-600 animate-pulse"
          >live</span
        >
      </h3>
      <StreamingView v-if="isActivelyStreaming" :request-id="request.id" />
      <RequestBody
        v-else
        :body="request.response_body"
        label="No response body yet"
      />
    </section>
  </div>
</template>
