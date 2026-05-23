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
  getDomElements,
  getPortCoordinates,
  setNodePosition,
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
  type: "pdb" | "sdf" | "fasta" | "unknown";
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
}

interface RunEventPayload {
  event: string;
  run_id: string;
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

const baklava = useBaklava();
baklava.settings.enableMinimap = true;
baklava.settings.displayValueOnHover = true;
baklava.settings.nodes.defaultWidth = 278;

const registeredConstructors = new Map<string, ReturnType<typeof defineNode>>();
const typeRegistry = new Map<PortType, NodeInterfaceType<any>>();
const uploadedByNode = reactive<Record<string, UploadedStructure[]>>({});
const apiBase = ref("http://127.0.0.1:8000");
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
const errorNodeIds = ref(new Set<string>());
const eventSource = ref<EventSource | null>(null);
const runStateLabel = computed(() => (runState.value === "failed" ? "ERROR" : runState.value.toUpperCase()));
const isRunActive = computed(() => runState.value === "validating" || runState.value === "queued" || runState.value === "running");
const viewerEl = ref<HTMLElement | null>(null);
const workflowFileInput = ref<HTMLInputElement | null>(null);
const viewerModal = reactive<ViewerModal>({
  open: false,
  nodeId: "",
  title: "",
  mode: "structure",
  fileIndex: 0,
  style: "cartoon",
});
const runSteps = reactive([
  { label: "Validate typed graph", done: false },
  { label: "Package Ryvencore workflow", done: false },
  { label: "Queue Foundry task", done: false },
  { label: "Stream model and score results", done: false },
]);
let viewer: any;

const SmilesTextControl = markRaw(
  defineComponent({
    name: "SmilesTextControl",
    props: {
      intf: { type: Object, required: true },
      node: { type: Object, required: true },
    },
    setup(props) {
      const sourceValue = computed(() => String((props.node as any).inputs?.source?.value ?? ""));
      const value = computed({
        get: () => String((props.intf as NodeInterfaceTypeBase<string>).value ?? ""),
        set: (next) => {
          (props.intf as NodeInterfaceTypeBase<string>).value = next;
        },
      });

      return () =>
        sourceValue.value === "SMILES"
          ? h("label", { class: "node-text-control" }, [
              h("span", (props.intf as NodeInterfaceTypeBase).name),
              h("input", {
                value: value.value,
                spellcheck: "false",
                onInput: (event: Event) => {
                  value.value = (event.target as HTMLInputElement).value;
                },
              }),
            ])
          : null;
    },
  }),
);

const FileUploadControl = markRaw(
  defineComponent({
    name: "FileUploadControl",
    props: {
      intf: { type: Object, required: true },
      node: { type: Object, required: true },
    },
    setup(props) {
      const status = ref("");
      const sourceValue = computed(() => String((props.node as any).inputs?.source?.value ?? ""));
      const shouldShow = computed(() => {
        const nodeType = (props.node as AbstractNode).type;
        return nodeType !== "LigandInput" || sourceValue.value === "PDB" || sourceValue.value === "SDF";
      });

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
        shouldShow.value
          ? h("label", { class: "node-file-upload" }, [
              h("span", (props.intf as NodeInterfaceTypeBase).name),
              h("input", {
                type: "file",
                multiple: true,
                accept: (props.intf as any).accept,
                onChange,
              }),
              status.value ? h("small", status.value) : null,
            ])
          : null;
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
      const sourceValue = computed(() => String((props.node as any).inputs?.source?.value ?? ""));
      const shouldShow = computed(() => {
        const nodeType = (props.node as AbstractNode).type;
        return nodeType !== "LigandInput" || sourceValue.value === "PDB" || sourceValue.value === "SDF";
      });

      return () =>
        shouldShow.value
          ? h(
              "button",
              {
                class: "node-viewer-button",
                type: "button",
                title: (props.intf as NodeInterfaceTypeBase).name,
                onClick: open,
              },
              [(props.intf as NodeInterfaceTypeBase).name],
            )
          : null;
    },
  }),
);

function detectStructureType(fileName: string): UploadedStructure["type"] {
  const lower = fileName.toLowerCase();
  if (lower.endsWith(".pdb")) return "pdb";
  if (lower.endsWith(".sdf")) return "sdf";
  if (lower.endsWith(".fasta") || lower.endsWith(".fa")) return "fasta";
  return "unknown";
}

function createPortInterface(port: PortSpec) {
  const intf = new NodeInterface(port.optional ? `${port.label}*` : port.label, null);
  intf.setPort(true);
  applyPortType(intf, port.type);
  return intf;
}

function createOptionInterface(option: OptionSpec) {
  let intf: NodeInterface<any>;
  if (option.kind === "textarea") {
    intf = new TextareaInputInterface(option.label, String(option.value));
  } else if (option.kind === "text") {
    intf =
      option.key === "smiles"
        ? new NodeInterface(option.label, String(option.value)).setComponent(SmilesTextControl)
        : new TextInputInterface(option.label, String(option.value));
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

function applyPortType(intf: NodeInterface<any>, type: PortType) {
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
      ...(spec.inputs ?? []).map((input) => [input.key, () => createPortInterface(input)]),
      ...(spec.options ?? []).map((option) => [option.key, () => createOptionInterface(option)]),
    ]),
    outputs: Object.fromEntries((spec.outputs ?? []).map((output) => [output.key, () => createPortInterface(output)])),
  });
}

function registerTypes() {
  const interfaceTypes = new BaklavaInterfaceTypes(baklava.editor, { viewPlugin: baklava });
  typeDetails.forEach(({ name }) => {
    typeRegistry.set(name, new NodeInterfaceType(name));
  });
  typeRegistry.set("Any", new NodeInterfaceType("Any"));

  typeRegistry.get("Protein")?.addConversion(typeRegistry.get("Batch Protein")!, (value) => value);
  typeRegistry.get("Ligand")?.addConversion(typeRegistry.get("Batch Ligand")!, (value) => value);
  typeRegistry.get("Batch Protein")?.addConversion(typeRegistry.get("Batch Structure")!, (value) => value);
  typeRegistry.get("Batch Protein with Ligand")?.addConversion(typeRegistry.get("Batch Structure")!, (value) => value);
  typeRegistry.get("Batch Ligand")?.addConversion(typeRegistry.get("Ligand")!, (value) => value);
  typeRegistry.get("Batch Protein")?.addConversion(typeRegistry.get("Protein")!, (value) => value);

  interfaceTypes.addTypes(...typeRegistry.values());
}

function registerNodes() {
  nodeSpecs.forEach((spec) => {
    const nodeConstructor = createFoundryNode(spec);
    registeredConstructors.set(spec.type, nodeConstructor);
    baklava.editor.registerNodeType(nodeConstructor, { category: spec.category, title: spec.title });
  });
}

function addNode(type: string, x: number, y: number) {
  const Constructor = registeredConstructors.get(type);
  if (!Constructor) return;
  const node = new Constructor();
  node.position = { x: 0, y: 0 };
  setNodePosition(node, x, y);
  baklava.editor.graph.addNode(node);
}

function seedExampleWorkflow() {
  [
    ["LigandInput", -780, -190],
    ["AtomSelector", -470, -190],
    ["RFDiffusionSMbinder", -120, -180],
    ["LigandMPNN", 260, -180],
    ["RosettaFold", 610, -170],
    ["FilterByScore", 930, -170],
    ["PDBViewer", 1260, -170],
  ].forEach(([type, x, y]) => addNode(String(type), Number(x), Number(y)));
}

function portColor(typeName: string | undefined) {
  return colorsByType[(typeName as PortType) ?? "Any"] ?? colorsByType.Any;
}

function primaryNodeColor(node: AbstractNode) {
  const output = Object.values(node.outputs).find((intf) => getType(intf));
  const input = Object.values(node.inputs).find((intf) => getType(intf));
  return portColor(output || input ? getType((output ?? input)!) : undefined);
}

function connectionColor(connection: Connection) {
  return portColor(getType(connection.from));
}

function nodeByModal() {
  return baklava.editor.graph.findNodeById(viewerModal.nodeId);
}

function selectorInterface(node = nodeByModal()) {
  if (!node) return undefined;
  if (viewerModal.mode === "atom") return node.inputs.atoms as NodeInterface<string> | undefined;
  if (viewerModal.mode === "residue") return node.inputs.residues as NodeInterface<string> | undefined;
  return undefined;
}

function selectorValue() {
  return String(selectorInterface()?.value ?? "");
}

function setSelectorValue(value: string) {
  const intf = selectorInterface();
  if (intf) {
    intf.value = value;
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
  const chain = atom.chain || "";
  const resi = atom.resi ?? atom.residueIndex ?? "";
  return `${chain}${resi}`;
}

function toggleSelectorItem(value: string) {
  const values = parseSelectorList();
  const next = values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
  setSelectorValue(next.join(","));
}

function specForNode(node: AbstractNode) {
  return nodeSpecs.find((spec) => spec.type === node.type);
}

function interfaceKey(node: AbstractNode | undefined, intf: NodeInterface<any>) {
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
  };
}

function loadWorkflowDocument(document: any) {
  const state = document.baklava ?? document.graph ?? document;
  const warnings = baklava.editor.load(state);
  Object.keys(uploadedByNode).forEach((nodeId) => {
    delete uploadedByNode[nodeId];
  });
  Object.entries(document.uploads ?? {}).forEach(([nodeId, files]) => {
    uploadedByNode[nodeId] = files as UploadedStructure[];
  });
  if (warnings.length) {
    console.warn("Workflow loaded with warnings", warnings);
  }
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

function requestLoadWorkflow() {
  workflowFileInput.value?.click();
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
    runSteps[0]!.done = validation.valid;
    if (!validation.valid) {
      runState.value = "failed";
      runMessage.value = "Validation failed";
      return;
    }

    runSteps[1]!.done = true;
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
    runSteps[2]!.done = true;
    connectRunEvents(created.run_id);
    await refreshRunStatus(created.run_id);
  } catch (error) {
    runState.value = "failed";
    runMessage.value = error instanceof Error ? error.message : "Backend request failed";
  }
}

function resetRunUi() {
  runSteps.forEach((step) => {
    step.done = false;
  });
  runLogs.value = [];
  validationErrors.value = [];
  runStatus.value = null;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${apiBase.value}${path}`, {
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
  const response = await fetch(`${apiBase.value}${path}`, {
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
  const response = await fetch(`${apiBase.value}${path}`);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(readBackendMessage(payload, response.statusText));
  }
  return payload as T;
}

async function ensureSession() {
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
  const session = await postJson<SessionRecord>("/api/sessions", { document: workflowDocument() });
  currentSessionId.value = session.session_id;
  await router.replace({ query: { ...route.query, session: session.session_id } });
}

async function createNewSession() {
  closeRunEvents();
  const route = useRoute();
  const router = useRouter();
  clearWorkflow(false);
  seedExampleWorkflow();
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

async function saveSessionDocument() {
  if (!currentSessionId.value) return;
  await putJson<SessionRecord>(`/api/sessions/${currentSessionId.value}`, {
    latest_run_id: currentRunId.value || undefined,
    document: workflowDocument(),
  });
}

async function refreshRunStatus(runId = currentRunId.value) {
  if (!runId) return;
  const response = await fetch(`${apiBase.value}/api/runs/${runId}`);
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
}

async function loadArtifacts(runId = currentRunId.value) {
  if (!runId) return;
  const response = await fetch(`${apiBase.value}/api/runs/${runId}/artifacts`);
  if (!response.ok) return;
  const payload = (await response.json()) as { artifacts: BackendArtifact[] };
  artifacts.value = payload.artifacts ?? [];
}

async function loadSavedArtifacts(runId = currentRunId.value) {
  if (!runId) return;
  const response = await fetch(`${apiBase.value}/api/runs/${runId}/saves`);
  if (!response.ok) return;
  const payload = (await response.json()) as { artifacts: BackendArtifact[] };
  savedArtifacts.value = payload.artifacts ?? [];
}

async function loadOutputs(runId = currentRunId.value) {
  if (!runId) return;
  const response = await fetch(`${apiBase.value}/api/runs/${runId}/outputs`);
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
  const source = new EventSource(`${apiBase.value}/api/runs/${runId}/events`);
  eventSource.value = source;
  const eventNames = [
    "queued",
    "started",
    "node_started",
    "node_progress",
    "stdout",
    "stderr",
    "node_completed",
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
    void refreshRunStatus(event.run_id);
    void loadOutputs(event.run_id);
  } else if (event.event === "artifact_created") {
    void refreshRunFiles(event.run_id);
  } else if (event.event === "error") {
    runState.value = "failed";
    runMessage.value = event.message ?? "Run failed";
    if (event.data?.error) validationErrors.value = [event.data.error, ...validationErrors.value];
    if (event.node_id) markNodeError(event.node_id);
    void refreshRunStatus(event.run_id);
    void refreshRunFiles(event.run_id);
    closeRunEvents();
  } else if (event.event === "completed") {
    runState.value = "completed";
    runMessage.value = "Run completed";
    runSteps[3]!.done = true;
    void refreshRunStatus(event.run_id);
    void refreshRunFiles(event.run_id);
    void saveSessionDocument();
    closeRunEvents();
  } else if (event.event === "stopped") {
    runState.value = "stopped";
    runMessage.value = "Run stopped";
    void refreshRunStatus(event.run_id);
    void refreshRunFiles(event.run_id);
    closeRunEvents();
  }
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
  return `${apiBase.value}/api/artifacts/${artifact.artifact_id}`;
}

function archiveUrl() {
  return currentRunId.value ? `${apiBase.value}/api/runs/${currentRunId.value}/archive` : "#";
}

function outputForConnection(connection: Connection) {
  const fromNode = baklava.editor.graph.findNodeById(connection.from.nodeId);
  if (!fromNode) return undefined;
  const outputKey = interfaceKey(fromNode, connection.from);
  return outputs.value.find((output) => output.node_id === fromNode.id && output.output_key === outputKey);
}

function hasOutputForConnection(connection: Connection) {
  return Boolean(outputForConnection(connection));
}

function outputDownloadUrlForConnection(connection: Connection) {
  const output = outputForConnection(connection);
  if (!output || !currentRunId.value) return "#";
  return `${apiBase.value}/api/runs/${currentRunId.value}/outputs/${encodeURIComponent(output.node_id)}/${encodeURIComponent(output.output_key)}/download`;
}

function connectionCenter(connection: Connection) {
  try {
    const from = getPortCoordinates(getDomElements(connection.from));
    const to = getPortCoordinates(getDomElements(connection.to));
    return { x: (from[0] + to[0]) / 2, y: (from[1] + to[1]) / 2 };
  } catch {
    return { x: 0, y: 0 };
  }
}

function markNodeError(nodeId: string) {
  const next = new Set(errorNodeIds.value);
  next.add(nodeId);
  errorNodeIds.value = next;
}

function clearNodeError(nodeId: string) {
  if (!errorNodeIds.value.has(nodeId)) return;
  const next = new Set(errorNodeIds.value);
  next.delete(nodeId);
  errorNodeIds.value = next;
}

function openViewer(nodeId: string, title: string, mode: ViewerModal["mode"]) {
  viewerModal.open = true;
  viewerModal.nodeId = nodeId;
  viewerModal.title = title;
  viewerModal.mode = mode;
  viewerModal.fileIndex = 0;
  void nextTick(initializeViewer);
}

function closeViewer() {
  viewerModal.open = false;
}

function connectedSourceNode(node: AbstractNode) {
  const inputInterfaces = new Set(Object.values(node.inputs));
  const connection = baklava.editor.graph.connections.find((conn) => inputInterfaces.has(conn.to));
  return connection ? baklava.editor.graph.findNodeById(connection.from.nodeId) : undefined;
}

function structuresForNodeId(nodeId: string, seen = new Set<string>()): UploadedStructure[] {
  if (seen.has(nodeId)) return [];
  seen.add(nodeId);
  const ownFiles = uploadedByNode[nodeId];
  if (ownFiles?.length) return ownFiles;
  const node = baklava.editor.graph.findNodeById(nodeId);
  const upstream = node ? connectedSourceNode(node) : undefined;
  if (upstream) {
    const upstreamFiles = structuresForNodeId(upstream.id, seen);
    if (upstreamFiles.length) return upstreamFiles;
  }
  return [{ name: "example_complex.pdb", type: "pdb", content: proteinExample }];
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
  if (!viewer || !activeModalFile.value) return;
  const file = activeModalFile.value;
  viewer.clear();
  if (file.type === "fasta") {
    viewer.render();
    return;
  }
  viewer.addModel(file.content || proteinExample, file.type === "sdf" ? "sdf" : "pdb");
  if (viewerModal.style === "stick" || viewerModal.mode === "atom") {
    viewer.setStyle({}, { stick: { radius: 0.18 } });
  } else if (viewerModal.style === "surface") {
    viewer.setStyle({ hetflag: false }, { cartoon: { color: "lightgray" } });
    viewer.addSurface((globalThis as any).$3Dmol?.SurfaceType?.VDW ?? 1, { opacity: 0.6, color: "white" }, { hetflag: false });
    viewer.setStyle({ hetflag: true }, { stick: { colorscheme: "greenCarbon", radius: 0.24 } });
  } else {
    viewer.setStyle({ hetflag: false }, { cartoon: { color: "spectrum" } });
    viewer.setStyle({ hetflag: true }, { stick: { colorscheme: "greenCarbon", radius: 0.22 } });
  }
  const selected = new Set(parseSelectorList());
  if (viewerModal.mode === "atom") {
    selected.forEach((name) => {
      viewer.addStyle({ atom: name }, { sphere: { color: "orange", radius: 0.45 } });
    });
    viewer.setClickable({}, true, (atom: any) => {
      toggleSelectorItem(atomId(atom));
    });
  } else if (viewerModal.mode === "residue") {
    selected.forEach((residue) => {
      const chain = residue[0];
      const resi = Number(residue.slice(1));
      viewer.addStyle({ chain, resi }, { stick: { color: "magenta", radius: 0.24 } });
    });
    viewer.setClickable({}, true, (atom: any) => {
      const value = residueId(atom);
      if (value) toggleSelectorItem(value);
    });
  }
  viewer.zoomTo();
  viewer.render();
}

watch([() => viewerModal.fileIndex, () => viewerModal.style, () => viewerModal.open], () => {
  void nextTick(renderViewer);
});

registerTypes();
registerNodes();
seedExampleWorkflow();

baklava.hooks.renderInterface.subscribe("foundry-colors", ({ intf, el }) => {
  const type = getType(intf);
  if (type) {
    el.dataset.interfaceType = type;
    el.style.setProperty("--foundry-port-color", portColor(type));
  }
  const node = baklava.editor.graph.findNodeById(intf.nodeId);
  const source = String((node as any)?.inputs?.source?.value ?? "");
  if (node?.type === "LigandInput" && intf.name === "SMILES") {
    el.style.display = source === "SMILES" ? "" : "none";
  } else {
    el.style.removeProperty("display");
  }
  return { intf, el };
});

baklava.hooks.renderNode.subscribe("foundry-node-colors", ({ node, el }) => {
  el.style.setProperty("--foundry-node-color", primaryNodeColor(node));
  el.classList.toggle("foundry-node-error", errorNodeIds.value.has(node.id));
  return { node, el };
});

onMounted(() => {
  void nextTick(renderViewer);
  void ensureSession();
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
        <p>Right click the canvas to add Rosetta Foundry nodes.</p>
      </div>
      <nav class="topbar-actions" aria-label="Workflow actions">
        <label class="api-base">
          API
          <input v-model="apiBase" spellcheck="false" />
        </label>
        <span v-if="currentSessionId" class="session-chip">{{ currentSessionId.slice(0, 18) }}</span>
        <NuxtLink class="doc-link" to="/document">Document</NuxtLink>
        <NuxtLink class="doc-link" to="/sessions">Sessions</NuxtLink>
        <button type="button" class="icon-button" title="New session" @click="createNewSession">N</button>
        <button type="button" class="icon-button" title="Save workflow" @click="saveWorkflow">S</button>
        <button type="button" class="icon-button" title="Load workflow" @click="requestLoadWorkflow">L</button>
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
      <span v-for="step in runSteps" :key="step.label" :class="{ done: step.done }">{{ step.label }}</span>
    </section>

    <section class="canvas-panel" aria-label="Workflow canvas">
      <ClientOnly>
        <BaklavaEditor :view-model="baklava">
          <template #connection="{ connection }">
            <g class="typed-connection" :style="{ '--connection-color': connectionColor(connection) }">
              <Components.ConnectionWrapper :connection="connection" />
              <foreignObject
                v-if="hasOutputForConnection(connection)"
                :x="connectionCenter(connection).x - 13"
                :y="connectionCenter(connection).y - 13"
                width="26"
                height="26"
              >
                <a class="flow-download" :href="outputDownloadUrlForConnection(connection)" title="Download flow data">D</a>
              </foreignObject>
            </g>
          </template>
        </BaklavaEditor>
      </ClientOnly>
    </section>

    <aside class="run-panel" aria-label="Backend run details">
      <section class="run-panel-section">
        <header>
          <h2>Status</h2>
          <a v-if="currentRunId && runState === 'completed'" class="archive-link" :href="archiveUrl()">Archive</a>
          <span v-else-if="runState === 'failed'" class="error-label">ERROR</span>
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
        <p v-else>No issues</p>
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
        <pre>{{ runLogs.length ? runLogs.join("\n") : "No command output yet" }}</pre>
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
          <label>
            File
            <select v-model.number="viewerModal.fileIndex">
              <option v-for="(file, index) in modalFiles" :key="file.name + index" :value="index">{{ file.name }}</option>
            </select>
          </label>
          <label>
            Style
            <select v-model="viewerModal.style">
              <option value="cartoon">Cartoon</option>
              <option value="stick">Stick</option>
              <option value="surface">Surface</option>
            </select>
          </label>
          <label v-if="viewerModal.mode === 'atom' || viewerModal.mode === 'residue'" class="selector-value">
            Selection
            <input
              :value="selectorValue()"
              spellcheck="false"
              @input="setSelectorValue(($event.target as HTMLInputElement).value)"
            />
          </label>
        </div>
        <div ref="viewerEl" class="viewer-surface" />
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

.doc-link,
.icon-button,
.run-button,
.stop-button {
  border: 1px solid #c6d0dc;
  background: #ffffff;
  color: #17202a;
  cursor: pointer;
  text-decoration: none;
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

.statusbar .done {
  color: #7ee0c4;
  font-weight: 700;
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
  color: #7ee0c4;
  text-decoration: none;
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

.logs-section pre {
  min-height: 120px;
  margin: 0;
  white-space: pre-wrap;
  color: #b8c5d4;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

.canvas-panel > div,
.canvas-panel .baklava-editor {
  width: 100%;
  height: 100%;
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

.flow-download {
  display: flex;
  width: 24px;
  height: 24px;
  align-items: center;
  justify-content: center;
  border: 1px solid #b8c7d7;
  border-radius: 50%;
  background: #ffffff;
  color: #176f5d;
  font-size: 11px;
  font-weight: 800;
  text-decoration: none;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}

.baklava-node.foundry-node-error {
  border-top-color: #ff5252 !important;
  box-shadow: 0 0 0 2px rgba(255, 82, 82, 0.75);
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

.viewer-controls select {
  height: 34px;
  border: 1px solid #c7d0dc;
  border-radius: 6px;
  background: #ffffff;
  color: #17202a;
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
