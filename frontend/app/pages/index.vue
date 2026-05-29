<script setup lang="ts">
import { computed, defineComponent, h, markRaw, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import type { AbstractNode, Connection, NodeInterface as NodeInterfaceTypeBase } from "@baklavajs/core";
import {
  BaklavaEditor,
  CheckboxInterface,
  Components,
  IntegerInterface,
  NodeInterface,
  NumberInterface,
  SelectInterface,
  TextareaInputInterface,
  TextInputInterface,
  defineNode,
  useBaklava,
} from "baklavajs";
import { BaklavaInterfaceTypes, NodeInterfaceType, getType, setType } from "@baklavajs/interface-types";
import "@baklavajs/themes/dist/syrup-dark.css";
import "../assets/css/baklava-generated.css";
import {
  type NodeCatalogResponse,
  proteinExample,
  type FoundryNodeSpec,
  type OptionSpec,
  type PortSpec,
  type PortType,
} from "../utils/foundrySpecs";
import { formatErrorDetails, normalizeApiBase, readBackendMessage } from "../utils/backendMessages";
import {
  atomId,
  atomNamesFromContent,
  detectStructureType,
  formatChiralityTargets,
  formatProteinAtomMap,
  parseChiralityTargets,
  parseProteinAtomMap,
  parseSelectorList,
  residueId,
  residueSelection,
} from "../utils/structureSelection";
import type {
  BackendArtifact,
  BackendOutput,
  PendingRunInput,
  RunEventPayload,
  RunStatus,
  SessionRecord,
  SidebarPanel,
  UploadedStructure,
  ViewerModal,
  WorkflowPreset,
} from "../utils/workbenchTypes";

const baklava = useBaklava();
baklava.settings.enableMinimap = true;
baklava.settings.displayValueOnHover = true;
baklava.settings.nodes.defaultWidth = 278;
baklava.settings.palette.enabled = false;

const registeredConstructors = new Map<string, ReturnType<typeof defineNode>>();
const typeRegistry = new Map<PortType, NodeInterfaceType<any>>();
const nodeSpecs = ref<FoundryNodeSpec[]>([]);
const typeDetails = ref<Array<{ name: PortType; detail: string; color?: string }>>([]);
const colorsByType = ref<Record<string, string>>({});
const typeConversions = ref<Array<{ from: PortType; to: PortType }>>([]);
const nodeCatalogLoaded = ref(false);
const uploadedByNode = reactive<Record<string, UploadedStructure[]>>({});
const DEFAULT_API_BASE = "http://127.0.0.1:3000/api";
const DEFAULT_WORKFLOW_PRESET = "ligand-binder-denovo.fuiworkflow";
const apiBase = ref(DEFAULT_API_BASE);
const apiStatus = ref<"idle" | "checking" | "available" | "unavailable">("idle");
const apiMessage = ref("Enter API URL");
const runState = ref<"idle" | "validating" | "queued" | "running" | "completed" | "failed" | "stopped">("idle");
const currentRunId = ref("");
const currentSessionId = ref("");
const runStatus = ref<RunStatus | null>(null);
const runMessage = ref("Ready");
const runLogs = ref<string[]>([]);
const validationErrors = ref<Array<Record<string, any>>>([]);
const artifacts = ref<BackendArtifact[]>([]);
const savedArtifacts = ref<BackendArtifact[]>([]);
const outputs = ref<BackendOutput[]>([]);
const workflowPresets = ref<WorkflowPreset[]>([]);
const selectedWorkflowPreset = ref("");
const errorNodeIds = ref(new Set<string>());
const cachedNodeIds = ref(new Set<string>());
const pendingInputNodeIds = ref(new Set<string>());
const eventSource = ref<EventSource | null>(null);
const nodeElements = new Map<string, HTMLElement>();
const manualSelections = reactive<Record<string, Record<string, string>>>({});
const runtimeInputPayloads = reactive<Record<string, Record<string, any>>>({});
const runStateLabel = computed(() => (runState.value === "failed" ? "ERROR" : runState.value.toUpperCase()));
const isRunActive = computed(() => runState.value === "validating" || runState.value === "queued" || runState.value === "running");
const normalizedApiBase = computed(() => normalizeApiBase(apiBase.value));
const viewerEl = ref<HTMLElement | null>(null);
const workflowFileInput = ref<HTMLInputElement | null>(null);
const viewerRuntimeFiles = ref<UploadedStructure[]>([]);
const pendingRunInput = ref<PendingRunInput | null>(null);
const activeSidebarPanel = ref<SidebarPanel | null>(null);
const logsFollowBottom = ref(true);
const viewerModal = reactive<ViewerModal>({
  open: false,
  nodeId: "",
  title: "",
  mode: "structure",
  fileIndex: 0,
  style: "cartoon",
});
let viewer: any;
let viewerZoomKey = "";
let viewerOpenSequence = 0;
let catalogRegistered = false;

const sidebarPanels: Array<{ key: SidebarPanel; label: string; icon: string }> = [
  { key: "logs", label: "Logs", icon: ">" },
  { key: "saves", label: "Save", icon: "↓" },
  { key: "nodes", label: "Nodes", icon: "+" },
  { key: "issues", label: "Issues", icon: "!" },
];

const canBulkSelectAtoms = computed(() => viewerModal.mode === "atom" && !isChiralityTargetMode());

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
  if (!import.meta.client) return;
  apiBase.value = localStorage.getItem("foundryui-api-base") ?? DEFAULT_API_BASE;
  apiMessage.value = apiBase.value === DEFAULT_API_BASE ? "Using default local API" : "API URL loaded";
}

async function connectApi() {
  apiStatus.value = "checking";
  apiMessage.value = "Checking API";
  try {
    const response = await fetch(apiUrl("/health"), { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Health check failed (${response.status})`);
    }
    localStorage.setItem("foundryui-api-base", normalizedApiBase.value);
    apiBase.value = normalizedApiBase.value;
    await loadNodeCatalog();
    apiStatus.value = "available";
    apiMessage.value = "API available";
    await ensureSession();
  } catch (error) {
    apiStatus.value = "unavailable";
    apiMessage.value = error instanceof Error ? error.message : "API unavailable";
  }
}

async function loadNodeCatalog() {
  if (nodeCatalogLoaded.value) return;
  const catalog = await getJson<NodeCatalogResponse>("/api/nodes");
  typeDetails.value = catalog.types ?? [];
  colorsByType.value = Object.fromEntries(typeDetails.value.map((type) => [type.name, type.color ?? "#6d7681"]));
  typeConversions.value = catalog.conversions ?? [];
  nodeSpecs.value = catalog.nodes ?? [];
  registerTypes();
  registerNodes();
  nodeCatalogLoaded.value = true;
}

const FileUploadControl = markRaw(
  defineComponent({
    name: "FileUploadControl",
    props: {
      intf: { type: Object, required: true },
      node: { type: Object, required: true },
    },
    setup(props) {
      const status = ref("");
      async function onChange(event: Event) {
        const input = event.target as HTMLInputElement;
        const files = [...(input.files ?? [])];
        const loaded = await Promise.all(
          files.map(async (file) => ({
            name: file.name,
            type: detectStructureType(file.name),
            content: await file.text(),
          })),
        );
        uploadedByNode[(props.node as AbstractNode).id] = loaded;
        (props.intf as NodeInterfaceTypeBase<string>).value = loaded.map((file) => file.name).join(", ");
        status.value = loaded.length ? `${loaded.length} file${loaded.length === 1 ? "" : "s"} loaded` : "";
      }

      return () =>
        h("label", { class: "grid gap-1.5 p-2" }, [
              h("span", { class: "text-xs text-[#d7dee8]" }, (props.intf as NodeInterfaceTypeBase).name),
              h("input", {
                class: "w-full text-xs text-[#d7dee8] bg-[#176f5d] cursor-pointer rounded-md border border-[#64758b] px-1 py-0.5",
                type: "file",
                multiple: true,
                accept: (props.intf as any).accept, 
                onChange,
              }),
              status.value ? h("small", { class: "text-[#7ee0c4]" }, status.value) : null,
            ])
    },
  }),
);

const ViewerButtonControl = markRaw(
  defineComponent({
    name: "ViewerButtonControl",
    props: {
      intf: { type: Object, required: true },
      node: { type: Object, required: true },
    },
    setup(props) {
      function open() {
        const node = props.node as AbstractNode;
        openViewer(node.id, node.title, (props.intf as any).viewerMode ?? "structure");
      }
      return () =>
        h(
              "button",
              {
                class: "mx-2 my-1.5 min-h-[30px] w-[calc(100%_-_16px)] cursor-pointer rounded-md border border-[#64758b] bg-[#273242] text-[#eef4fb]",
                type: "button",
                title: (props.intf as NodeInterfaceTypeBase).name,
                onClick: open,
              },
              [(props.intf as NodeInterfaceTypeBase).name],
            );
    },
  }),
);

function createPortInterface(port: PortSpec, isInput = false) {
  const intf = new NodeInterface(port.optional ? `${port.label}*` : port.label, null);
  intf.setPort(true);
  if (isInput && port.type.startsWith("Batch ")) {
    (intf as any).allowMultipleConnections = true;
  }
  applyPortType(intf, port.type);
  return intf;
}

function createOptionInterface(option: OptionSpec) {
  let intf: NodeInterfaceTypeBase<any>;
  if (option.kind === "textarea") {
    intf = new TextareaInputInterface(option.label, String(option.value));
  } else if (option.kind === "text") {
    intf = new TextInputInterface(option.label, String(option.value));
  } else if (option.kind === "int") {
    intf = new IntegerInterface(option.label, Number(option.value), option.min, option.max);
  } else if (option.kind === "float") {
    intf = new NumberInterface(option.label, Number(option.value), option.min, option.max);
  } else if (option.kind === "bool") {
    intf = new CheckboxInterface(option.label, Boolean(option.value));
  } else if (option.kind === "select") {
    intf = new SelectInterface(option.label, String(option.value), option.items ?? []);
  } else if (option.kind === "file") {
    intf = new NodeInterface(option.label, String(option.value)).setComponent(FileUploadControl);
    (intf as any).accept = option.accept ?? "";
  } else {
    intf = new NodeInterface(option.label, String(option.value)).setComponent(ViewerButtonControl);
    (intf as any).viewerMode = option.viewerMode ?? "structure";
  }
  intf.setPort(false);
  return intf;
}

function applyPortType(intf: NodeInterfaceTypeBase<any>, type: PortType) {
  const foundryType = typeRegistry.get(type);
  if (foundryType) {
    setType(intf, foundryType);
  }
}

function createFoundryNode(spec: FoundryNodeSpec) {
  return defineNode({
    type: spec.type,
    title: spec.title,
    inputs: Object.fromEntries([
      ...(spec.inputs ?? []).map((input) => [input.key, () => createPortInterface(input, true)]),
      ...(spec.options ?? []).map((option) => [option.key, () => createOptionInterface(option)]),
    ]),
    outputs: Object.fromEntries((spec.outputs ?? []).map((output) => [output.key, () => createPortInterface(output, false)])),
  });
}

function registerTypes() {
  if (catalogRegistered) return;
  const interfaceTypes = new BaklavaInterfaceTypes(baklava.editor, { viewPlugin: baklava });
  typeDetails.value.forEach(({ name }) => {
    typeRegistry.set(name, new NodeInterfaceType(name));
  });

  typeConversions.value.forEach((conversion) => {
    const source = typeRegistry.get(conversion.from);
    const target = typeRegistry.get(conversion.to);
    if (source && target) source.addConversion(target, (value) => value);
  });

  interfaceTypes.addTypes(...typeRegistry.values());
}

function registerNodes() {
  nodeSpecs.value.forEach((spec) => {
    const nodeConstructor = createFoundryNode(spec);
    registeredConstructors.set(spec.type, nodeConstructor);
    baklava.editor.registerNodeType(nodeConstructor, { category: spec.category, title: spec.title });
  });
  catalogRegistered = true;
}

function toggleSidebarPanel(panel: SidebarPanel) {
  activeSidebarPanel.value = activeSidebarPanel.value === panel ? null : panel;
  if (panel === "logs") void nextTick(scrollLogsToBottom);
}

function openSidebarPanel(panel: SidebarPanel) {
  activeSidebarPanel.value = panel;
  if (panel === "logs") void nextTick(scrollLogsToBottom);
}

function addNodeFromSidebar(type: string) {
  const Constructor = registeredConstructors.get(type);
  if (!Constructor) return;
  const node = new Constructor();
  const offset = baklava.editor.graph.nodes.length * 24;
  (node as any).position = { x: 80 + (offset % 260), y: 80 + (offset % 180) };
  baklava.editor.graph.addNode(node);
}

function specPrimaryColor(spec: FoundryNodeSpec) {
  return portColor(spec.outputs?.[0]?.type ?? spec.inputs?.[0]?.type);
}

function portColor(typeName: string | undefined) {
  return typeName ? colorsByType.value[typeName] ?? "#6d7681" : "#6d7681";
}

function primaryNodeColor(node: AbstractNode) {
  const spec = specForNode(node);
  if (spec) return specPrimaryColor(spec);
  const output = Object.values(node.outputs).find((intf) => getType(intf));
  const input = Object.values(node.inputs).find((intf) => getType(intf));
  return portColor(output || input ? getType((output ?? input)!) : undefined);
}

function nodeRequiresRuntimeInput(node: AbstractNode) {
  return Boolean(specForNode(node)?.requiresRuntimeInput);
}

function uiForNode(node: AbstractNode | undefined) {
  return node ? specForNode(node)?.ui ?? {} : {};
}

function runtimeViewerMode(node: AbstractNode | undefined, event: RunEventPayload): ViewerModal["mode"] {
  const uiMode = uiForNode(node).viewerMode;
  if (uiMode) return uiMode as ViewerModal["mode"];
  return event.node_type === "ResidueSelector"
    ? "residue"
    : event.node_type === "ProteinAtomSelector" || event.node_type === "ResidueAtomSelector"
      ? "proteinAtom"
      : event.node_type === "ProteinChainSelector" || event.node_type === "ChainFilter"
        ? "chain"
        : event.node_type === "FilterByScore"
          ? "score"
          : "atom";
}

function connectionColor(connection: Connection) {
  return portColor(getType(connection.from));
}

function nodeByModal() {
  return baklava.editor.graph.findNodeById(viewerModal.nodeId);
}

function selectorInterface(node = nodeByModal()) {
  if (!node) return undefined;
  const selectorFields = uiForNode(node).selectorFields ?? {};
  const metadataField = selectorFields[viewerModal.mode];
  if (metadataField && (!pendingRunInput.value || pendingRunInput.value.fields.includes(metadataField))) {
    return node.inputs[metadataField] as NodeInterfaceTypeBase<string> | undefined;
  }
  if (isChiralityTargetMode(node)) return node.inputs.chiralityTargets as NodeInterfaceTypeBase<string> | undefined;
  if (pendingRunInput.value?.fields.includes("proteinAtoms") || viewerModal.mode === "proteinAtom") return node.inputs.proteinAtoms as NodeInterfaceTypeBase<string> | undefined;
  if (pendingRunInput.value?.fields.includes("chains") || viewerModal.mode === "chain") return node.inputs.chains as NodeInterfaceTypeBase<string> | undefined;
  if (viewerModal.mode === "atom") return node.inputs.atoms as NodeInterfaceTypeBase<string> | undefined;
  if (viewerModal.mode === "residue") return node.inputs.residues as NodeInterfaceTypeBase<string> | undefined;
  return undefined;
}

function isChiralityTargetMode(node = nodeByModal()) {
  return Boolean(pendingRunInput.value?.fields.includes("chiralityTargets") || (node && (uiForNode(node).chiralityTargets || (String(node.type) === "FilterAtomsChirality" && viewerModal.mode === "atom"))));
}

function selectorValue() {
  return String(selectorInterface()?.value ?? "");
}

function runtimeChoiceValue(field: string) {
  const node = pendingRunInput.value ? baklava.editor.graph.findNodeById(pendingRunInput.value.nodeId) : undefined;
  return String(node?.inputs[field]?.value ?? "");
}

function setRuntimeChoiceValue(field: string, value: string) {
  const node = pendingRunInput.value ? baklava.editor.graph.findNodeById(pendingRunInput.value.nodeId) : undefined;
  const intf = node?.inputs[field];
  if (intf) intf.value = value;
  if (pendingRunInput.value) {
    manualSelections[pendingRunInput.value.nodeId] = { ...manualSelections[pendingRunInput.value.nodeId], [field]: value };
    void saveSessionDocument();
  }
}

function setNodeInputValue(nodeId: string, field: string, value: string) {
  const node = baklava.editor.graph.findNodeById(nodeId);
  const intf = node?.inputs[field];
  if (intf) intf.value = value;
}

function setSelectorValue(value: string) {
  const intf = selectorInterface();
  if (intf) {
    intf.value = value;
    const node = nodeByModal();
    if (node && nodeRequiresRuntimeInput(node)) {
      manualSelections[node.id] = { ...manualSelections[node.id], [interfaceKey(node, intf)]: value };
      void saveSessionDocument();
    }
    void nextTick(renderViewer);
  }
}

function toggleSelectorItem(value: string) {
  if (pendingRunInput.value?.fields.includes("chiralityTargets")) {
    const targets = parseChiralityTargets(selectorValue());
    const existing = targets.find((target) => target.atom === value);
    const next = existing ? targets.filter((target) => target.atom !== value) : [...targets, { atom: value, chirality: "R" }];
    setSelectorValue(formatChiralityTargets(next));
    return;
  }
  const values = parseSelectorList(selectorValue());
  const next = values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
  setSelectorValue(next.join(","));
}

function selectAllAtomsInViewer() {
  if (!activeModalFile.value || !canBulkSelectAtoms.value) return;
  setSelectorValue(atomNamesFromContent(activeModalFile.value.content).join(","));
}

function clearSelectorSelection() {
  setSelectorValue("");
}

function toggleProteinAtom(atom: any) {
  const residue = residueId(atom);
  const name = atomId(atom);
  if (!residue || !name) return;
  const selected = parseProteinAtomMap(selectorValue());
  const atoms = selected[residue] ?? [];
  selected[residue] = atoms.includes(name) ? atoms.filter((atomName) => atomName !== name) : [...atoms, name];
  if (!selected[residue].length) delete selected[residue];
  setSelectorValue(formatProteinAtomMap(selected));
}

function setChiralityTarget(atom: string, chirality: string) {
  setSelectorValue(formatChiralityTargets(parseChiralityTargets(selectorValue()).map((target) => (target.atom === atom ? { ...target, chirality } : target))));
}

function removeChiralityTarget(atom: string) {
  setSelectorValue(formatChiralityTargets(parseChiralityTargets(selectorValue()).filter((target) => target.atom !== atom)));
}

function submitViewerSelection() {
  closeViewer();
}

async function submitRuntimeInput() {
  const input = pendingRunInput.value;
  if (!input) return;
  const values: Record<string, string> = {};
  input.fields.forEach((field) => {
    const node = baklava.editor.graph.findNodeById(input.nodeId);
    values[field] = String(node?.inputs[field]?.value ?? "");
  });
  manualSelections[input.nodeId] = { ...manualSelections[input.nodeId], ...values };
  await postJson(`/api/runs/${input.runId}/input`, {
    node_id: input.nodeId,
    values,
  });
  runMessage.value = "Input submitted";
  setNodePendingInput(input.nodeId, false);
  if (pendingRunInput.value?.nodeId === input.nodeId && pendingRunInput.value.sequence === input.sequence) {
    pendingRunInput.value = null;
    closeViewer();
  }
  await saveSessionDocument();
}

function specForNode(node: AbstractNode) {
  return nodeSpecs.value.find((spec) => spec.type === node.type);
}

function interfaceKey(node: AbstractNode | undefined, intf: NodeInterfaceTypeBase<any>) {
  if (!node) return intf.name;
  const input = Object.entries(node.inputs).find(([, candidate]) => candidate.id === intf.id);
  if (input) return input[0];
  const output = Object.entries(node.outputs).find(([, candidate]) => candidate.id === intf.id);
  return output?.[0] ?? intf.name;
}

function normalizedWorkflow() {
  const nodes = baklava.editor.graph.nodes.map((node) => {
    const spec = specForNode(node);
    const inputKeys = new Set((spec?.inputs ?? []).map((input) => input.key));
    const optionKeys = new Set((spec?.options ?? []).map((option) => option.key));

    return {
      id: node.id,
      type: node.type,
      title: node.title,
      position: node.position,
      inputs: Object.fromEntries(
        Object.entries(node.inputs)
          .filter(([key]) => inputKeys.has(key))
          .map(([key, intf]) => [key, { label: intf.name.replace(/\*$/, ""), type: getType(intf), optional: intf.name.endsWith("*") }]),
      ),
      options: Object.fromEntries(
        Object.entries(node.inputs)
          .filter(([key]) => optionKeys.has(key))
          .map(([key, intf]) => [key, intf.value]),
      ),
      outputs: Object.fromEntries(Object.entries(node.outputs).map(([key, intf]) => [key, { label: intf.name, type: getType(intf) }])),
    };
  });

  const connections = baklava.editor.graph.connections.map((connection) => {
    const fromNode = baklava.editor.graph.findNodeById(connection.from.nodeId);
    const toNode = baklava.editor.graph.findNodeById(connection.to.nodeId);
    return {
      from: {
        nodeId: connection.from.nodeId,
        key: interfaceKey(fromNode, connection.from),
        type: getType(connection.from),
      },
      to: {
        nodeId: connection.to.nodeId,
        key: interfaceKey(toNode, connection.to),
        type: getType(connection.to),
      },
    };
  });

  return { nodes, connections };
}

function workflowDocument() {
  return {
    fileType: "FoundryUIWorkflow",
    extension: ".fuiworkflow",
    version: 1,
    savedAt: new Date().toISOString(),
    baklava: baklava.editor.save(),
    workflow: normalizedWorkflow(),
    uploads: Object.fromEntries(Object.entries(uploadedByNode).map(([nodeId, files]) => [nodeId, files])),
    manualSelections: Object.fromEntries(Object.entries(manualSelections).map(([nodeId, values]) => [nodeId, { ...values }])),
    runtimeInputPayloads: Object.fromEntries(Object.entries(runtimeInputPayloads).map(([nodeId, payloads]) => [nodeId, { ...payloads }])),
  };
}

function loadWorkflowDocument(document: any) {
  migrateWorkflowDocument(document);
  const state = document.baklava ?? document.graph ?? document;
  const warnings = baklava.editor.load(state);
  Object.keys(uploadedByNode).forEach((nodeId) => {
    delete uploadedByNode[nodeId];
  });
  Object.entries(document.uploads ?? {}).forEach(([nodeId, files]) => {
    uploadedByNode[nodeId] = files as UploadedStructure[];
  });
  Object.keys(manualSelections).forEach((nodeId) => {
    delete manualSelections[nodeId];
  });
  Object.keys(runtimeInputPayloads).forEach((nodeId) => {
    delete runtimeInputPayloads[nodeId];
  });
  Object.entries(document.manualSelections ?? {}).forEach(([nodeId, values]) => {
    if (!values || typeof values !== "object" || Array.isArray(values)) return;
    manualSelections[nodeId] = Object.fromEntries(Object.entries(values).map(([key, value]) => [key, String(value ?? "")]));
  });
  Object.entries(document.runtimeInputPayloads ?? {}).forEach(([nodeId, payloads]) => {
    if (!payloads || typeof payloads !== "object" || Array.isArray(payloads)) return;
    runtimeInputPayloads[nodeId] = payloads as Record<string, any>;
  });
  restoreManualSelections();
  if (warnings.length) {
    console.warn("Workflow loaded with warnings", warnings);
  }
}

function restoreManualSelections() {
  Object.entries(manualSelections).forEach(([nodeId, values]) => {
    Object.entries(values).forEach(([field, value]) => {
      setNodeInputValue(nodeId, field, value);
    });
  });
}

function migrateWorkflowDocument(document: any) {
  const visit = (value: any) => {
    if (!value || typeof value !== "object") return;
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    Object.entries(value).forEach(([key, nested]) => {
      if (key === "type" && nested === "ProteinAtomSelector") value[key] = "ResidueAtomSelector";
      if (key === "type" && nested === "ProteinChainSelector") value[key] = "ChainFilter";
      if (key === "type" && nested === "Protein Atoms List") value[key] = "Residues Atoms List";
      if (key === "name" && nested === "Protein Atoms List") value[key] = "Residues Atoms List";
      visit(nested);
    });
  };
  visit(document);
}

function saveWorkflow() {
  const blob = new Blob([JSON.stringify(workflowDocument(), null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `foundryui-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.fuiworkflow`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  runState.value = "idle";
  void saveSessionDocument();
}

async function loadWorkflowPresets() {
  try {
    const response = await fetch("/workflows/presets.json", { cache: "no-store" });
    if (!response.ok) return;
    const payload = (await response.json()) as { presets?: WorkflowPreset[] };
    workflowPresets.value = (payload.presets ?? []).filter((preset) => preset.label && preset.file);
  } catch {
    workflowPresets.value = [];
  }
}

function requestLoadWorkflow() {
  workflowFileInput.value?.click();
}

async function loadWorkflowPreset() {
  if (!selectedWorkflowPreset.value) return;
  try {
    await loadWorkflowPresetFile(selectedWorkflowPreset.value);
    await saveSessionDocument();
    selectedWorkflowPreset.value = "";
  } catch (error) {
    window.alert(error instanceof Error ? error.message : "Could not load preset workflow.");
  }
}

async function loadWorkflowPresetFile(file: string) {
  const response = await fetch(`/workflows/${file}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load preset (${response.status})`);
  loadWorkflowDocument(await response.json());
}

async function loadWorkflow(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  if (!file.name.endsWith(".fuiworkflow")) {
    window.alert("Please load a .fuiworkflow file.");
    input.value = "";
    return;
  }
  const document = JSON.parse(await file.text());
  loadWorkflowDocument(document);
  await saveSessionDocument();
  input.value = "";
}

function clearWorkflow(save: boolean | Event = true) {
  [...baklava.editor.graph.nodes].forEach((node) => baklava.editor.graph.removeNode(node));
  Object.keys(manualSelections).forEach((nodeId) => {
    delete manualSelections[nodeId];
  });
  Object.keys(runtimeInputPayloads).forEach((nodeId) => {
    delete runtimeInputPayloads[nodeId];
  });
  if (save !== false) void saveSessionDocument();
}

async function queueRun() {
  closeRunEvents();
  resetRunUi();
  runState.value = "validating";
  runMessage.value = "Validating workflow";
  const document = workflowDocument();

  try {
    const validation = await postJson<{ valid: boolean; errors: Array<Record<string, any>> }>(
      "/api/workflows/validate",
      { document },
    );
    validationErrors.value = validation.errors ?? [];
    if (!validation.valid) {
      runState.value = "failed";
      runMessage.value = "Validation failed";
      openSidebarPanel("issues");
      return;
    }

    const created = await postJson<{ accepted: boolean; run_id?: string; state?: string; errors?: Array<Record<string, any>> }>(
      "/api/runs",
      { document, session_id: currentSessionId.value || undefined },
    );
    if (!created.accepted || !created.run_id) {
      validationErrors.value = created.errors ?? [];
      runState.value = "failed";
      runMessage.value = "Run was rejected";
      openSidebarPanel("issues");
      return;
    }

    currentRunId.value = created.run_id;
    outputs.value = [];
    savedArtifacts.value = [];
    artifacts.value = [];
    runState.value = "queued";
    runMessage.value = `Queued ${created.run_id}`;
    connectRunEvents(created.run_id);
    await refreshRunStatus(created.run_id);
  } catch (error) {
    runState.value = "failed";
    runMessage.value = error instanceof Error ? error.message : "Backend request failed";
    openSidebarPanel("issues");
  }
}

function resetRunUi() {
  runLogs.value = [];
  logsFollowBottom.value = true;
  validationErrors.value = [];
  runStatus.value = null;
  pendingRunInput.value = null;
  clearPendingInputs();
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(readBackendMessage(payload, response.statusText));
  }
  return payload as T;
}

async function putJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(apiUrl(path), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(readBackendMessage(payload, response.statusText));
  }
  return payload as T;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path));
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(readBackendMessage(payload, response.statusText));
  }
  return payload as T;
}

async function ensureSession() {
  if (!normalizedApiBase.value) {
    runMessage.value = "Enter API URL and click Connect";
    return;
  }
  const route = useRoute();
  const router = useRouter();
  const requestedSession = typeof route.query.session === "string" ? route.query.session : "";
  if (requestedSession) {
    try {
      const session = await getJson<SessionRecord>(`/api/sessions/${requestedSession}`);
      currentSessionId.value = session.session_id;
      if (session.document) {
        loadWorkflowDocument(session.document);
      }
      if (session.latest_run_id) {
        currentRunId.value = session.latest_run_id;
        await refreshRunStatus(session.latest_run_id);
        await refreshRunFiles(session.latest_run_id);
        if (runState.value === "queued" || runState.value === "running") {
          connectRunEvents(session.latest_run_id);
        }
      }
      return;
    } catch (error) {
      runMessage.value = error instanceof Error ? error.message : "Could not load session";
    }
  }
  await ensureDefaultWorkflowLoaded();
  const session = await postJson<SessionRecord>("/api/sessions", { document: workflowDocument() });
  currentSessionId.value = session.session_id;
  await router.replace({ query: { ...route.query, session: session.session_id } });
}

async function createNewSession() {
  closeRunEvents();
  const route = useRoute();
  const router = useRouter();
  clearWorkflow(false);
  await loadDefaultWorkflow();
  const session = await postJson<SessionRecord>("/api/sessions", { document: workflowDocument() });
  currentSessionId.value = session.session_id;
  currentRunId.value = "";
  runStatus.value = null;
  outputs.value = [];
  artifacts.value = [];
  savedArtifacts.value = [];
  validationErrors.value = [];
  runLogs.value = [];
  runState.value = "idle";
  runMessage.value = "New session created";
  await router.replace({ query: { ...route.query, session: session.session_id } });
}

async function loadDefaultWorkflow() {
  try {
    await loadWorkflowPresetFile(DEFAULT_WORKFLOW_PRESET);
  } catch (error) {
    clearWorkflow(false);
    runMessage.value = error instanceof Error ? error.message : "Could not load default workflow";
  }
}

async function ensureDefaultWorkflowLoaded() {
  if (baklava.editor.graph.nodes.length) return;
  await loadDefaultWorkflow();
}

async function saveSessionDocument() {
  if (!currentSessionId.value) return;
  await putJson<SessionRecord>(`/api/sessions/${currentSessionId.value}`, {
    latest_run_id: currentRunId.value || undefined,
    document: workflowDocument(),
  });
}

async function refreshRunStatus(runId = currentRunId.value) {
  if (!runId) return;
  const response = await fetch(apiUrl(`/api/runs/${runId}`));
  if (!response.ok) return;
  const status = (await response.json()) as RunStatus;
  runStatus.value = status;
  if (status.state === "running") runState.value = "running";
  if (status.state === "queued") runState.value = "queued";
  if (status.state === "completed") runState.value = "completed";
  if (status.state === "failed") runState.value = "failed";
  if (status.state === "stopped") runState.value = "stopped";
  if (status.recent_output?.length) {
    runLogs.value = status.recent_output.slice(-160);
  }
  openPendingInputFromStatus(status);
}

function openPendingInputFromStatus(status: RunStatus) {
  const pending = status.pending_inputs?.find((event) => event.node_id);
  if (!pending || status.state === "completed" || status.state === "failed" || status.state === "stopped") return;
  if (pendingRunInput.value?.nodeId === pending.node_id) return;
  void openRuntimeInput(pending);
}

async function loadArtifacts(runId = currentRunId.value) {
  if (!runId) return;
  const response = await fetch(apiUrl(`/api/runs/${runId}/artifacts`));
  if (!response.ok) return;
  const payload = (await response.json()) as { artifacts: BackendArtifact[] };
  artifacts.value = payload.artifacts ?? [];
}

async function loadSavedArtifacts(runId = currentRunId.value) {
  if (!runId) return;
  const response = await fetch(apiUrl(`/api/runs/${runId}/saves`));
  if (!response.ok) return;
  const payload = (await response.json()) as { artifacts: BackendArtifact[] };
  savedArtifacts.value = payload.artifacts ?? [];
}

async function loadOutputs(runId = currentRunId.value) {
  if (!runId) return;
  const response = await fetch(apiUrl(`/api/runs/${runId}/outputs`));
  if (!response.ok) return;
  const payload = (await response.json()) as { outputs: BackendOutput[] };
  outputs.value = payload.outputs ?? [];
}

async function refreshRunFiles(runId = currentRunId.value) {
  await Promise.all([loadArtifacts(runId), loadSavedArtifacts(runId), loadOutputs(runId)]);
}

async function stopRun() {
  if (!currentRunId.value) return;
  await postJson(`/api/runs/${currentRunId.value}/stop`, {});
  runMessage.value = "Stopping run";
}

function connectRunEvents(runId: string) {
  closeRunEvents();
  const source = new EventSource(apiUrl(`/api/runs/${runId}/events`));
  eventSource.value = source;
  const eventNames = [
    "queued",
    "started",
    "node_started",
    "node_progress",
    "stdout",
    "stderr",
    "node_completed",
    "input_required",
    "artifact_created",
    "warning",
    "error",
    "completed",
    "stopped",
  ];
  eventNames.forEach((eventName) => {
    source.addEventListener(eventName, (event) => {
      const message = event as MessageEvent;
      if (!message.data) return;
      handleRunEvent(JSON.parse(message.data) as RunEventPayload);
    });
  });
  source.onerror = () => {
    if (runState.value !== "completed" && runState.value !== "failed" && runState.value !== "stopped") {
      runMessage.value = "Event stream disconnected";
      void refreshRunStatus(runId);
    }
    closeRunEvents();
  };
}

function handleRunEvent(event: RunEventPayload) {
  if (event.message && (event.event === "stdout" || event.event === "stderr")) {
    runLogs.value = [...runLogs.value, `${event.event}: ${event.message}`].slice(-160);
  }
  if (event.event === "started") {
    runState.value = "running";
    runMessage.value = "Run started";
  } else if (event.event === "node_started") {
    runState.value = "running";
    runMessage.value = `${event.node_type ?? "Node"} started`;
    if (event.node_id) clearNodeError(event.node_id);
  } else if (event.event === "node_completed") {
    runMessage.value = `${event.node_type ?? "Node"} completed`;
    if (event.node_id) setNodePendingInput(event.node_id, false);
    if (shouldClosePendingInput(event)) {
      pendingRunInput.value = null;
      closeViewer();
    }
    if (event.node_id && event.data?.cached) markNodeCached(event.node_id);
    void refreshRunStatus(event.run_id);
    void loadOutputs(event.run_id);
  } else if (event.event === "artifact_created") {
    void refreshRunFiles(event.run_id);
  } else if (event.event === "input_required") {
    runState.value = "running";
    runMessage.value = `${event.node_type ?? "Node"} needs input`;
    void openRuntimeInput(event);
  } else if (event.event === "node_progress" && event.node_id && event.message === "User input received.") {
    setNodePendingInput(event.node_id, false);
    if (shouldClosePendingInput(event)) {
      pendingRunInput.value = null;
      closeViewer();
    }
  } else if (event.event === "error") {
    runState.value = "failed";
    runMessage.value = event.message ?? "Run failed";
    if (event.node_id) setNodePendingInput(event.node_id, false);
    if (event.data?.error) validationErrors.value = [event.data.error, ...validationErrors.value];
    if (event.node_id) markNodeError(event.node_id);
    openSidebarPanel("issues");
    void refreshRunStatus(event.run_id);
    void refreshRunFiles(event.run_id);
    closeRunEvents();
  } else if (event.event === "completed") {
    runState.value = "completed";
    runMessage.value = "Run completed";
    clearPendingInputs();
    openSidebarPanel("saves");
    void refreshRunStatus(event.run_id);
    void refreshRunFiles(event.run_id);
    void saveSessionDocument();
    closeRunEvents();
  } else if (event.event === "stopped") {
    runState.value = "stopped";
    runMessage.value = "Run stopped";
    clearPendingInputs();
    void refreshRunStatus(event.run_id);
    void refreshRunFiles(event.run_id);
    closeRunEvents();
  }
}

function shouldClosePendingInput(event: RunEventPayload) {
  if (!event.node_id || pendingRunInput.value?.nodeId !== event.node_id) return false;
  return Number(event.sequence ?? 0) > pendingRunInput.value.sequence;
}

function closeRunEvents() {
  eventSource.value?.close();
  eventSource.value = null;
}

function artifactUrl(artifact: BackendArtifact) {
  return apiUrl(`/api/artifacts/${artifact.artifact_id}`);
}

function archiveUrl() {
  return currentRunId.value ? apiUrl(`/api/runs/${currentRunId.value}/archive`) : "#";
}

function onLogsScroll(event: Event) {
  const el = event.target as HTMLElement | null;
  if (!el) return;
  logsFollowBottom.value = el.scrollTop + el.clientHeight >= el.scrollHeight - 8;
}

function scrollLogsToBottom() {
  const el = document.querySelector<HTMLElement>(".terminal-log");
  if (el) el.scrollTop = el.scrollHeight;
}

function markNodeError(nodeId: string) {
  const next = new Set(errorNodeIds.value);
  next.add(nodeId);
  errorNodeIds.value = next;
  applyNodeRuntimeClasses(nodeId);
}

function clearNodeError(nodeId: string) {
  if (!errorNodeIds.value.has(nodeId)) return;
  const next = new Set(errorNodeIds.value);
  next.delete(nodeId);
  errorNodeIds.value = next;
  applyNodeRuntimeClasses(nodeId);
}

function markNodeCached(nodeId: string) {
  const next = new Set(cachedNodeIds.value);
  next.add(nodeId);
  cachedNodeIds.value = next;
  applyNodeRuntimeClasses(nodeId);
}

function setNodePendingInput(nodeId: string, pending: boolean) {
  const next = new Set(pendingInputNodeIds.value);
  if (pending) {
    next.add(nodeId);
  } else {
    next.delete(nodeId);
  }
  pendingInputNodeIds.value = next;
  applyNodeRuntimeClasses(nodeId);
}

function clearPendingInputs() {
  const pending = [...pendingInputNodeIds.value];
  pendingInputNodeIds.value = new Set();
  pending.forEach(applyNodeRuntimeClasses);
}

function applyNodeRuntimeClasses(nodeId: string) {
  const el = nodeElements.get(nodeId);
  if (!el) return;
  el.classList.toggle("foundry-node-pending-input", pendingInputNodeIds.value.has(nodeId));
  el.classList.toggle("foundry-node-error", errorNodeIds.value.has(nodeId));
  el.classList.toggle("foundry-node-cached", cachedNodeIds.value.has(nodeId));
}

async function openViewer(nodeId: string, title: string, mode: ViewerModal["mode"]) {
  if (pendingRunInput.value?.nodeId !== nodeId) {
    pendingRunInput.value = null;
  }
  viewerZoomKey = "";
  viewerOpenSequence += 1;
  viewerModal.open = true;
  viewerModal.nodeId = nodeId;
  viewerModal.title = title;
  viewerModal.mode = mode;
  viewerModal.fileIndex = 0;
  viewerRuntimeFiles.value = [];
  await loadViewerRuntimeFiles(nodeId);
  void nextTick(initializeViewer);
}

async function openRuntimeInput(event: RunEventPayload) {
  if (!event.node_id || !event.node_type) return;
  const node = baklava.editor.graph.findNodeById(event.node_id);
  pendingRunInput.value = {
    runId: event.run_id,
    nodeId: event.node_id,
    nodeType: event.node_type,
    fields: event.data?.fields ?? [],
    payloads: event.data?.payloads ?? {},
    choices: event.data?.choices ?? {},
    sequence: Number(event.sequence ?? 0),
  };
  runtimeInputPayloads[event.node_id] = pendingRunInput.value.payloads;
  if (event.data?.defaults && node) {
    Object.entries(event.data.defaults).forEach(([key, value]) => {
      const intf = node.inputs[key];
      if (intf) intf.value = String(value ?? "");
    });
  }
  viewerZoomKey = "";
  viewerOpenSequence += 1;
  viewerModal.open = true;
  viewerModal.nodeId = event.node_id;
  viewerModal.title = node?.title ?? event.node_type;
  setNodePendingInput(event.node_id, true);
  viewerModal.mode = runtimeViewerMode(node, event);
  viewerModal.fileIndex = 0;
  viewerRuntimeFiles.value = await runtimeFilesFromPayloads(pendingRunInput.value.payloads);
  void nextTick(initializeViewer);
}

function closeViewer() {
  viewerModal.open = false;
  viewerZoomKey = "";
  viewer = null;
}

function connectedSourceNode(node: AbstractNode) {
  const inputInterfaces = new Set(Object.values(node.inputs));
  const connection = baklava.editor.graph.connections.find((conn) => inputInterfaces.has(conn.to));
  return connection ? baklava.editor.graph.findNodeById(connection.from.nodeId) : undefined;
}

function connectedSourceOutput(node: AbstractNode) {
  const inputInterfaces = new Set(Object.values(node.inputs));
  const connection = baklava.editor.graph.connections.find((conn) => inputInterfaces.has(conn.to));
  if (!connection) return undefined;
  const source = baklava.editor.graph.findNodeById(connection.from.nodeId);
  if (!source) return undefined;
  const outputKey = interfaceKey(source, connection.from);
  return outputs.value.find((output) => output.node_id === source.id && output.output_key === outputKey)
    ?? outputs.value.find((output) => output.node_id === source.id && output.artifact_ids.length && String(output.type_name ?? "").includes("Protein"));
}

function nodeStructureOutput(node: AbstractNode | undefined) {
  if (!node) return undefined;
  return outputs.value.find((output) => {
    if (output.node_id !== node.id || !output.artifact_ids.length) return false;
    const typeName = String(output.type_name ?? "");
    return typeName.includes("Protein") || typeName === "Batch Structure";
  });
}

async function loadViewerRuntimeFiles(nodeId: string) {
  const node = baklava.editor.graph.findNodeById(nodeId);
  if (!node) return;
  const sourceMode = String(uiForNode(node).structureSource ?? "");
  const viewerManaged = Boolean(sourceMode) || ["PDBViewer", "AtomSelector", "ResidueSelector", "ProteinAtomSelector", "ResidueAtomSelector", "ProteinChainSelector", "ChainFilter", "FilterAtomsChirality"].includes(String(node.type));
  if (!viewerManaged) return;
  if (sourceMode === "runtimePayloadsOrConnectedSource" || String(node.type) === "FilterAtomsChirality") {
    if (pendingRunInput.value?.nodeId === nodeId && runtimeInputPayloads[nodeId]) {
      viewerRuntimeFiles.value = await runtimeFilesFromPayloads(runtimeInputPayloads[nodeId]);
      return;
    }
    const output = connectedSourceOutput(node);
    if (output?.artifact_ids.length) {
      viewerRuntimeFiles.value = await runtimeFilesFromArtifactIds(output.artifact_ids, output.paths);
    }
    return;
  }
  const output = sourceMode === "selfOutputOrConnectedSource" || String(node.type) === "ChainFilter" || String(node.type) === "PDBViewer"
    ? nodeStructureOutput(node) ?? connectedSourceOutput(node)
    : pendingRunInput.value?.nodeId === nodeId
      ? connectedSourceOutput(node)
      : undefined;
  if (!output?.artifact_ids.length) return;
  viewerRuntimeFiles.value = await runtimeFilesFromArtifactIds(output.artifact_ids, output.paths);
}

async function runtimeFilesFromPayloads(payloads: Record<string, any>) {
  const files: UploadedStructure[] = [];
  for (const payload of Object.values(payloads)) {
    files.push(...await runtimeFilesFromArtifactIds(payload?.artifact_ids ?? [], payload?.paths ?? []));
  }
  return files;
}

async function runtimeFilesFromArtifactIds(artifactIds: string[], paths: string[] = []) {
  const files: UploadedStructure[] = [];
  const artifactById = new Map(artifacts.value.map((artifact) => [artifact.artifact_id, artifact]));
  for (const [index, artifactId] of artifactIds.entries()) {
    const artifact = artifactById.get(artifactId);
    const path = artifact?.path ?? paths[index] ?? artifactId;
    if (artifact && artifact.media_type !== "chemical/x-pdb" && !path.toLowerCase().endsWith(".pdb")) continue;
    const response = await fetch(artifact ? artifactUrl(artifact) : apiUrl(`/api/artifacts/${artifactId}`));
    if (!response.ok) continue;
    files.push({ name: path.split("/").pop() || path, type: "pdb", content: await response.text() });
  }
  return files;
}

function structuresForNodeId(nodeId: string, seen = new Set<string>()): UploadedStructure[] {
  if (viewerRuntimeFiles.value.length) return viewerRuntimeFiles.value;
  if (seen.has(nodeId)) return [];
  seen.add(nodeId);
  const node = baklava.editor.graph.findNodeById(nodeId);
  if (node && (uiForNode(node).structureSource || ["PDBViewer", "AtomSelector", "ResidueSelector", "ProteinAtomSelector", "ResidueAtomSelector", "ProteinChainSelector", "ChainFilter", "FilterAtomsChirality"].includes(String(node.type)))) {
    return [];
  }
  const ownFiles = uploadedByNode[nodeId];
  if (ownFiles?.length) return ownFiles;
  const upstream = node ? connectedSourceNode(node) : undefined;
  if (upstream) {
    const upstreamFiles = structuresForNodeId(upstream.id, seen);
    if (upstreamFiles.length) return upstreamFiles;
  }
  return [];
}

const modalFiles = computed(() => structuresForNodeId(viewerModal.nodeId));
const activeModalFile = computed(() => modalFiles.value[Math.min(viewerModal.fileIndex, Math.max(0, modalFiles.value.length - 1))]);

async function initializeViewer() {
  if (!viewerEl.value || !import.meta.client || !viewerModal.open) return;
  const mol = await import("3dmol");
  viewer = mol.createViewer(viewerEl.value, { backgroundColor: "white" });
  try {
    viewer.resize();
  } catch {
    // Some 3Dmol builds do not expose resize; zoom/render below still handles sizing.
  }
  renderViewer();
}

function renderViewer() {
  if (!viewer) return;
  if (!activeModalFile.value) {
    viewer.clear();
    render3dViewer();
    return;
  }
  const file = activeModalFile.value;
  viewer.clear();
  if (file.type === "fasta") {
    render3dViewer();
    return;
  }
  if (!file.content) {
    render3dViewer();
    return;
  }
  let model: any;
  try {
    model = viewer.addModel(file.content, "pdb");
  } catch (error) {
    console.warn("Failed to load PDB content into viewer", error);
    render3dViewer();
    return;
  }
  if (!model) {
    render3dViewer();
    return;
  }
  if (viewerModal.style === "stick" || viewerModal.mode === "atom" || viewerModal.mode === "proteinAtom" || viewerModal.mode === "chain") {
    viewer.setStyle({ hetflag: false }, { stick: { radius: 0.18 } });
    viewer.setStyle({ hetflag: true }, { stick: { colorscheme: "greenCarbon", radius: 0.22 } });
  } else if (viewerModal.style === "surface") {
    viewer.setStyle({ hetflag: false }, { cartoon: { color: "lightgray" } });
    try {
      viewer.addSurface((globalThis as any).$3Dmol?.SurfaceType?.VDW ?? 1, { opacity: 0.6, color: "white" }, { hetflag: false });
    } catch (error) {
      console.warn("Failed to create viewer surface", error);
    }
    viewer.setStyle({ hetflag: true }, { stick: { colorscheme: "greenCarbon", radius: 0.24 } });
  } else {
    viewer.setStyle({ hetflag: false }, { cartoon: { color: "spectrum" } });
    viewer.setStyle({ hetflag: true }, { stick: { colorscheme: "greenCarbon", radius: 0.22 } });
  }
  const selected = new Set(isChiralityTargetMode() ? parseChiralityTargets(selectorValue()).map((target) => target.atom) : parseSelectorList(selectorValue()));
  if (viewerModal.mode === "atom") {
    selected.forEach((name) => {
      viewer.addStyle({ atom: name }, { sphere: { color: "orange", radius: 0.45 } });
    });
    viewer.setClickable({}, true, (atom: any) => {
      toggleSelectorItem(atomId(atom));
    });
  } else if (viewerModal.mode === "residue") {
    selected.forEach((residue) => {
      viewer.addStyle(residueSelection(residue), { stick: { color: "magenta", radius: 0.24 } });
    });
    viewer.setClickable({}, true, (atom: any) => {
      const value = residueId(atom);
      if (value) toggleSelectorItem(value);
    });
  } else if (viewerModal.mode === "proteinAtom") {
    const proteinAtoms = parseProteinAtomMap(selectorValue());
    Object.entries(proteinAtoms).forEach(([residue, atoms]) => {
      const residueSpec = residueSelection(residue);
      atoms.forEach((atom) => {
        viewer.addStyle({ ...residueSpec, atom }, { sphere: { color: "orange", radius: 0.42 } });
      });
    });
    viewer.setClickable({}, true, (atom: any) => {
      toggleProteinAtom(atom);
    });
  } else if (viewerModal.mode === "chain") {
    selected.forEach((chain) => {
      viewer.addStyle({ chain }, { stick: { color: "orange", radius: 0.26 } });
    });
    viewer.setClickable({}, true, (atom: any) => {
      const chain = String(atom.chain || "").trim();
      if (chain) toggleSelectorItem(chain);
    });
  }
  const zoomKey = `${viewerOpenSequence}:${viewerModal.nodeId}:${viewerModal.fileIndex}:${file.name}`;
  if (zoomKey !== viewerZoomKey) {
    try {
      viewer.resize?.();
      viewer.zoomTo();
    } catch {
      viewerZoomKey = "";
      render3dViewer();
      return;
    }
    viewerZoomKey = zoomKey;
  }
  render3dViewer();
}

function render3dViewer() {
  if (!viewer) return;
  try {
    const rendered = viewer.render();
    if (rendered && typeof rendered.catch === "function") {
      rendered.catch((error: unknown) => console.warn("Failed to render 3D viewer", error));
    }
  } catch (error) {
    console.warn("Failed to render 3D viewer", error);
  }
}

watch([() => viewerModal.fileIndex, () => viewerModal.style, () => viewerModal.open], () => {
  void nextTick(renderViewer);
});

watch(runLogs, () => {
  if (logsFollowBottom.value) void nextTick(scrollLogsToBottom);
}, { deep: true });

baklava.hooks.renderInterface.subscribe("foundry-colors", ({ intf, el }) => {
  const type = getType(intf);
  if (type) {
    el.dataset.interfaceType = type;
    el.style.setProperty("--foundry-port-color", portColor(type));
  }
  el.style.removeProperty("display");
  return { intf, el };
});

baklava.hooks.renderNode.subscribe("foundry-node-colors", ({ node, el }) => {
  nodeElements.set(node.id, el);
  el.style.setProperty("--foundry-node-color", primaryNodeColor(node));
  el.classList.toggle("foundry-node-manual", nodeRequiresRuntimeInput(node));
  el.classList.toggle("foundry-node-pending-input", pendingInputNodeIds.value.has(node.id));
  el.classList.toggle("foundry-node-error", errorNodeIds.value.has(node.id));
  el.classList.toggle("foundry-node-cached", cachedNodeIds.value.has(node.id));
  return { node, el };
});

onMounted(() => {
  restoreApiBase();
  void loadWorkflowPresets();
  void nextTick(renderViewer);
  if (normalizedApiBase.value) {
    void connectApi();
  }
});

onBeforeUnmount(() => {
  closeRunEvents();
});
</script>

<template>
  <main class="grid h-screen grid-rows-[auto_minmax(0,1fr)] overflow-hidden bg-[#171d25] max-md:grid-rows-[auto_minmax(520px,1fr)]">
    <TopRunBar
      v-model:api-base="apiBase"
      v-model:selected-workflow-preset="selectedWorkflowPreset"
      :current-run-id="currentRunId"
      :current-session-id="currentSessionId"
      :run-state="runState"
      :run-state-label="runStateLabel"
      :run-status="runStatus"
      :run-message="runMessage"
      :archive-href="archiveUrl()"
      :api-status="apiStatus"
      :api-message="apiMessage"
      :workflow-presets="workflowPresets"
      :is-run-active="isRunActive"
      @connect="connectApi"
      @create-new-session="createNewSession"
      @save-workflow="saveWorkflow"
      @request-load-workflow="requestLoadWorkflow"
      @load-workflow-preset="loadWorkflowPreset"
      @clear-workflow="clearWorkflow"
      @stop-run="stopRun"
      @queue-run="queueRun"
    />
    <input ref="workflowFileInput" class="hidden" type="file" accept=".fuiworkflow" @change="loadWorkflow" />

    <div class="relative grid min-h-0 min-w-0 grid-cols-[minmax(0,1fr)] overflow-hidden">
      <aside
        class="absolute inset-y-0 left-0 z-10 grid min-h-0 border-r border-[#2a3440] bg-[#101720] text-[#d8e1ec] transition-[grid-template-columns] duration-200 max-md:grid-cols-[42px_0]"
        :class="activeSidebarPanel ? 'w-[min(388px,100%)] grid-cols-[48px_minmax(280px,340px)] max-md:w-[min(100%,392px)] max-md:grid-cols-[42px_minmax(250px,calc(100vw_-_42px))]' : 'w-12 grid-cols-[48px_0] max-md:w-[42px]'"
        aria-label="Workspace panels"
      >
        <nav class="grid content-start gap-2 border-r border-[#2a3440] px-[7px] py-2.5 max-md:px-1 max-md:py-2" aria-label="Panel shortcuts">
          <button
            v-for="panel in sidebarPanels"
            :key="panel.key"
            type="button"
            class="grid h-[42px] w-[34px] cursor-pointer content-center place-items-center gap-px rounded-md border text-[15px] font-black max-md:w-16"
            :class="activeSidebarPanel === panel.key ? 'border-[#2ca58d] bg-[#12372f] text-[#7ee0c4]' : 'border-[#334154] bg-[#182231] text-[#d8e1ec]'"
            :title="panel.label"
            @click="toggleSidebarPanel(panel.key)"
          >
            <span aria-hidden="true">{{ panel.icon }}</span>
            <small class="block text-[7px] leading-none font-black tracking-normal">{{ panel.label.toUpperCase() }}</small>
          </button>
        </nav>
        <section v-if="activeSidebarPanel" class="grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)] overflow-hidden bg-[#151c25]">
          <header class="flex min-w-0 items-center justify-between gap-2.5 border-b border-[#2a3440] px-3 py-2.5">
            <h2 class="m-0 text-xs tracking-normal text-[#91a0b2] uppercase">{{ sidebarPanels.find((panel) => panel.key === activeSidebarPanel)?.label }}</h2>
            <button type="button" class="size-8 cursor-pointer rounded-md border border-[#c6d0dc] bg-white font-bold text-[#17202a]" title="Collapse sidebar" @click="activeSidebarPanel = null">X</button>
          </header>

          <div v-if="activeSidebarPanel === 'logs'" class="min-h-0 min-w-0 overflow-auto overscroll-contain px-3 py-2.5">
            <LogsPanel :logs="runLogs" @scroll="onLogsScroll" />
          </div>

          <div v-else-if="activeSidebarPanel === 'saves'" class="min-h-0 min-w-0 overflow-auto overscroll-contain px-3 py-2.5">
            <SavesPanel :artifacts="savedArtifacts" :artifact-url="artifactUrl" />
          </div>

          <div v-else-if="activeSidebarPanel === 'nodes'" class="min-h-0 min-w-0 overflow-auto overscroll-contain px-3 py-2.5">
            <NodeBrowser :node-specs="nodeSpecs" :color-for-spec="specPrimaryColor" @add-node="addNodeFromSidebar" />
          </div>

          <div v-else-if="activeSidebarPanel === 'issues'" class="min-h-0 min-w-0 overflow-auto overscroll-contain px-3 py-2.5">
            <IssuesPanel :errors="validationErrors" :format-details="formatErrorDetails" />
          </div>
        </section>
      </aside>

      <section class="canvas-panel relative min-h-0 min-w-0" aria-label="Workflow canvas">
        <ClientOnly>
          <BaklavaEditor :view-model="baklava">
            <template #connection="{ connection }">
              <g class="typed-connection" :style="{ '--connection-color': connectionColor(connection) }">
                <Components.ConnectionWrapper :connection="connection" />
              </g>
            </template>
          </BaklavaEditor>
        </ClientOnly>
      </section>
    </div>

    <div v-if="viewerModal.open" class="fixed inset-0 z-50 grid place-items-center bg-[rgba(15,22,31,0.62)] p-6" @click.self="closeViewer">
      <section class="max-h-[min(760px,calc(100vh_-_48px))] w-[min(920px,100%)] overflow-auto rounded-lg border border-[#cfd8e3] bg-white p-3.5 shadow-[0_22px_70px_rgba(0,0,0,0.25)]" aria-label="3D selector">
        <header class="flex items-start justify-between gap-4">
          <div>
            <p class="m-0 text-xs font-extrabold text-[#176f5d] uppercase">{{ viewerModal.mode }}</p>
            <h2 class="m-0 text-xl tracking-normal">{{ viewerModal.title }}</h2>
          </div>
          <button type="button" class="size-8 cursor-pointer rounded-md border border-[#c6d0dc] bg-white font-bold text-[#17202a]" title="Close viewer" @click="closeViewer">X</button>
        </header>
        <div class="my-3 flex flex-wrap items-end gap-2 max-md:grid">
          <label v-if="viewerModal.mode !== 'score'" class="grid min-w-[180px] gap-1.5 text-xs font-bold text-[#596575]">
            File
            <select v-model.number="viewerModal.fileIndex" class="h-[34px] rounded-md border border-[#c7d0dc] bg-white text-[#17202a]">
              <option v-for="(file, index) in modalFiles" :key="file.name + index" :value="index">{{ file.name }}</option>
            </select>
          </label>
          <label v-if="viewerModal.mode !== 'score'" class="grid min-w-[180px] gap-1.5 text-xs font-bold text-[#596575]">
            Style
            <select v-model="viewerModal.style" class="h-[34px] rounded-md border border-[#c7d0dc] bg-white text-[#17202a]">
              <option value="cartoon">Cartoon</option>
              <option value="stick">Stick</option>
              <option value="surface">Surface</option>
            </select>
          </label>
          <label v-if="viewerModal.mode === 'atom' || viewerModal.mode === 'residue' || viewerModal.mode === 'chain'" class="grid min-w-[180px] gap-1.5 text-xs font-bold text-[#596575]">
            Selection
            <input
              class="h-[34px] rounded-md border border-[#c7d0dc] bg-white text-[#17202a]"
              :value="selectorValue()"
              spellcheck="false"
              @input="setSelectorValue(($event.target as HTMLInputElement).value)"
            />
          </label>
          <div v-if="canBulkSelectAtoms" class="grid grid-cols-[repeat(2,max-content)] gap-1.5 self-end">
            <button type="button" class="h-8 cursor-pointer rounded-md border border-[#c6d0dc] bg-white px-3 font-bold text-[#17202a]" @click="selectAllAtomsInViewer">Select all</button>
            <button type="button" class="h-8 cursor-pointer rounded-md border border-[#c6d0dc] bg-white px-3 font-bold text-[#17202a]" @click="clearSelectorSelection">Clear all</button>
          </div>
          <label v-if="viewerModal.mode === 'proteinAtom'" class="grid min-w-[180px] gap-1.5 text-xs font-bold text-[#596575]">
            Selection
            <textarea
              class="min-h-[76px] resize-y rounded-md border border-[#c7d0dc] bg-white px-2 py-1.5 font-mono text-xs text-[#17202a]"
              :value="selectorValue()"
              spellcheck="false"
              @input="setSelectorValue(($event.target as HTMLTextAreaElement).value)"
            />
          </label>
          <div v-if="pendingRunInput?.fields.includes('metric')" class="grid min-w-[180px] gap-1.5">
            <label class="grid min-w-[180px] gap-1.5 text-xs font-bold text-[#596575]">
              Score
              <select class="h-[34px] rounded-md border border-[#c7d0dc] bg-white text-[#17202a]" :value="runtimeChoiceValue('metric')" @change="setRuntimeChoiceValue('metric', ($event.target as HTMLSelectElement).value)">
                <option v-for="choice in pendingRunInput.choices.metric ?? []" :key="choice" :value="choice">{{ choice }}</option>
              </select>
            </label>
            <button type="button" class="h-8 w-full cursor-pointer rounded-md border border-[#176f5d] bg-[#176f5d] px-4 font-bold text-white" @click="submitRuntimeInput">Submit</button>
          </div>
          <div v-if="isChiralityTargetMode()" class="flex max-w-[420px] flex-wrap items-center gap-1.5">
            <div v-for="target in parseChiralityTargets(selectorValue())" :key="target.atom" class="inline-flex items-center gap-1 rounded-md border border-[#d9b56d] bg-[#fff8e8] py-0.5 pr-1 pl-2 text-xs font-bold text-[#2d261a]">
              <span>{{ target.atom }}</span>
              <select class="h-[26px] w-[52px] rounded-md border border-[#c7d0dc] bg-white text-[#17202a]" :value="target.chirality" @change="setChiralityTarget(target.atom, ($event.target as HTMLSelectElement).value)">
                <option value="R">R</option>
                <option value="S">S</option>
              </select>
              <button type="button" class="size-6 cursor-pointer rounded-md border border-[#c6d0dc] bg-white font-bold text-[#17202a]" title="Remove target" @click="removeChiralityTarget(target.atom)">X</button>
            </div>
          </div>
          <button v-if="pendingRunInput && !pendingRunInput.fields.includes('metric')" type="button" class="h-8 cursor-pointer rounded-md border border-[#176f5d] bg-[#176f5d] px-4 font-bold text-white" @click="submitRuntimeInput">Submit</button>
          <button v-else-if="viewerModal.mode === 'residue'" type="button" class="h-8 cursor-pointer rounded-md border border-[#176f5d] bg-[#176f5d] px-4 font-bold text-white" @click="submitViewerSelection">Submit</button>
        </div>
        <div v-show="viewerModal.mode !== 'score'" ref="viewerEl" class="relative h-[520px] w-full rounded-lg border border-[#d5dde6] bg-white max-md:h-[380px]" />
        <p v-if="activeModalFile?.type === 'fasta'" class="mt-3 whitespace-pre-wrap rounded-lg bg-[#f4f7fa] p-3 text-[#26313f]">{{ activeModalFile.content || "No sequence content loaded." }}</p>
      </section>
    </div>
  </main>
</template>
