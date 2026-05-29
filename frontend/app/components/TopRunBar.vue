<script setup lang="ts">
interface RunStatusSummary {
  progress_percent: number;
  completed_nodes: number;
  total_nodes: number;
}

interface WorkflowPreset {
  label: string;
  file: string;
}

const props = defineProps<{
  currentRunId: string;
  currentSessionId: string;
  runState: string;
  runStateLabel: string;
  runStatus: RunStatusSummary | null;
  runMessage: string;
  archiveHref: string;
  apiBase: string;
  apiStatus: "idle" | "checking" | "available" | "unavailable";
  apiMessage: string;
  workflowPresets: WorkflowPreset[];
  selectedWorkflowPreset: string;
  isRunActive: boolean;
}>();

const emit = defineEmits<{
  "update:apiBase": [value: string];
  "update:selectedWorkflowPreset": [value: string];
  connect: [];
  createNewSession: [];
  saveWorkflow: [];
  requestLoadWorkflow: [];
  loadWorkflowPreset: [];
  clearWorkflow: [];
  stopRun: [];
  queueRun: [];
}>();

function onPresetChange(event: Event) {
  emit("update:selectedWorkflowPreset", (event.target as HTMLSelectElement).value);
  emit("loadWorkflowPreset");
}
</script>

<template>
  <header class="grid items-center gap-3.5 border-b border-[#ccd4dd] bg-[#fbfcfd] px-4 py-2.5 md:grid-cols-[auto_minmax(220px,1fr)_auto] max-md:items-start max-md:gap-2.5 max-md:px-3">
    <div class="min-w-24">
      <h1 class="m-0 text-lg font-bold tracking-normal">FoundryUI</h1>
    </div>
    <section class="grid min-w-0 grid-cols-[auto_minmax(80px,max-content)_auto_auto_minmax(120px,1fr)] items-center gap-2 text-xs text-[#344052] max-md:w-full max-md:grid-cols-[auto_minmax(80px,1fr)_auto_auto]" aria-label="Run status">
      <a
        v-if="currentRunId && (runState === 'completed' || runState === 'failed' || runState === 'stopped')"
        class="inline-flex items-center gap-1.5 rounded-md px-2 py-1 font-extrabold text-white no-underline"
        :class="runState === 'failed' ? 'bg-[#b33939]' : runState === 'stopped' ? 'bg-[#6d4b8d]' : 'bg-[#176f5d]'"
        :href="archiveHref"
        title="Download archive"
      >
        <span class="inline-grid size-[18px] place-items-center rounded border border-current text-xs leading-none" aria-hidden="true">⇩</span>
        {{ runState === "failed" ? "ERROR" : runState === "stopped" ? "STOPPED" : "ARCHIVED" }}
      </a>
      <span v-else class="rounded-md px-2 py-1 font-bold" :class="runState === 'failed' ? 'bg-[#4a1d22] text-[#ff9c9c]' : runState === 'stopped' ? 'bg-[#3b3340] text-[#d8b6ff]' : 'bg-[#12372f] text-[#7ee0c4]'">{{ runStateLabel }}</span>
      <span v-if="currentRunId" class="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap font-bold text-[#566271]">{{ currentRunId }}</span>
      <span v-if="runStatus" class="font-bold text-[#566271]">{{ runStatus.progress_percent }}%</span>
      <span v-if="runStatus" class="font-bold text-[#566271]">{{ runStatus.completed_nodes }}/{{ runStatus.total_nodes }}</span>
      <span class="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap text-[#17202a] max-md:col-span-full">{{ runMessage }}</span>
      <div class="col-span-full h-[5px] w-full overflow-hidden rounded bg-[#dbe3ec]">
        <div class="h-full min-w-0 bg-[#2ca58d] transition-[width] duration-200" :style="{ width: `${runStatus?.progress_percent ?? 0}%` }" />
      </div>
    </section>
    <nav class="flex flex-wrap items-center justify-end gap-2 max-md:w-full" aria-label="Workflow actions">
      <label class="flex items-center gap-1.5 text-xs font-bold text-[#566271] max-md:flex-[1_1_220px]">
        API
        <input class="h-8 w-[190px] rounded-md border border-[#c6d0dc] bg-white px-2 text-[#17202a] max-md:w-full" :value="apiBase" placeholder="http://127.0.0.1:3000/api" spellcheck="false" @input="emit('update:apiBase', ($event.target as HTMLInputElement).value)" @keyup.enter="emit('connect')" />
      </label>
      <button type="button" class="h-8 cursor-pointer rounded-md border border-[#c6d0dc] bg-white px-3 font-bold text-[#17202a] disabled:cursor-progress disabled:opacity-65" :disabled="apiStatus === 'checking'" @click="emit('connect')">
        {{ apiStatus === "checking" ? "Checking" : "Connect" }}
      </button>
      <span class="max-w-[180px] overflow-hidden text-ellipsis whitespace-nowrap text-xs font-bold" :class="apiStatus === 'available' ? 'text-[#176f5d]' : apiStatus === 'unavailable' ? 'text-[#b33939]' : 'text-[#667386]'">{{ apiMessage }}</span>
      <span v-if="currentSessionId" class="max-w-[150px] overflow-hidden text-ellipsis whitespace-nowrap text-xs font-bold text-[#566271]">{{ currentSessionId.slice(0, 18) }}</span>
      <NuxtLink class="inline-flex h-8 cursor-pointer items-center rounded-md border border-[#c6d0dc] bg-white px-3 font-bold text-[#17202a] no-underline" to="/sessions">Sessions</NuxtLink>
      <button type="button" class="size-8 cursor-pointer rounded-md border border-[#c6d0dc] bg-white font-bold text-[#17202a]" title="New session" @click="emit('createNewSession')">N</button>
      <button type="button" class="size-8 cursor-pointer rounded-md border border-[#c6d0dc] bg-white font-bold text-[#17202a]" title="Save workflow" @click="emit('saveWorkflow')">S</button>
      <div class="inline-flex h-8 items-center">
        <button type="button" class="size-8 cursor-pointer rounded-l-md border border-[#c6d0dc] bg-white font-bold text-[#17202a]" title="Load workflow file" @click="emit('requestLoadWorkflow')">L</button>
        <select class="h-8 w-[92px] rounded-r-md border border-l-0 border-[#c6d0dc] bg-white text-xs font-bold text-[#17202a]" :value="selectedWorkflowPreset" title="Load workflow preset" @change="onPresetChange">
          <option value="">Presets</option>
          <option v-for="preset in workflowPresets" :key="preset.file" :value="preset.file">{{ preset.label }}</option>
        </select>
      </div>
      <button type="button" class="size-8 cursor-pointer rounded-md border border-[#c6d0dc] bg-white font-bold text-[#17202a]" title="Clear canvas" @click="emit('clearWorkflow')">C</button>
      <button v-if="isRunActive" type="button" class="h-8 cursor-pointer rounded-md border border-[#a8343d] bg-[#a8343d] px-3.5 font-bold text-white" @click="emit('stopRun')">Stop</button>
      <button type="button" class="h-8 cursor-pointer rounded-md border border-[#176f5d] bg-[#176f5d] px-4 font-bold text-white disabled:cursor-wait disabled:opacity-60" :disabled="isRunActive" @click="emit('queueRun')">Run</button>
    </nav>
  </header>
</template>
