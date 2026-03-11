<script setup lang="ts">
import { useRoute } from "vue-router";

const route = useRoute();
</script>

<template>
  <div>
    <h2 class="mb-4 text-2xl font-bold">Request Detail</h2>
    <p class="text-gray-500">Request ID: {{ route.params.id }}</p>
  </div>
</template>
