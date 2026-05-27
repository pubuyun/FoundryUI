# Binary Logic

Combines two structure sets with a boolean set operation.

> [!input]
- `Batch Protein (With Ligand) 1`: first <span class="type complex">Batch Protein (With Ligand)</span>.
- `Score1*`: optional first <span class="type score">Score</span>.
- `Batch Protein (With Ligand) 2`: second structure batch.
- `Score2*`: optional second score batch.

> [!options]
- `Operation`: `OR`, `AND`, `NOR`, `NAND`, or `XOR`.

> [!output]
- `structures`: combined structures.
- `score`: combined scores when score inputs are present.
