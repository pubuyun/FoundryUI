- 当把Batch Protein/Ligand输入到Protein/Ligand时，只取第一个
- 联动处理节点：凡是会改变模型或分数数量、顺序的节点，必须设计为**同时接受模型和分数，并同时输出过滤后的模型和分数**
- 未传入 Score 则不输出 Score 
## Note
### MDNote
- 笔记，无输入输出
#### Input
- N/A
#### Options
- Text Field
#### Output
- N/A
## Selector
### Residue Selector
- 用3DViewer选择Residue或手动输入,输出类似"A103,A201"的字符串
#### Input
- Protein*
#### Options
- Text Field (example:"A103,A201")
- 3D Viewer residue selector when protein inputted
#### Output
- List of Residues
### Atom Selector
- 用3DViewer选择Atom或手动输入,输出类似"C1,O2"的字符串
#### Input
- Ligand*
#### Options
- Text Field (example:"C1,C2")
- 3D Viewer atom selector* when ligand inputted
#### Output
- List of Atoms
## Structure Inputs
### Ligand Input
- 手动输入Ligand
#### Input
- N/A
#### Options
- Upload File(pdb/sdf)/SMILES(text)
- 3D Viewer
#### Output
- Ligand
### Protein Input
- 手动输入Batch Protein
#### Input
- N/A
#### Options
- Upload File(pdb)
- File Selector + 3D Viewer
#### Output
- Batch Protein
### Sequence Input
- 手动输入Batch Sequence
#### Input
- N/A
#### Options
- Upload File(fasta)
#### Output
- Batch Sequence
## Generation
### RFDiffusionSMbinder
- RFdiffusion3的SMbinder生成
#### Input
- Ligand
- List of Atoms (select_fixed_atoms) default ""
- List of Atoms (select_buried) default ""
- List of Atoms (select_exposed) default ""
#### Options
- length
- n_batches
- diffusion_batch_size
#### Output
- Batch Protein with Ligand
## MPNN
### LigandMPNN
- LigandMPNN
#### Input
- Batch Protein with Ligand
- List of Residues (fixed_residues/redesigned_residues*)
#### Options
- number_of_batches required
- batch_size required
- seed default 42
- temperature default 0.05
- bias_AA default ""
- omit_AA default ""
#### Output
- Batch Sequence
### ProteinMPNN
- ProteinMPNN
#### Input
- Batch Protein
- List of Residues (fixed_residues/redesigned_residues*)
#### Options
- number_of_batches required 
- batch_size required
- seed default 42
- temperature default 0.05
- bias_AA default ""
- omit_AA default ""
#### Output
- Batch Sequence

## Folding
### RosettaFold
- 折叠Batch Sequence, 可能跟Ligand共折叠
#### Input
- Batch Sequence
- Ligand*
#### Options
- 0-1 float: early_stopping_plddt_threshold default 0.5
- int: diffusion_batch_size default 5
- int: num_steps default 50
- int: seed default 42
#### Output
- Batch Protein with Ligand/Batch Protein
- Score
## Filter
### FilterByScore
- 根据**一个**分数指标过滤[Batch Protein with Ligand/Batch Protein]
#### Input
- Batch Protein with Ligand/Batch Protein
- Score
#### Options
- [Specific Score] from {pLDDT, length, pTM, interface_PAE*, ipTM*, ranking_score*}
	- Is largest top [int]
	- Is smallest top [int]
	- Higher than [float]
	- Lower than [float]
#### Output
- Batch Protein with Ligand/Batch Protein
- Score
### FilterByLigand
- 留下所有[Batch Protein with Ligand]中含有[Ligand]的，可以设置是否手性敏感
#### Input
- Batch Protein with Ligand
- Ligand
- Score*
#### Options
- Ignore Chirality?
#### Output
- Batch Protein with Ligand
- Score*
## Logic
### BinaryLogic
- 对输入的两个Batch Protein (With Ligand)进行逻辑操作
#### Input
- Batch Protein with Ligand/Batch Protein1
- Score1*
- Batch Protein with Ligand/Batch Protein2 (should be same type to input 1)
- Score2*
#### Options
- OR/AND/NOR/NAND/XOR
#### Output
- Batch Protein with Ligand/Batch Protein
- Score*

## Util
### Protein2Seq
- 提取Batch Protein的Batch Sequence
#### Input
- Batch Protein
#### Options
#### Output
- Batch Sequence
### Merge
- 把Batch Protein和Batch Ligand合并，或用一个Ligand合并所有Batch Protein
#### Input
- (Batch) Ligand
- Batch Protein
#### Options
#### Output
- Batch Protein with Ligand
### Split
- 把Batch Protein with Ligand分开，输出Batch Protein和Batch Ligand(不同Ligand构象)
#### Input
- Batch Protein with Ligand
#### Options
#### Output
- Batch Ligand
- Batch Protein
## View
### PDBViewer
- 用3D Viewer查看Batch Protein
#### Input
- Batch Protein (with Ligand)
#### Options
- File Selector + 3D Viewer
#### Output
- N/A

### SequenceViewer
- 用Sequence Viewer查看Batch Sequence
#### Input
- Batch Sequence
#### Options
- File Selector + 3D Viewer
#### Output
- N/A

## Save
### Save Proteins with Scores
- 把蛋白的pdb跟分数一起保存，分数以csv格式保存，其中有一列跟pdb文件名对应.
#### Input
- Batch Protein (with Ligand)
- Score
#### Options
- Folder Selector
#### Output
- N/A
### Save Sequences
- 把Batch Sequence保存为fasta格式
#### Input
- Batch Sequence
#### Options
- Folder Selector
#### Output
- N/A
### Save Ligands
- 把Ligand保存为pdb格式
#### Input
- (Batch) Ligand
#### Options
- Folder Selector
#### Output
- N/A
