import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "dashboard",
      component: () => import("@/pages/DashboardPage.vue"),
    },
    {
      path: "/requests/:id",
      name: "request-detail",
      component: () => import("@/pages/RequestDetailPage.vue"),
    },
    {
      path: "/editor",
      name: "editor",
      component: () => import("@/pages/EditorPage.vue"),
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("@/pages/SettingsPage.vue"),
    },
    {
      path: "/compare",
      name: "compare",
      component: () => import("@/pages/ComparisonPage.vue"),
    },
  ],
});

export default router;
