#!/usr/bin/env python3
"""
批量将当前目录下的 PDB 文件转换为 FASTA 格式，所有序列合并写入一个文件。
使用方法: python pdb_to_fasta_merged.py
输出: all_sequences.fasta (包含所有 PDB 中所有链的氨基酸序列)
"""

import os
import sys
from collections import defaultdict

# 三字母氨基酸到单字母的映射表
AA3_TO_1 = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
    "MSE": "M",  # 硒代甲硫氨酸
    "PYL": "O",  # 吡咯赖氨酸
    "SEC": "U",  # 硒半胱氨酸
}


def parse_pdb(pdb_path):
    """
    解析 PDB 文件，返回字典: {链ID: 氨基酸序列字符串}
    按残基序号和插入码排序，忽略非标准氨基酸（不在映射表中）。
    """
    residues = defaultdict(dict)  # chain -> {(resseq, icode): one_letter}
    with open(pdb_path, "r") as f:
        for line in f:
            if not line.startswith("ATOM"):
                continue
            if len(line) < 27:
                continue
            res_name = line[17:20].strip()
            if res_name not in AA3_TO_1:
                continue
            chain_id = line[21] if len(line) > 21 else " "
            if chain_id == " ":
                chain_id = "_"
            try:
                res_seq = int(line[22:26].strip())
            except ValueError:
                continue
            icode = line[26] if len(line) > 26 else " "

            key = (res_seq, icode)
            if key not in residues[chain_id]:
                residues[chain_id][key] = AA3_TO_1[res_name]

    sequences = {}
    for chain, res_dict in residues.items():
        sorted_keys = sorted(res_dict.keys(), key=lambda x: (x[0], x[1]))
        seq = "".join(res_dict[k] for k in sorted_keys)
        if seq:
            sequences[chain] = seq
    return sequences


def write_all_fasta(output_file, all_entries):
    """
    将所有条目写入单个 FASTA 文件。
    all_entries: list of (header, sequence)
    """
    with open(output_file, "w") as f:
        for header, seq in all_entries:
            f.write(header + "\n")
            for i in range(0, len(seq), 80):
                f.write(seq[i : i + 80] + "\n")
    print(f"已生成合并文件: {output_file}")


def main():
    output_file = "all_sequences.fasta"
    pdb_files = [f for f in os.listdir(".") if f.lower().endswith(".pdb")]
    if not pdb_files:
        print("当前目录下没有找到 .pdb 文件。")
        sys.exit(0)

    all_entries = []  # 存储 (header, sequence)

    for pdb_file in pdb_files:
        print(f"正在处理: {pdb_file}")
        try:
            sequences = parse_pdb(pdb_file)
            if not sequences:
                print(f"警告: {pdb_file} 中未找到可识别的氨基酸序列。")
                continue
            base = os.path.splitext(pdb_file)[0]
            for chain, seq in sequences.items():
                header = f">{base}|{chain}"
                all_entries.append((header, seq))
        except Exception as e:
            print(f"处理 {pdb_file} 时出错: {e}", file=sys.stderr)

    if not all_entries:
        print("未提取到任何有效序列，不生成输出文件。")
        sys.exit(1)

    write_all_fasta(output_file, all_entries)
    print(f"共处理 {len(pdb_files)} 个 PDB 文件，生成 {len(all_entries)} 条序列。")


if __name__ == "__main__":
    main()
