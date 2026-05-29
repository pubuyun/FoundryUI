import type { UploadedStructure } from "./workbenchTypes";

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

export function detectStructureType(fileName: string): UploadedStructure["type"] {
  const lower = fileName.toLowerCase();
  if (lower.endsWith(".pdb")) return "pdb";
  if (lower.endsWith(".fasta") || lower.endsWith(".fa")) return "fasta";
  return "unknown";
}

export function parseSelectorList(value = "") {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function atomId(atom: any) {
  return String(atom.atom || atom.name || `${atom.elem ?? "Atom"}${atom.serial ?? (typeof atom.index === "number" ? atom.index + 1 : "")}`);
}

export function residueId(atom: any) {
  const resn = String(atom.resn || atom.residue || "").trim();
  if (resn && !STANDARD_RESIDUES.has(resn.toUpperCase())) return resn;
  const chain = atom.chain || "";
  const resi = atom.resi ?? atom.residueIndex ?? "";
  return `${chain}${resi}`;
}

export function residueSelection(residue: string) {
  if (/^[A-Za-z]\d+$/.test(residue)) {
    return { chain: residue[0], resi: Number(residue.slice(1)) };
  }
  return { resn: residue };
}

export function parseProteinAtomMap(value = ""): Record<string, string[]> {
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

export function formatProteinAtomMap(value: Record<string, string[]>) {
  const compact = Object.fromEntries(Object.entries(value).filter(([, atoms]) => atoms.length).map(([residue, atoms]) => [residue, [...new Set(atoms)].join(",")]));
  return JSON.stringify(compact, null, 2);
}

export function atomNamesFromContent(content: string) {
  const names: string[] = [];
  content.split(/\r?\n/).forEach((line) => {
    if (!line.startsWith("ATOM") && !line.startsWith("HETATM")) return;
    const name = line.slice(12, 16).trim();
    const element = line.length >= 78 ? line.slice(76, 78).trim().toUpperCase() : "";
    const inferred = name.replace(/^[0-9]+/, "").charAt(0).toUpperCase();
    if (element === "H" || (!element && inferred === "H")) return;
    if (name && !names.includes(name)) names.push(name);
  });
  return names;
}

export function parseChiralityTargets(value = "") {
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

export function formatChiralityTargets(targets: Array<{ atom: string; chirality: string }>) {
  return targets.map((target) => `${target.atom}:${target.chirality === "S" ? "S" : "R"}`).join(", ");
}
