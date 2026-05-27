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
import {
  colorsByType,
  nodeSpecs,
  proteinExample,
  typeDetails,
  type FoundryNodeSpec,
  type OptionSpec,
  type PortSpec,
  type PortType,
} from "../utils/foundrySpecs";

interface UploadedStructure {
  name: string;
  type: "pdb" | "fasta" | "unknown";
  content: string;
}

interface ViewerModal {
  open: boolean;
  nodeId: string;
  title: string;
  mode: NonNullable<OptionSpec["viewerMode"]>;
  fileIndex: number;
  style: "cartoon" | "stick" | "surface";
}

interface PendingRunInput {
  runId: string;
  nodeId: string;
  nodeType: string;
  fields: string[];
  payloads: Record<string, any>;
  choices: Record<string, string[]>;
  sequence: number;
}

interface BackendArtifact {
  artifact_id: string;
  payload_type: string;
  media_type: string;
  path: string;
  byte_size: number;
  item_count: number;
  node_id?: string | null;
  node_type?: string | null;
}

interface BackendOutput {
  node_id: string;
  output_key: string;
  type_name: string;
  item_count: number;
  artifact_ids: string[];
  paths: string[];
}

interface RunStatus {
  run_id: string;
  state: string;
  current_node_id?: string | null;
  current_node_type?: string | null;
  completed_nodes: number;
  total_nodes: number;
  progress_percent: number;
  recent_output: string[];
  warnings: Array<Record<string, any>>;
  errors: Array<Record<string, any>>;
  pending_inputs?: RunEventPayload[];
}

interface RunEventPayload {
  event: string;
  run_id: string;
  sequence?: number;
  node_id?: string | null;
  node_type?: string | null;
  message?: string | null;
  data?: Record<string, any>;
}

interface SessionRecord {
  session_id: string;
  created_at: string;
  updated_at: string;
  latest_run_id?: string | null;
  document?: Record<string, any> | null;
}

interface WorkflowPreset {
  label: string;
  file: string;
}

const baklava = useBaklava();
baklava.settings.enableMinimap = true;
baklava.settings.displayValueOnHover = true;
baklava.settings.nodes.defaultWidth = 278;
baklava.settings.palette.enabled = false;

const registeredConstructors = new Map<string, ReturnType<typeof defineNode>>();
const typeRegistry = new Map<PortType, NodeInterfaceType<any>>();
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
const logsEl = ref<HTMLElement | null>(null);
const workflowFileInput = ref<HTMLInputElement | null>(null);
const viewerRuntimeFiles = ref<UploadedStructure[]>([]);
const pendingRunInput = ref<PendingRunInput | null>(null);
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
    apiStatus.value = "available";
    apiMessage.value = "API available";
    await ensureSession();
  } catch (error) {
    apiStatus.value = "unavailable";
    apiMessage.value = error instanceof Error ? error.message : "API unavailable";
  }
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
        h("label", { class: "node-file-upload" }, [
              h("span", (props.intf as NodeInterfaceTypeBase).name),
              h("input", {
                type: "file",
                multiple: true,
                accept: (props.intf as any).accept,
                onChange,
              }),
              status.value ? h("small", status.value) : null,
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
                class: "node-viewer-button",
                type: "button",
                title: (props.intf as NodeInterfaceTypeBase).name,
                onClick: open,
              },
              [(props.intf as NodeInterfaceTypeBase).name],
            );
    },
  }),
);

function detectStructureType(fileName: string): UploadedStructure["type"] {
  const lower = fileName.toLowerCase();
  if (lower.endsWith(".pdb")) return "pdb";
  if (lower.endsWith(".fasta") || lower.endsWith(".fa")) return "fasta";
  return "unknown";
}

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
  const interfaceTypes = new BaklavaInterfaceTypes(baklava.editor, { viewPlugin: baklava });
  typeDetails.forEach(({ name }) => {
    typeRegistry.set(name, new NodeInterfaceType(name));
  });

  typeRegistry.get("Protein")?.addConversion(typeRegistry.get("Batch Protein")!, (value) => value);
  typeRegistry.get("Ligand")?.addConversion(typeRegistry.get("Batch Ligand")!, (value) => value);
  typeRegistry.get("Batch Protein with Ligand")?.addConversion(typeRegistry.get("Batch Protein (With Ligand)")!, (value) => value);
  typeRegistry.get("Batch Protein (With Ligand)")?.addConversion(typeRegistry.get("Batch Protein with Ligand")!, (value) => value);
  typeRegistry.get("Batch Protein with Ligand")?.addConversion(typeRegistry.get("Batch Protein")!, (value) => value);
  typeRegistry.get("Batch Protein (With Ligand)")?.addConversion(typeRegistry.get("Batch Protein")!, (value) => value);
  typeRegistry.get("Batch Protein")?.addConversion(typeRegistry.get("Batch Protein (With Ligand)")!, (value) => value);
  typeRegistry.get("Batch Ligand")?.addConversion(typeRegistry.get("Ligand")!, (value) => value);
  typeRegistry.get("Batch Protein")?.addConversion(typeRegistry.get("Protein")!, (value) => value);
  typeRegistry.get("Batch Protein with Ligand")?.addConversion(typeRegistry.get("Protein")!, (value) => value);
  typeRegistry.get("Batch Protein (With Ligand)")?.addConversion(typeRegistry.get("Protein")!, (value) => value);
  typeRegistry.get("Ligand")?.addConversion(typeRegistry.get("Batch Protein (With Ligand)")!, (value) => value);
  typeRegistry.get("Batch Ligand")?.addConversion(typeRegistry.get("Batch Protein (With Ligand)")!, (value) => value);
  typeRegistry.get("Protein")?.addConversion(typeRegistry.get("Batch Protein (With Ligand)")!, (value) => value);

  interfaceTypes.addTypes(...typeRegistry.values());
}

function registerNodes() {
  nodeSpecs.forEach((spec) => {
    const nodeConstructor = createFoundryNode(spec);
    registeredConstructors.set(spec.type, nodeConstructor);
    baklava.editor.registerNodeType(nodeConstructor, { category: spec.category, title: spec.title });
  });
}

function portColor(typeName: string | undefined) {
  return typeName ? colorsByType[typeName as PortType] ?? "#6d7681" : "#6d7681";
}

function primaryNodeColor(node: AbstractNode) {
  const output = Object.values(node.outputs).find((intf) => getType(intf));
  const input = Object.values(node.inputs).find((intf) => getType(intf));
  return portColor(output || input ? getType((output ?? input)!) : undefined);
}

function nodeRequiresRuntimeInput(node: AbstractNode) {
  return Boolean(specForNode(node)?.requiresRuntimeInput);
}

function connectionColor(connection: Connection) {
  return portColor(getType(connection.from));
}

function nodeByModal() {
  return baklava.editor.graph.findNodeById(viewerModal.nodeId);
}

function selectorInterface(node = nodeByModal()) {
  if (!node) return undefined;
  if (pendingRunInput.value?.fields.includes("chiralityTargets")) return node.inputs.chiralityTargets as NodeInterfaceTypeBase<string> | undefined;
  if (pendingRunInput.value?.fields.includes("proteinAtoms") || viewerModal.mode === "proteinAtom") return node.inputs.proteinAtoms as NodeInterfaceTypeBase<string> | undefined;
  if (pendingRunInput.value?.fields.includes("chains") || viewerModal.mode === "chain") return node.inputs.chains as NodeInterfaceTypeBase<string> | undefined;
  if (viewerModal.mode === "atom") return node.inputs.atoms as NodeInterfaceTypeBase<string> | undefined;
  if (viewerModal.mode === "residue") return node.inputs.residues as NodeInterfaceTypeBase<string> | undefined;
  return undefined;
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

function parseSelectorList(value = selectorValue()) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function atomId(atom: any) {
  return String(atom.atom || atom.name || `${atom.elem ?? "Atom"}${atom.serial ?? (typeof atom.index === "number" ? atom.index + 1 : "")}`);
}

function residueId(atom: any) {
  const resn = String(atom.resn || atom.residue || "").trim();
  if (resn && !STANDARD_RESIDUES.has(resn.toUpperCase())) return resn;
  const chain = atom.chain || "";
  const resi = atom.resi ?? atom.residueIndex ?? "";
  return `${chain}${resi}`;
}

const STANDARD_RESIDUES = new Set([
  "ALA",
  "ARG",
  "ASN",
  "ASP",
  "CYS",
  "GLN",
  "GLU",
  "GLY",
  "HIS",
  "ILE",
  "LEU",
  "LYS",
  "MET",
  "PHE",
  "PRO",
  "SER",
  "THR",
  "TRP",
  "TYR",
  "VAL",
]);

function residueSelection(residue: string) {
  if (/^[A-Za-z]\d+$/.test(residue)) {
    return { chain: residue[0], resi: Number(residue.slice(1)) };
  }
  return { resn: residue };
}

function parseProteinAtomMap(value = selectorValue()): Record<string, string[]> {
  const text = value.trim();
  if (!text) return {};
  try {
    const data = JSON.parse(text);
    if (data && typeof data === "object" && !Array.isArray(data)) {
      return Object.fromEntries(
        Object.entries(data)
          .map(([residue, atoms]) => [
            residue.trim(),
            Array.isArray(atoms)
              ? atoms.map((atom) => String(atom).trim()).filter(Boolean)
              : String(atoms ?? "")
                  .split(",")
                  .map((atom) => atom.trim())
                  .filter(Boolean),
          ])
          .filter(([residue, atoms]) => residue && (atoms as string[]).length),
      );
    }
  } catch {
    // Fall through to "A56:CG,OH; A115:CG" parsing.
  }
  const parsed: Record<string, string[]> = {};
  text
    .replace(/\n/g, ";")
    .split(";")
    .map((entry) => entry.trim())
    .filter(Boolean)
    .forEach((entry) => {
      const [residue, atoms] = entry.split(":", 2);
      const atomNames = String(atoms ?? "")
        .split(",")
        .map((atom) => atom.trim())
        .filter(Boolean);
      if (residue?.trim() && atomNames.length) parsed[residue.trim()] = atomNames;
    });
  return parsed;
}

function formatProteinAtomMap(value: Record<string, string[]>) {
  const compact = Object.fromEntries(Object.entries(value).filter(([, atoms]) => atoms.length).map(([residue, atoms]) => [residue, [...new Set(atoms)].join(",")]));
  return JSON.stringify(compact, null, 2);
}

function toggleSelectorItem(value: string) {
  if (pendingRunInput.value?.fields.includes("chiralityTargets")) {
    const targets = parseChiralityTargets();
    const existing = targets.find((target) => target.atom === value);
    const next = existing ? targets.filter((target) => target.atom !== value) : [...targets, { atom: value, chirality: "R" }];
    setSelectorValue(formatChiralityTargets(next));
    return;
  }
  const values = parseSelectorList();
  const next = values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
  setSelectorValue(next.join(","));
}

function toggleProteinAtom(atom: any) {
  const residue = residueId(atom);
  const name = atomId(atom);
  if (!residue || !name) return;
  const selected = parseProteinAtomMap();
  const atoms = selected[residue] ?? [];
  selected[residue] = atoms.includes(name) ? atoms.filter((atomName) => atomName !== name) : [...atoms, name];
  if (!selected[residue].length) delete selected[residue];
  setSelectorValue(formatProteinAtomMap(selected));
}

function parseChiralityTargets(value = selectorValue()) {
  return value
    .split(/[,;\n]+/)
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => {
      const [atom, chirality] = entry.split(/[:=\s]+/);
      return { atom: atom ?? "", chirality: (chirality ?? "R").toUpperCase() === "S" ? "S" : "R" };
    })
    .filter((target) => target.atom);
}

function formatChiralityTargets(targets: Array<{ atom: string; chirality: string }>) {
  return targets.map((target) => `${target.atom}:${target.chirality === "S" ? "S" : "R"}`).join(", ");
}

function setChiralityTarget(atom: string, chirality: string) {
  setSelectorValue(formatChiralityTargets(parseChiralityTargets().map((target) => (target.atom === atom ? { ...target, chirality } : target))));
}

function removeChiralityTarget(atom: string) {
  setSelectorValue(formatChiralityTargets(parseChiralityTargets().filter((target) => target.atom !== atom)));
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
  return nodeSpecs.find((spec) => spec.type === node.type);
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
    void refreshRunStatus(event.run_id);
    void refreshRunFiles(event.run_id);
    closeRunEvents();
  } else if (event.event === "completed") {
    runState.value = "completed";
    runMessage.value = "Run completed";
    clearPendingInputs();
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

function readBackendMessage(payload: any, fallback: string) {
  if (typeof payload?.detail === "string") return payload.detail;
  if (payload?.detail?.message) return payload.detail.message;
  if (payload?.message) return payload.message;
  return fallback || "Backend request failed";
}

function artifactUrl(artifact: BackendArtifact) {
  return apiUrl(`/api/artifacts/${artifact.artifact_id}`);
}

function archiveUrl() {
  return currentRunId.value ? apiUrl(`/api/runs/${currentRunId.value}/archive`) : "#";
}

function onLogsScroll() {
  const el = logsEl.value;
  if (!el) return;
  logsFollowBottom.value = el.scrollTop + el.clientHeight >= el.scrollHeight - 8;
}

function scrollLogsToBottom() {
  const el = logsEl.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
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
  viewerModal.open = true;
  viewerModal.nodeId = event.node_id;
  viewerModal.title = node?.title ?? event.node_type;
  setNodePendingInput(event.node_id, true);
  viewerModal.mode =
    event.node_type === "ResidueSelector"
      ? "residue"
      : event.node_type === "ProteinAtomSelector" || event.node_type === "ResidueAtomSelector"
        ? "proteinAtom"
        : event.node_type === "ProteinChainSelector" || event.node_type === "ChainFilter"
          ? "chain"
          : event.node_type === "FilterByScore"
            ? "score"
            : "atom";
  viewerModal.fileIndex = 0;
  viewerRuntimeFiles.value = await runtimeFilesFromPayloads(pendingRunInput.value.payloads);
  void nextTick(initializeViewer);
}

function closeViewer() {
  viewerModal.open = false;
  viewerZoomKey = "";
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
  if (!node || !["PDBViewer", "AtomSelector", "ResidueSelector", "ProteinAtomSelector", "ResidueAtomSelector", "ProteinChainSelector", "ChainFilter", "FilterAtomsChirality"].includes(String(node.type))) return;
  if (String(node.type) === "FilterAtomsChirality" && runtimeInputPayloads[nodeId]) {
    viewerRuntimeFiles.value = await runtimeFilesFromPayloads(runtimeInputPayloads[nodeId]);
    return;
  }
  const output = String(node.type) === "ChainFilter" || String(node.type) === "PDBViewer"
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
    if (artifact && artifact.media_type !== "chemical/x-pdb") continue;
    const response = await fetch(artifact ? artifactUrl(artifact) : apiUrl(`/api/artifacts/${artifactId}`));
    if (!response.ok) continue;
    const path = artifact?.path ?? paths[index] ?? artifactId;
    files.push({ name: path.split("/").pop() || path, type: "pdb", content: await response.text() });
  }
  return files;
}

function structuresForNodeId(nodeId: string, seen = new Set<string>()): UploadedStructure[] {
  if (viewerRuntimeFiles.value.length) return viewerRuntimeFiles.value;
  if (seen.has(nodeId)) return [];
  seen.add(nodeId);
  const node = baklava.editor.graph.findNodeById(nodeId);
  if (node && ["PDBViewer", "AtomSelector", "ResidueSelector", "ProteinAtomSelector", "ResidueAtomSelector", "ProteinChainSelector", "ChainFilter"].includes(String(node.type))) {
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
  renderViewer();
}

function renderViewer() {
  if (!viewer) return;
  if (!activeModalFile.value) {
    viewer.clear();
    viewer.render();
    return;
  }
  const file = activeModalFile.value;
  viewer.clear();
  if (file.type === "fasta") {
    viewer.render();
    return;
  }
  if (!file.content) {
    viewer.render();
    return;
  }
  const model = viewer.addModel(file.content, "pdb");
  if (!model) {
    viewer.render();
    return;
  }
  if (viewerModal.style === "stick" || viewerModal.mode === "atom" || viewerModal.mode === "proteinAtom" || viewerModal.mode === "chain") {
    viewer.setStyle({ hetflag: false }, { stick: { radius: 0.18 } });
    viewer.setStyle({ hetflag: true }, { stick: { colorscheme: "greenCarbon", radius: 0.22 } });
  } else if (viewerModal.style === "surface") {
    viewer.setStyle({ hetflag: false }, { cartoon: { color: "lightgray" } });
    viewer.addSurface((globalThis as any).$3Dmol?.SurfaceType?.VDW ?? 1, { opacity: 0.6, color: "white" }, { hetflag: false });
    viewer.setStyle({ hetflag: true }, { stick: { colorscheme: "greenCarbon", radius: 0.24 } });
  } else {
    viewer.setStyle({ hetflag: false }, { cartoon: { color: "spectrum" } });
    viewer.setStyle({ hetflag: true }, { stick: { colorscheme: "greenCarbon", radius: 0.22 } });
  }
  const selected = new Set(pendingRunInput.value?.fields.includes("chiralityTargets") ? parseChiralityTargets().map((target) => target.atom) : parseSelectorList());
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
    const proteinAtoms = parseProteinAtomMap();
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
  const zoomKey = `${viewerModal.nodeId}:${viewerModal.fileIndex}:${file.name}`;
  if (zoomKey !== viewerZoomKey) {
    try {
      viewer.zoomTo();
    } catch {
      viewerZoomKey = "";
      viewer.render();
      return;
    }
    viewerZoomKey = zoomKey;
  }
  viewer.render();
}

watch([() => viewerModal.fileIndex, () => viewerModal.style, () => viewerModal.open], () => {
  void nextTick(renderViewer);
});

watch(runLogs, () => {
  if (logsFollowBottom.value) void nextTick(scrollLogsToBottom);
}, { deep: true });

registerTypes();
registerNodes();

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
  const route = useRoute();
  if (!route.query.session) {
    void ensureDefaultWorkflowLoaded();
  }
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
  <main class="workbench-shell">
    <header class="topbar">
      <div>
        <h1>FoundryUI</h1>
      </div>
      <nav class="topbar-actions" aria-label="Workflow actions">
        <label class="api-base">
          API
          <input v-model="apiBase" placeholder="http://127.0.0.1:3000/api" spellcheck="false" @keyup.enter="connectApi" />
        </label>
        <button type="button" class="connect-button" :disabled="apiStatus === 'checking'" @click="connectApi">
          {{ apiStatus === "checking" ? "Checking" : "Connect" }}
        </button>
        <span class="api-feedback" :class="apiStatus">{{ apiMessage }}</span>
        <span v-if="currentSessionId" class="session-chip">{{ currentSessionId.slice(0, 18) }}</span>
        <NuxtLink class="doc-link" to="/sessions">Sessions</NuxtLink>
        <button type="button" class="icon-button" title="New session" @click="createNewSession">N</button>
        <button type="button" class="icon-button" title="Save workflow" @click="saveWorkflow">S</button>
        <div class="load-workflow-menu">
          <button type="button" class="icon-button" title="Load workflow file" @click="requestLoadWorkflow">L</button>
          <select v-model="selectedWorkflowPreset" title="Load workflow preset" @change="loadWorkflowPreset">
            <option value="">Presets</option>
            <option v-for="preset in workflowPresets" :key="preset.file" :value="preset.file">{{ preset.label }}</option>
          </select>
        </div>
        <button type="button" class="icon-button" title="Clear canvas" @click="clearWorkflow">C</button>
        <button v-if="isRunActive" type="button" class="stop-button" @click="stopRun">Stop</button>
        <button type="button" class="run-button" :disabled="isRunActive" @click="queueRun">Run</button>
        <input ref="workflowFileInput" class="workflow-file-input" type="file" accept=".fuiworkflow" @change="loadWorkflow" />
      </nav>
    </header>

    <section class="statusbar" aria-label="Run status">
      <span class="run-state" :class="{ error: runState === 'failed', stopped: runState === 'stopped' }">{{ runStateLabel }}</span>
      <span v-if="currentRunId">{{ currentRunId }}</span>
      <span v-if="runStatus">{{ runStatus.progress_percent }}%</span>
      <span>{{ runMessage }}</span>
    </section>

    <section class="canvas-panel" aria-label="Workflow canvas">
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

    <aside class="run-panel" aria-label="Backend run details">
      <section class="run-panel-section">
        <header>
          <h2>Status</h2>
          <a v-if="currentRunId && (runState === 'completed' || runState === 'failed')" class="archive-link" :class="{ error: runState === 'failed' }" :href="archiveUrl()" title="Download archive">
            <span class="download-icon" aria-hidden="true">⇩</span>
            {{ runState === "failed" ? "ERROR" : "Archive Download" }}
          </a>
          <span v-else-if="runState === 'stopped'" class="stopped-label">STOPPED</span>
        </header>
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: `${runStatus?.progress_percent ?? 0}%` }" />
        </div>
        <p v-if="runStatus">
          {{ runStatus.completed_nodes }} / {{ runStatus.total_nodes }}
          <span v-if="runStatus.current_node_type">Current: {{ runStatus.current_node_type }}</span>
        </p>
        <p v-else>{{ runMessage }}</p>
      </section>

      <section class="run-panel-section">
        <header>
          <h2>Issues</h2>
          <span>{{ validationErrors.length }}</span>
        </header>
        <ul v-if="validationErrors.length" class="issue-list">
          <li v-for="(error, index) in validationErrors" :key="`${error.code ?? 'error'}-${index}`">
            <strong>{{ error.code ?? "ERROR" }}</strong>
            <span>{{ error.node_type || error.node_id ? `${error.node_type ?? "node"} ${error.node_id ?? ""}` : "" }}</span>
            <p>{{ error.message ?? "Unknown error" }}</p>
          </li>
        </ul>
        <p v-else-if="!validationErrors.length">No issues</p>
      </section>

      <section class="run-panel-section">
        <header>
          <h2>Saves</h2>
          <span>{{ savedArtifacts.length }}</span>
        </header>
        <ul v-if="savedArtifacts.length" class="artifact-list">
          <li v-for="artifact in savedArtifacts" :key="artifact.artifact_id">
            <a :href="artifactUrl(artifact)">{{ artifact.path }}</a>
            <span>{{ artifact.payload_type }} · {{ artifact.item_count }}</span>
          </li>
        </ul>
        <p v-else>No saved results yet</p>
      </section>

      <section class="run-panel-section logs-section">
        <header>
          <h2>Logs</h2>
          <span>{{ runLogs.length }}</span>
        </header>
        <pre ref="logsEl" class="terminal-log" @scroll="onLogsScroll">{{ runLogs.length ? runLogs.join("\n") : "No command output yet" }}</pre>
      </section>
    </aside>

    <div v-if="viewerModal.open" class="modal-backdrop" @click.self="closeViewer">
      <section class="viewer-modal" aria-label="3D selector">
        <header class="viewer-modal-header">
          <div>
            <p>{{ viewerModal.mode }}</p>
            <h2>{{ viewerModal.title }}</h2>
          </div>
          <button type="button" class="icon-button" title="Close viewer" @click="closeViewer">X</button>
        </header>
        <div class="viewer-controls">
          <label v-if="viewerModal.mode !== 'score'">
            File
            <select v-model.number="viewerModal.fileIndex">
              <option v-for="(file, index) in modalFiles" :key="file.name + index" :value="index">{{ file.name }}</option>
            </select>
          </label>
          <label v-if="viewerModal.mode !== 'score'">
            Style
            <select v-model="viewerModal.style">
              <option value="cartoon">Cartoon</option>
              <option value="stick">Stick</option>
              <option value="surface">Surface</option>
            </select>
          </label>
          <label v-if="viewerModal.mode === 'atom' || viewerModal.mode === 'residue' || viewerModal.mode === 'chain'" class="selector-value">
            Selection
            <input
              :value="selectorValue()"
              spellcheck="false"
              @input="setSelectorValue(($event.target as HTMLInputElement).value)"
            />
          </label>
          <label v-if="viewerModal.mode === 'proteinAtom'" class="selector-value">
            Selection
            <textarea
              :value="selectorValue()"
              spellcheck="false"
              @input="setSelectorValue(($event.target as HTMLTextAreaElement).value)"
            />
          </label>
          <label v-if="pendingRunInput?.fields.includes('metric')" class="selector-value">
            Score
            <select :value="runtimeChoiceValue('metric')" @change="setRuntimeChoiceValue('metric', ($event.target as HTMLSelectElement).value)">
              <option v-for="choice in pendingRunInput.choices.metric ?? []" :key="choice" :value="choice">{{ choice }}</option>
            </select>
          </label>
          <div v-if="pendingRunInput?.fields.includes('chiralityTargets')" class="chirality-targets">
            <div v-for="target in parseChiralityTargets()" :key="target.atom" class="chirality-target">
              <span>{{ target.atom }}</span>
              <select :value="target.chirality" @change="setChiralityTarget(target.atom, ($event.target as HTMLSelectElement).value)">
                <option value="R">R</option>
                <option value="S">S</option>
              </select>
              <button type="button" class="icon-button" title="Remove target" @click="removeChiralityTarget(target.atom)">X</button>
            </div>
          </div>
          <button v-if="pendingRunInput" type="button" class="run-button" @click="submitRuntimeInput">Submit</button>
          <button v-else-if="viewerModal.mode === 'residue'" type="button" class="run-button" @click="submitViewerSelection">Submit</button>
        </div>
        <div v-show="viewerModal.mode !== 'score'" ref="viewerEl" class="viewer-surface" />
        <p v-if="activeModalFile?.type === 'fasta'" class="sequence-preview">{{ activeModalFile.content || "No sequence content loaded." }}</p>
      </section>
    </div>
  </main>
</template>

<style>
.workbench-shell {
  min-height: 100vh;
  display: grid;
  grid-template-rows: 58px 36px minmax(0, 1fr) 190px;
  background: #171d25;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #ccd4dd;
  background: #fbfcfd;
  padding: 0 16px;
}

.topbar h1,
.topbar p,
.viewer-modal h2,
.viewer-modal p {
  margin: 0;
}

.topbar h1 {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0;
}

.topbar p {
  margin-top: 2px;
  color: #566271;
  font-size: 12px;
}

.topbar-actions,
.statusbar,
.viewer-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.api-base {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #566271;
  font-size: 12px;
  font-weight: 700;
}

.api-base input {
  width: 190px;
  height: 32px;
  border: 1px solid #c6d0dc;
  border-radius: 6px;
  background: #ffffff;
  color: #17202a;
  padding: 0 8px;
}

.load-workflow-menu {
  display: inline-flex;
  align-items: center;
  height: 32px;
}

.load-workflow-menu .icon-button {
  border-radius: 6px 0 0 6px;
}

.load-workflow-menu select {
  width: 92px;
  height: 32px;
  border: 1px solid #c6d0dc;
  border-left: 0;
  border-radius: 0 6px 6px 0;
  background: #ffffff;
  color: #17202a;
  font-size: 12px;
  font-weight: 700;
}

.doc-link,
.icon-button,
.run-button,
.stop-button,
.connect-button {
  border: 1px solid #c6d0dc;
  background: #ffffff;
  color: #17202a;
  cursor: pointer;
  text-decoration: none;
}

.connect-button {
  height: 32px;
  padding: 0 12px;
  border-radius: 6px;
  font-weight: 700;
}

.connect-button:disabled {
  cursor: progress;
  opacity: 0.65;
}

.api-feedback {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #667386;
  font-size: 12px;
  font-weight: 700;
}

.api-feedback.available {
  color: #176f5d;
}

.api-feedback.unavailable {
  color: #b33939;
}

.session-chip {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #566271;
  font-size: 12px;
  font-weight: 700;
}

.doc-link {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 12px;
  border-radius: 6px;
  font-weight: 700;
}

.icon-button {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  font-weight: 700;
}

.run-button {
  height: 32px;
  padding: 0 16px;
  border-radius: 6px;
  background: #176f5d;
  border-color: #176f5d;
  color: #ffffff;
  font-weight: 700;
}

.stop-button {
  height: 32px;
  padding: 0 14px;
  border-radius: 6px;
  background: #a8343d;
  border-color: #a8343d;
  color: #ffffff;
  font-weight: 700;
}

.run-button:disabled {
  opacity: 0.62;
  cursor: wait;
}

.workflow-file-input {
  display: none;
}

.statusbar {
  overflow-x: auto;
  padding: 0 14px;
  border-bottom: 1px solid #2a3440;
  background: #202935;
  color: #aeb8c5;
  font-size: 12px;
}

.statusbar span {
  white-space: nowrap;
}

.run-state {
  padding: 4px 8px;
  border-radius: 5px;
  background: #12372f;
  color: #7ee0c4;
  font-weight: 700;
}

.run-state.error {
  background: #4a1d22;
  color: #ff9c9c;
}

.run-state.stopped {
  background: #3b3340;
  color: #d8b6ff;
}

.canvas-panel {
  min-width: 0;
  min-height: 0;
  position: relative;
}

.run-panel {
  display: grid;
  grid-template-columns: minmax(170px, 0.8fr) minmax(210px, 1fr) minmax(250px, 1.2fr) minmax(280px, 1.6fr);
  gap: 1px;
  border-top: 1px solid #2a3440;
  background: #2a3440;
  color: #d8e1ec;
  min-height: 0;
}

.run-panel-section {
  min-width: 0;
  min-height: 0;
  overflow: auto;
  background: #151c25;
  padding: 10px 12px;
}

.run-panel-section header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.run-panel-section h2,
.run-panel-section p {
  margin: 0;
}

.run-panel-section h2 {
  font-size: 12px;
  letter-spacing: 0;
  text-transform: uppercase;
  color: #91a0b2;
}

.run-panel-section p,
.run-panel-section li,
.run-panel-section pre {
  font-size: 12px;
}

.progress-track {
  width: 100%;
  height: 8px;
  overflow: hidden;
  border-radius: 4px;
  background: #2b3542;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  min-width: 0;
  background: #2ca58d;
  transition: width 180ms ease;
}

.archive-link,
.artifact-list a {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #7ee0c4;
  text-decoration: none;
}

.archive-link.error {
  color: #ff9c9c;
}

.download-icon {
  display: inline-grid;
  place-items: center;
  width: 18px;
  height: 18px;
  border: 1px solid currentColor;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1;
}

.error-label {
  color: #ff9c9c;
  font-size: 12px;
  font-weight: 800;
}

.stopped-label {
  color: #d8b6ff;
  font-size: 12px;
  font-weight: 800;
}

.issue-list,
.artifact-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.issue-list li,
.artifact-list li {
  display: grid;
  gap: 3px;
}

.issue-list strong {
  color: #ffb86b;
}

.issue-list span,
.artifact-list span {
  color: #91a0b2;
  font-size: 11px;
}

.terminal-log {
  min-height: 120px;
  max-height: 150px;
  overflow: auto;
  margin: 0;
  padding: 10px 12px;
  border: 1px solid #273342;
  border-radius: 6px;
  background: #05080d;
  white-space: pre-wrap;
  color: #8ef0bd;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  line-height: 1.45;
  box-shadow: inset 0 0 0 1px rgba(126, 224, 196, 0.05);
}

.canvas-panel > div,
.canvas-panel .baklava-editor {
  width: 100%;
  height: 100%;
}

.baklava-node-palette {
  display: none !important;
}

.baklava-context-menu {
  width: max-content !important;
  min-width: 220px;
  max-width: none !important;
  max-height: none !important;
  overflow: visible !important;
  border: 1px solid rgba(190, 207, 226, 0.24);
  border-radius: 8px !important;
}

.baklava-context-menu > .item {
  min-height: 30px;
  border-left: 4px solid #6d7681;
  white-space: nowrap;
}

.baklava-context-menu > .item > .__label {
  white-space: nowrap;
}

.baklava-context-menu > .item:nth-of-type(6n + 1) {
  border-left-color: #249a86;
}

.baklava-context-menu > .item:nth-of-type(6n + 2) {
  border-left-color: #c74b67;
}

.baklava-context-menu > .item:nth-of-type(6n + 3) {
  border-left-color: #7d8b23;
}

.baklava-context-menu > .item:nth-of-type(6n + 4) {
  border-left-color: #9062ce;
}

.baklava-context-menu > .item:nth-of-type(6n + 5) {
  border-left-color: #d28a19;
}

.baklava-context-menu > .item:nth-of-type(6n) {
  border-left-color: #e2559b;
}

@media (max-height: 760px), (max-width: 900px) {
  .baklava-context-menu:not(.--nested) {
    min-width: min(560px, calc(100vw - 32px));
    column-count: 2;
    column-gap: 0;
    column-fill: balance;
  }

  .baklava-context-menu:not(.--nested) > .item,
  .baklava-context-menu:not(.--nested) > .divider {
    break-inside: avoid;
  }
}

.baklava-node {
  border-top: 3px solid var(--foundry-node-color, #6d7681);
}

.baklava-node-interface .__port {
  background: var(--foundry-port-color, #6d7681) !important;
  border-color: color-mix(in srgb, var(--foundry-port-color, #6d7681), white 30%) !important;
}

.typed-connection .baklava-connection {
  stroke: var(--connection-color, #6d7681) !important;
}

.baklava-node.foundry-node-error {
  border-top-color: #ff5252 !important;
  box-shadow: 0 0 0 2px rgba(255, 82, 82, 0.75);
}

.baklava-node.foundry-node-cached {
  box-shadow: 0 0 0 2px rgba(126, 224, 196, 0.72);
}

.baklava-node.foundry-node-manual {
  border-style: dashed;
  box-shadow: inset 0 0 0 1px rgba(255, 184, 107, 0.55);
}

.baklava-node.foundry-node-manual::after {
  content: "manual";
  position: absolute;
  top: 4px;
  right: 34px;
  z-index: 1;
  color: #ffb86b;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.baklava-node.foundry-node-pending-input {
  animation: foundryPendingInput 0.9s ease-in-out infinite;
  border-top-color: #ffb86b !important;
}

.baklava-node.foundry-node-pending-input::after {
  content: "input";
  color: #ffd29a;
}

@keyframes foundryPendingInput {
  0%,
  100% {
    box-shadow: inset 0 0 0 1px rgba(255, 184, 107, 0.55), 0 0 0 1px rgba(255, 184, 107, 0.2);
  }

  50% {
    box-shadow: inset 0 0 0 1px rgba(255, 184, 107, 0.9), 0 0 0 4px rgba(255, 184, 107, 0.38), 0 0 18px rgba(255, 184, 107, 0.45);
  }
}

.node-file-upload {
  display: grid;
  gap: 5px;
  padding: 8px;
}

.node-file-upload.--hidden {
  color: #8f9aaa;
  font-size: 12px;
}

.node-file-upload span {
  color: #d7dee8;
  font-size: 12px;
}

.node-text-control {
  display: grid;
  gap: 5px;
  padding: 8px;
}

.node-text-control span {
  color: #d7dee8;
  font-size: 12px;
}

.node-text-control input {
  width: 100%;
  height: 30px;
  border: 1px solid #536176;
  border-radius: 5px;
  background: #17202a;
  color: #eef4fb;
  padding: 0 7px;
}

.node-file-upload input {
  width: 100%;
  color: #d7dee8;
  font-size: 12px;
}

.node-file-upload small {
  color: #7ee0c4;
}

.node-viewer-button {
  width: calc(100% - 16px);
  min-height: 30px;
  margin: 6px 8px;
  border: 1px solid #64758b;
  border-radius: 6px;
  background: #273242;
  color: #eef4fb;
  cursor: pointer;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 22, 31, 0.62);
}

.viewer-modal {
  width: min(920px, 100%);
  max-height: min(760px, calc(100vh - 48px));
  overflow: auto;
  border: 1px solid #cfd8e3;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 22px 70px rgba(0, 0, 0, 0.25);
  padding: 14px;
}

.viewer-modal-header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 16px;
}

.viewer-modal-header p {
  color: #176f5d;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.viewer-modal-header h2 {
  font-size: 20px;
  letter-spacing: 0;
}

.viewer-controls {
  margin: 12px 0;
}

.viewer-controls label {
  display: grid;
  gap: 5px;
  min-width: 180px;
  color: #596575;
  font-size: 12px;
  font-weight: 700;
}

.viewer-controls select,
.viewer-controls input,
.viewer-controls textarea {
  height: 34px;
  border: 1px solid #c7d0dc;
  border-radius: 6px;
  background: #ffffff;
  color: #17202a;
}

.viewer-controls textarea {
  min-height: 76px;
  resize: vertical;
  padding: 7px 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

.chirality-targets {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  max-width: 420px;
}

.chirality-target {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 4px 3px 8px;
  border: 1px solid #d9b56d;
  border-radius: 6px;
  background: #fff8e8;
  color: #2d261a;
  font-size: 12px;
  font-weight: 700;
}

.chirality-target select {
  width: 52px;
  height: 26px;
}

.chirality-target .icon-button {
  width: 24px;
  height: 24px;
}

.viewer-surface {
  width: 100%;
  height: 520px;
  border: 1px solid #d5dde6;
  border-radius: 7px;
  background: #ffffff;
  position: relative;
}

.sequence-preview {
  white-space: pre-wrap;
  margin-top: 12px;
  padding: 12px;
  border-radius: 7px;
  background: #f4f7fa;
  color: #26313f;
}

@media (max-width: 760px) {
  .workbench-shell {
    grid-template-rows: auto 44px minmax(520px, 1fr) 360px;
  }

  .topbar {
    align-items: start;
    gap: 10px;
    padding: 10px 12px;
    flex-direction: column;
  }

  .viewer-controls {
    display: grid;
  }

  .topbar-actions,
  .run-panel {
    width: 100%;
  }

  .topbar-actions {
    flex-wrap: wrap;
  }

  .api-base {
    flex: 1 1 220px;
  }

  .api-base input {
    width: 100%;
  }

  .run-panel {
    grid-template-columns: 1fr;
  }

  .viewer-surface {
    height: 380px;
  }
}
</style>
