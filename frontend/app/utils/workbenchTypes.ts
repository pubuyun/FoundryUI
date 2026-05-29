import type { OptionSpec } from "./foundrySpecs";

export interface UploadedStructure {
  name: string;
  type: "pdb" | "fasta" | "unknown";
  content: string;
}

export interface ViewerModal {
  open: boolean;
  nodeId: string;
  title: string;
  mode: NonNullable<OptionSpec["viewerMode"]>;
  fileIndex: number;
  style: "cartoon" | "stick" | "surface";
}

export interface PendingRunInput {
  runId: string;
  nodeId: string;
  nodeType: string;
  fields: string[];
  payloads: Record<string, any>;
  choices: Record<string, string[]>;
  sequence: number;
}

export interface BackendArtifact {
  artifact_id: string;
  payload_type: string;
  media_type: string;
  path: string;
  byte_size: number;
  item_count: number;
  node_id?: string | null;
  node_type?: string | null;
}

export interface BackendOutput {
  node_id: string;
  output_key: string;
  type_name: string;
  item_count: number;
  artifact_ids: string[];
  paths: string[];
}

export interface RunEventPayload {
  event: string;
  run_id: string;
  sequence?: number;
  node_id?: string | null;
  node_type?: string | null;
  message?: string | null;
  data?: Record<string, any>;
}

export interface RunStatus {
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

export interface SessionRecord {
  session_id: string;
  created_at: string;
  updated_at: string;
  latest_run_id?: string | null;
  document?: Record<string, any> | null;
}

export interface WorkflowPreset {
  label: string;
  file: string;
}

export type SidebarPanel = "logs" | "saves" | "nodes" | "issues";
