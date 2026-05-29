<script setup lang="ts">
interface BackendArtifact {
  artifact_id: string;
  payload_type: string;
  path: string;
  item_count: number;
}

defineProps<{
  artifacts: BackendArtifact[];
  artifactUrl: (artifact: any) => string;
}>();
</script>

<template>
  <ul v-if="artifacts.length" class="grid list-none gap-2 p-0">
    <li v-for="artifact in artifacts" :key="artifact.artifact_id" class="grid gap-0.5 text-xs">
      <a class="inline-flex items-center gap-1.5 text-[#7ee0c4] no-underline" :href="artifactUrl(artifact)">{{ artifact.path }}</a>
      <span class="text-[11px] text-[#91a0b2]">{{ artifact.payload_type }} · {{ artifact.item_count }}</span>
    </li>
  </ul>
  <p v-else class="m-0 text-xs">No saved results yet</p>
</template>
