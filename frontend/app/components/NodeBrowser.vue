<script setup lang="ts">
import { computed } from "vue";
import type { FoundryNodeSpec } from "../utils/foundrySpecs";

const props = defineProps<{
  nodeSpecs: FoundryNodeSpec[];
  colorForSpec: (spec: FoundryNodeSpec) => string;
}>();

const emit = defineEmits<{
  addNode: [type: string];
}>();

const groupedSpecs = computed(() => {
  const groups = new Map<string, FoundryNodeSpec[]>();
  props.nodeSpecs
    .filter((spec) => !spec.hidden)
    .forEach((spec) => {
      const category = spec.category || "Other";
      groups.set(category, [...(groups.get(category) ?? []), spec]);
    });
  return [...groups.entries()]
    .map(([category, specs]) => ({
      category,
      specs: specs.slice().sort((left, right) => left.title.localeCompare(right.title)),
    }))
    .sort((left, right) => left.category.localeCompare(right.category));
});
</script>

<template>
  <div class="grid content-start gap-2.5 overflow-auto">
    <details v-for="group in groupedSpecs" :key="group.category" class="group rounded-lg border border-[#2f3b4d] bg-[#111923]" open>
      <summary class="flex cursor-pointer list-none items-center justify-between gap-2 p-2.5 text-xs font-extrabold tracking-normal text-[#d8e1ec] marker:hidden [&::-webkit-details-marker]:hidden">
        <span class="text-[11px] text-[#7ee0c4] transition-transform group-open:rotate-90" aria-hidden="true">▸</span>
        <span class="flex-1">{{ group.category }}</span>
        <small class="text-[11px] text-[#91a0b2]">{{ group.specs.length }}</small>
      </summary>
      <div class="grid gap-2 px-2 pb-2">
        <button
          v-for="spec in group.specs"
          :key="spec.type"
          type="button"
          class="grid min-h-12 w-full cursor-pointer gap-0.5 rounded-md border border-[#334154] bg-[#1a2533] px-2.5 py-2 text-left text-[#e8f0f8] hover:border-[#7ee0c4]"
          :style="{ borderLeft: `4px solid ${colorForSpec(spec)}` }"
          @click="emit('addNode', spec.type)"
        >
          <strong class="text-xs">{{ spec.title }}</strong>
          <span class="text-[11px] text-[#91a0b2]">{{ spec.type }}</span>
        </button>
      </div>
    </details>
  </div>
</template>
