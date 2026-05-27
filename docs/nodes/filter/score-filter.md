# Score Filter

Filters structures by a selected score metric while preserving <span class="type score">Score</span> alignment.

> [!input]
- `Batch Protein (With Ligand)`: <span class="type complex">Batch Protein (With Ligand)</span>.
- `Score`: <span class="type score">Score</span>.

> [!options]
- `Specific Score`: selected at runtime from numeric fields in the connected score payload.
- `Filter Mode`: `Is largest top`, `Is smallest top`, `Greater than`, or `Smaller than`.
- `top / threshold`: top count for top modes, numeric threshold for comparison modes.

> [!output]
- Filtered structures and matching score records.
