import { defineStore } from "pinia";
import { ref } from "vue";
import {
  listServers,
  createServer,
  updateServer,
  deleteServer,
  type Server,
  type ServerCreate,
  type ServerUpdate,
} from "@/lib/api";

export const useServersStore = defineStore("servers", () => {
  const servers = ref<Server[]>([]);
  const loading = ref(false);

  async function fetchServers() {
    loading.value = true;
    try {
      servers.value = await listServers();
    } finally {
      loading.value = false;
    }
  }

  async function addServer(data: ServerCreate): Promise<Server> {
    const server = await createServer(data);
    await fetchServers(); // reload to get consistent is_default state
    return server;
  }

  async function editServer(id: string, data: ServerUpdate): Promise<Server> {
    const server = await updateServer(id, data);
    await fetchServers();
    return server;
  }

  async function removeServer(id: string): Promise<void> {
    await deleteServer(id);
    servers.value = servers.value.filter((s) => s.id !== id);
  }

  return { servers, loading, fetchServers, addServer, editServer, removeServer };
});
