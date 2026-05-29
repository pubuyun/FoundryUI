export function normalizeApiBase(value: string) {
  return value.trim().replace(/\/+$/, "");
}

export function readBackendMessage(payload: any, fallback: string) {
  if (typeof payload?.detail === "string") return payload.detail;
  if (payload?.detail?.message) return payload.detail.message;
  if (payload?.message) return payload.message;
  return fallback || "Backend request failed";
}

export function formatErrorDetails(error: Record<string, any>) {
  const details = error.details;
  if (!details || typeof details !== "object") return "";
  const parts: string[] = [];
  const detailFields: Array<[string, string]> = [
    ["missing_atoms", "Missing atoms"],
    ["missing_residues", "Missing residues"],
    ["missing_chains", "Missing chains"],
    ["missing_entries", "Missing entries"],
    ["invalid_entries", "Invalid entries"],
  ];
  detailFields.forEach(([key, label]) => {
    const value = details[key];
    if (Array.isArray(value) && value.length) parts.push(`${label}: ${value.join(", ")}`);
  });
  if (details.missing_atoms && !Array.isArray(details.missing_atoms) && typeof details.missing_atoms === "object") {
    const value = Object.entries(details.missing_atoms)
      .map(([residue, atoms]) => `${residue}: ${Array.isArray(atoms) ? atoms.join(", ") : String(atoms)}`)
      .join("; ");
    if (value) parts.push(`Missing atoms: ${value}`);
  }
  return parts.join(" | ");
}
