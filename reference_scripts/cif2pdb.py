#!/usr/bin/env python3
# convert_cif_to_pdb.py
# 批量转换当前目录下所有 .cif 文件为 .pdb

import sys
import glob
from pathlib import Path

try:
    import gemmi
except ImportError:
    print("Error: gemmi not installed. Run: pip install gemmi", file=sys.stderr)
    sys.exit(1)

def main():
    cif_files = glob.glob("*.cif")
    if not cif_files:
        print("No .cif files found in current directory.")
        return

    for cif_path in cif_files:
        try:
            # 读取 CIF 文件
            structure = gemmi.read_structure(cif_path)
            # 生成输出 PDB 文件名
            pdb_path = Path(cif_path).with_suffix(".pdb")
            # 写入 PDB（保留链 ID、残基编号等）
            structure.write_pdb(str(pdb_path))
            print(f"Converted: {cif_path} -> {pdb_path}")
        except Exception as e:
            print(f"Failed to convert {cif_path}: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()