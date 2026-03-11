<script setup lang="ts">
import { LayoutDashboard, PenTool } from "lucide-vue-next";
import { RouterLink, useRoute } from "vue-router";

const route = useRoute();

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/editor", label: "Editor", icon: PenTool },
];
</script>

<template>
  <aside class="flex w-56 shrink-0 flex-col border-r border-gray-200 bg-white">
    <nav class="flex flex-1 flex-col gap-1 p-3">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors"
        :class="
          route.path === item.to
            ? 'bg-gray-100 text-gray-900'
            : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
        "
      >
        <component :is="item.icon" class="h-4 w-4" />
        {{ item.label }}
      </RouterLink>
    </nav>
  </aside>
</template>
