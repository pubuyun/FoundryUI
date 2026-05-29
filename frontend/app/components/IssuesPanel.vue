<script setup lang="ts">
defineProps<{
  errors: Array<Record<string, any>>;
  formatDetails: (error: Record<string, any>) => string;
}>();
</script>

<template>
  <ul v-if="errors.length" class="grid list-none gap-2 p-0">
    <li v-for="(error, index) in errors" :key="`${error.code ?? 'error'}-${index}`" class="grid gap-0.5 text-xs">
      <strong class="text-[#ffb86b]">{{ error.code ?? "ERROR" }}</strong>
      <span class="text-[11px] text-[#91a0b2]">{{ error.node_type || error.node_id ? `${error.node_type ?? "node"} ${error.node_id ?? ""}` : "" }}</span>
      <p class="m-0 text-xs">{{ error.message ?? "Unknown error" }}</p>
      <small v-if="formatDetails(error)" class="text-[11px] leading-snug text-[#ffd7a8]">{{ formatDetails(error) }}</small>
    </li>
  </ul>
  <p v-else class="m-0 text-xs">No issues</p>
</template>
