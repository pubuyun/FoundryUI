<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  logs: string[];
}>();

const emit = defineEmits<{
  scroll: [event: Event];
}>();

const logText = computed(() => (props.logs.length ? props.logs.join("\n") : "No command output yet"));
</script>

<template>
  <pre class="h-full min-h-40 max-h-none overflow-auto overscroll-contain rounded-md border border-[#273342] bg-[#05080d] p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-[#8ef0bd] shadow-[inset_0_0_0_1px_rgba(126,224,196,0.05)]" @scroll="emit('scroll', $event)">{{ logText }}</pre>
</template>
