<script setup lang="ts">
import { onMounted, ref } from "vue";

interface SessionRecord {
  session_id: string;
  created_at: string;
  updated_at: string;
  latest_run_id?: string | null;
}

const apiBase = ref("http://127.0.0.1:8000");
const sessions = ref<SessionRecord[]>([]);
const message = ref("Loading sessions");

async function loadSessions() {
  const response = await fetch(`${apiBase.value}/api/sessions`);
  if (!response.ok) {
    message.value = "Could not load sessions";
    return;
  }
  const payload = (await response.json()) as { sessions: SessionRecord[] };
  sessions.value = payload.sessions ?? [];
  message.value = sessions.value.length ? "" : "No sessions yet";
}

async function createSession() {
  const response = await fetch(`${apiBase.value}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!response.ok) {
    message.value = "Could not create session";
    return;
  }
  const session = (await response.json()) as SessionRecord;
  await navigateTo({ path: "/", query: { session: session.session_id } });
}

async function deleteSession(sessionId: string) {
  const response = await fetch(`${apiBase.value}/api/sessions/${sessionId}`, { method: "DELETE" });
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

onMounted(loadSessions);
</script>

<template>
  <main class="sessions-page">
    <header class="sessions-header">
      <div>
        <h1>Sessions</h1>
        <p>Open an existing session or create a clean workspace.</p>
      </div>
      <nav class="sessions-actions">
        <label>
          API
          <input v-model="apiBase" spellcheck="false" />
        </label>
        <NuxtLink class="secondary-button" to="/">Workbench</NuxtLink>
        <button type="button" class="primary-button" @click="createSession">New Session</button>
      </nav>
    </header>

    <section class="sessions-list" aria-label="Existing sessions">
      <p v-if="message">{{ message }}</p>
      <article v-for="session in sessions" :key="session.session_id" class="session-row">
        <div>
          <h2>{{ session.session_id }}</h2>
          <p>Updated {{ new Date(session.updated_at).toLocaleString() }}</p>
          <p v-if="session.latest_run_id">Latest run {{ session.latest_run_id }}</p>
        </div>
        <div class="session-row-actions">
          <NuxtLink class="secondary-button" :to="sessionUrl(session.session_id)">Open</NuxtLink>
          <button type="button" class="danger-button" @click="deleteSession(session.session_id)">Delete</button>
        </div>
      </article>
    </section>
  </main>
</template>

<style>
.sessions-page {
  min-height: 100vh;
  background: #f5f7fa;
  color: #17202a;
}

.sessions-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid #ccd4dd;
  background: #ffffff;
  padding: 18px 22px;
}

.sessions-header h1,
.sessions-header p,
.session-row h2,
.session-row p,
.sessions-list p {
  margin: 0;
}

.sessions-header h1 {
  font-size: 22px;
  letter-spacing: 0;
}

.sessions-header p,
.session-row p {
  color: #5b6878;
  font-size: 13px;
}

.sessions-actions,
.session-row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sessions-actions label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #566271;
  font-size: 12px;
  font-weight: 700;
}

.sessions-actions input {
  width: 210px;
  height: 34px;
  border: 1px solid #c6d0dc;
  border-radius: 6px;
  padding: 0 8px;
}

.sessions-list {
  display: grid;
  gap: 10px;
  max-width: 980px;
  padding: 18px 22px;
}

.session-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border: 1px solid #d4dde8;
  border-radius: 8px;
  background: #ffffff;
  padding: 14px;
}

.session-row h2 {
  font-size: 14px;
  letter-spacing: 0;
}

.primary-button,
.secondary-button,
.danger-button {
  display: inline-flex;
  height: 34px;
  align-items: center;
  border-radius: 6px;
  padding: 0 12px;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}

.primary-button {
  border: 1px solid #176f5d;
  background: #176f5d;
  color: #ffffff;
}

.secondary-button {
  border: 1px solid #c6d0dc;
  background: #ffffff;
  color: #17202a;
}

.danger-button {
  border: 1px solid #a8343d;
  background: #a8343d;
  color: #ffffff;
}

@media (max-width: 760px) {
  .sessions-header,
  .session-row {
    align-items: stretch;
    flex-direction: column;
  }

  .sessions-actions,
  .session-row-actions {
    flex-wrap: wrap;
  }
}
</style>
