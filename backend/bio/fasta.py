from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

from Bio import SeqIO


@dataclass(frozen=True)
class SequenceRecord:
    id: str
    sequence: str
    description: str = ""


def parse_fasta(content: str) -> list[SequenceRecord]:
    records = [
        SequenceRecord(id=record.id, sequence=str(record.seq), description=record.description)
        for record in SeqIO.parse(StringIO(content), "fasta")
    ]
    if not records:
        raise ValueError("FASTA contains no sequences.")
    invalid = [record.id for record in records if not record.sequence or any(char.isspace() for char in record.sequence)]
    if invalid:
        raise ValueError(f"Invalid FASTA sequence records: {', '.join(invalid)}")
    return records


def write_fasta(records: list[dict] | list[SequenceRecord]) -> str:
    lines: list[str] = []
    for index, record in enumerate(records, start=1):
        if isinstance(record, SequenceRecord):
            record_id = record.id or f"sequence_{index:04d}"
            sequence = record.sequence
        else:
            record_id = str(record.get("id") or f"sequence_{index:04d}")
            sequence = str(record.get("sequence") or "")
        lines.extend([f">{record_id}", sequence])
    return "\n".join(lines) + ("\n" if lines else "")
