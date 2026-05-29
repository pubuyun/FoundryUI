<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

interface SessionRecord {
  session_id: string;
  created_at: string;
  updated_at: string;
  latest_run_id?: string | null;
}

const DEFAULT_API_BASE = "http://127.0.0.1:3000/api";
const apiBase = ref(DEFAULT_API_BASE);
const apiStatus = ref<"idle" | "checking" | "available" | "unavailable">("idle");
const sessions = ref<SessionRecord[]>([]);
const message = ref("Enter API URL and click Connect");
const normalizedApiBase = computed(() => normalizeApiBase(apiBase.value));

function normalizeApiBase(value: string) {
  return value.trim().replace(/\/+$/, "");
}

function apiUrl(path: string) {
  const base = normalizedApiBase.value;
  if (!base) {
    throw new Error("Enter an API URL and click Connect.");
  }
  let requestPath = path.startsWith("/") ? path : `/${path}`;
  if (base.endsWith("/api") && requestPath.startsWith("/api/")) {
    requestPath = requestPath.slice(4);
  }
  return `${base}${requestPath}`;
}

function restoreApiBase() {
  apiBase.value = localStorage.getItem("foundryui-api-base") ?? DEFAULT_API_BASE;
  message.value = apiBase.value === DEFAULT_API_BASE ? "Using default local API" : "API URL loaded";
}

async function connectApi() {
  apiStatus.value = "checking";
  message.value = "Checking API";
  try {
    const response = await fetch(apiUrl("/health"), { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Health check failed (${response.status})`);
    }
    localStorage.setItem("foundryui-api-base", normalizedApiBase.value);
    apiBase.value = normalizedApiBase.value;
    apiStatus.value = "available";
    await loadSessions();
  } catch (error) {
    apiStatus.value = "unavailable";
    message.value = error instanceof Error ? error.message : "API unavailable";
  }
}

async function loadSessions() {
  let response: Response;
  try {
    response = await fetch(apiUrl("/api/sessions"));
  } catch (error) {
    message.value = error instanceof Error ? error.message : "Could not load sessions";
    return;
  }
  if (!response.ok) {
    message.value = "Could not load sessions";
    return;
  }
  const payload = (await response.json()) as { sessions: SessionRecord[] };
  sessions.value = payload.sessions ?? [];
  message.value = sessions.value.length ? "" : "No sessions yet";
}

async function createSession() {
  let response: Response;
  try {
    response = await fetch(apiUrl("/api/sessions"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
  } catch (error) {
    message.value = error instanceof Error ? error.message : "Could not create session";
    return;
  }
  if (!response.ok) {
    message.value = "Could not create session";
    return;
  }
  const session = (await response.json()) as SessionRecord;
  await navigateTo({ path: "/", query: { session: session.session_id } });
}

async function deleteSession(sessionId: string) {
  let response: Response;
  try {
    response = await fetch(apiUrl(`/api/sessions/${sessionId}`), { method: "DELETE" });
  } catch (error) {
    message.value = error instanceof Error ? error.message : "Could not delete session";
    return;
  }
  if (!response.ok) {
    message.value = "Could not delete session";
    return;
  }
  sessions.value = sessions.value.filter((session) => session.session_id !== sessionId);
  message.value = sessions.value.length ? "" : "No sessions yet";
}

function sessionUrl(sessionId: string) {
  return `/?session=${encodeURIComponent(sessionId)}`;
}

onMounted(() => {
  restoreApiBase();
  if (normalizedApiBase.value) {
    void connectApi();
  }
});
</script>

<template>
  <main class="min-h-screen bg-[#f5f7fa] text-[#17202a]">
    <header class="flex items-center justify-between gap-5 border-b border-[#ccd4dd] bg-white px-5 py-4 max-md:flex-col max-md:items-stretch">
      <div>
        <h1 class="m-0 text-[22px] font-bold tracking-normal">Sessions</h1>
        <p class="m-0 text-[13px] text-[#5b6878]">Open an existing session or create a clean workspace.</p>
      </div>
      <nav class="flex items-center gap-2 max-md:flex-wrap">
        <label class="flex items-center gap-1.5 text-xs font-bold text-[#566271]">
          API
          <input v-model="apiBase" class="h-[34px] w-[210px] rounded-md border border-[#c6d0dc] px-2" placeholder="http://127.0.0.1:3000/api" spellcheck="false" @keyup.enter="connectApi" />
        </label>
        <button type="button" class="inline-flex h-[34px] cursor-pointer items-center rounded-md border border-[#c6d0dc] bg-white px-3 font-bold text-[#17202a] no-underline" :disabled="apiStatus === 'checking'" @click="connectApi">
          {{ apiStatus === "checking" ? "Checking" : "Connect" }}
        </button>
        <NuxtLink class="inline-flex h-[34px] cursor-pointer items-center rounded-md border border-[#c6d0dc] bg-white px-3 font-bold text-[#17202a] no-underline" to="/">Workbench</NuxtLink>
        <button type="button" class="inline-flex h-[34px] cursor-pointer items-center rounded-md border border-[#176f5d] bg-[#176f5d] px-3 font-bold text-white no-underline" @click="createSession">New Session</button>
      </nav>
    </header>

    <section class="grid max-w-[980px] gap-2.5 px-5 py-4" aria-label="Existing sessions">
      <p v-if="message" class="m-0">{{ message }}</p>
      <article v-for="session in sessions" :key="session.session_id" class="flex items-center justify-between gap-4 rounded-lg border border-[#d4dde8] bg-white p-3.5 max-md:flex-col max-md:items-stretch">
        <div>
          <h2 class="m-0 text-sm font-bold tracking-normal">{{ session.session_id }}</h2>
          <p class="m-0 text-[13px] text-[#5b6878]">Updated {{ new Date(session.updated_at).toLocaleString() }}</p>
          <p v-if="session.latest_run_id" class="m-0 text-[13px] text-[#5b6878]">Latest run {{ session.latest_run_id }}</p>
        </div>
        <div class="flex items-center gap-2 max-md:flex-wrap">
          <NuxtLink class="inline-flex h-[34px] cursor-pointer items-center rounded-md border border-[#c6d0dc] bg-white px-3 font-bold text-[#17202a] no-underline" :to="sessionUrl(session.session_id)">Open</NuxtLink>
          <button type="button" class="inline-flex h-[34px] cursor-pointer items-center rounded-md border border-[#a8343d] bg-[#a8343d] px-3 font-bold text-white no-underline" @click="deleteSession(session.session_id)">Delete</button>
        </div>
      </article>
    </section>
  </main>
</template>
