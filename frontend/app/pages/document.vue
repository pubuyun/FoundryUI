<script setup lang="ts">
import { computed, ref } from "vue";
import { colorsByType, nodeSpecs, typeDetails } from "../utils/foundrySpecs";

const activeTab = ref<"nodes" | "types" | "rules">("nodes");

const nodeGroups = computed(() => {
  const groups = new Map<string, typeof nodeSpecs>();
  nodeSpecs.forEach((node) => {
    if (!groups.has(node.category)) {
      groups.set(node.category, []);
    }
    groups.get(node.category)?.push(node);
  });
  return [...groups.entries()].map(([category, nodes]) => ({ category, nodes }));
});
</script>

<template>
  <main class="document-shell">
    <header class="document-topbar">
      <div>
        <h1>FoundryUI Document</h1>
        <p>Node inventory, typed ports, and workflow rules.</p>
      </div>
      <NuxtLink to="/" class="back-link">Workbench</NuxtLink>
    </header>

    <nav class="document-tabs" aria-label="Document sections">
      <button :class="{ active: activeTab === 'nodes' }" type="button" @click="activeTab = 'nodes'">Nodes</button>
      <button :class="{ active: activeTab === 'types' }" type="button" @click="activeTab = 'types'">Types</button>
      <button :class="{ active: activeTab === 'rules' }" type="button" @click="activeTab = 'rules'">Rules</button>
    </nav>

    <section v-if="activeTab === 'nodes'" class="document-content">
      <article v-for="group in nodeGroups" :key="group.category" class="doc-section">
        <h2>{{ group.category }}</h2>
        <div class="node-grid">
          <section v-for="node in group.nodes" :key="node.type" class="node-card">
            <p class="eyebrow">{{ node.type }}</p>
            <h3>{{ node.title }}</h3>
            <p>{{ node.description }}</p>
            <div class="io-grid">
              <div>
                <h4>Inputs</h4>
                <span v-if="!node.inputs?.length" class="empty">None</span>
                <span v-for="input in node.inputs" :key="input.key" class="chip">
                  <i :style="{ background: colorsByType[input.type] }" />
                  {{ input.label }}{{ input.optional ? "*" : "" }}
                </span>
              </div>
              <div>
                <h4>Options</h4>
                <span v-if="!node.options?.length" class="empty">None</span>
                <span v-for="option in node.options" :key="option.key" class="option-chip">
                  {{ option.label }}
                  <small v-if="option.value !== ''">default {{ option.value }}</small>
                </span>
              </div>
              <div>
                <h4>Outputs</h4>
                <span v-if="!node.outputs?.length" class="empty">None</span>
                <span v-for="output in node.outputs" :key="output.key" class="chip">
                  <i :style="{ background: colorsByType[output.type] }" />
                  {{ output.label }}
                </span>
              </div>
            </div>
          </section>
        </div>
      </article>
    </section>

    <section v-else-if="activeTab === 'types'" class="document-content type-list">
      <article v-for="type in typeDetails" :key="type.name" class="type-row">
        <span class="type-dot" :style="{ background: colorsByType[type.name] }" />
        <div>
          <strong>{{ type.name }}</strong>
          <p>{{ type.detail }}</p>
        </div>
      </article>
    </section>

    <section v-else class="document-content rules">
      <article class="node-card">
        <h2>Workflow Rules</h2>
        <p>Batch Protein or Batch Ligand connected to a single Protein or Ligand port uses the first item.</p>
        <p>Nodes that change model or score counts/order accept models and scores together and output the filtered models and scores together.</p>
        <p>If Score is not connected, Score is not emitted by optional-score operations.</p>
        <p>Options with defaults in the node specification are represented as non-port node options, not optional graph inputs.</p>
        <p>Node-local 3D selector buttons open separate viewer instances and use the structure uploaded or connected for that node.</p>
      </article>
    </section>
  </main>
</template>

<style>
.document-shell {
  min-height: 100vh;
  background: #eef2f6;
}

.document-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 22px;
  border-bottom: 1px solid #ccd4dd;
  background: #fbfcfd;
}

.document-topbar h1,
.document-topbar p,
.doc-section h2,
.node-card h3,
.node-card h4,
.node-card p {
  margin: 0;
}

.document-topbar h1 {
  font-size: 20px;
  letter-spacing: 0;
}

.document-topbar p,
.node-card p,
.type-row p,
.rules p {
  color: #647181;
  line-height: 1.4;
}

.back-link,
.document-tabs button {
  border: 1px solid #c6d0dc;
  background: #ffffff;
  color: #17202a;
  cursor: pointer;
  text-decoration: none;
}

.back-link {
  display: inline-flex;
  align-items: center;
  height: 34px;
  padding: 0 12px;
  border-radius: 6px;
  font-weight: 700;
}

.document-tabs {
  display: flex;
  gap: 8px;
  padding: 12px 22px;
  border-bottom: 1px solid #d8dee7;
  background: #f8fafc;
}

.document-tabs button {
  height: 34px;
  padding: 0 14px;
  border-radius: 6px;
  color: #495465;
}

.document-tabs button.active {
  background: #17202a;
  border-color: #17202a;
  color: #ffffff;
}

.document-content {
  padding: 22px;
}

.doc-section + .doc-section {
  margin-top: 26px;
}

.doc-section h2 {
  margin-bottom: 12px;
  color: #4d5968;
  font-size: 14px;
  text-transform: uppercase;
}

.node-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 12px;
}

.node-card,
.type-row {
  border: 1px solid #d5dde6;
  border-radius: 8px;
  background: #ffffff;
}

.node-card {
  padding: 14px;
}

.eyebrow {
  color: #176f5d;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.node-card h3 {
  margin-top: 4px;
  font-size: 18px;
}

.io-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.node-card h4 {
  margin-bottom: 8px;
  color: #596575;
  font-size: 12px;
  text-transform: uppercase;
}

.chip,
.option-chip,
.empty {
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 28px;
  margin: 5px 0;
  padding: 5px 8px;
  border-radius: 6px;
  background: #f3f6f9;
  color: #26313f;
  font-size: 12px;
}

.chip i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex: 0 0 auto;
}

.option-chip {
  align-items: start;
  flex-direction: column;
  background: #fff6e8;
}

.option-chip small {
  color: #78624a;
}

.empty {
  color: #7a8593;
}

.type-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.type-row {
  display: grid;
  grid-template-columns: 14px 1fr;
  gap: 10px;
  padding: 12px;
}

.type-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 4px;
}

.type-row p {
  margin: 3px 0 0;
  font-size: 12px;
}

.rules {
  max-width: 820px;
}

.rules p + p {
  margin-top: 10px;
}

@media (max-width: 760px) {
  .document-topbar {
    align-items: start;
    flex-direction: column;
  }

  .io-grid {
    grid-template-columns: 1fr;
  }
}
</style>
