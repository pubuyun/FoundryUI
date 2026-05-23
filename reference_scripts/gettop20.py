#!/usr/bin/env python3
import os
import glob
import json
import zipfile
import pandas as pd
import io
import sys

from rdkit import Chem
from rdkit.Chem import rdCIPLabeler
from Bio.PDB import MMCIFParser, PDBIO, Select

class LigandSelect(Select):
    """用于从 Biopython 的结构中提取特定链/残基的类"""
    def __init__(self, chain_id='B'):
        self.chain_id = chain_id
        
    def accept_residue(self, residue):
        # 匹配链ID为 L 的残基 (有些软件将小分子标记在L链)
        if residue.get_parent().id == self.chain_id:
            return 1
        return 0

def get_chirality_of_C1_from_cif(cif_file):
    """
    读取 CIF 文件，提取 L 链的小分子，转化为 PDB block 交给 RDKit，并判断 C1 手性。
    返回 True (S), False (R), 或 None。
    """
    parser = MMCIFParser(QUIET=True)
    try:
        structure = parser.get_structure("struct", cif_file)
    except Exception as e:
        print(f"  [Error] Biopython 无法解析 CIF {cif_file}: {e}")
        return None
    
    # 提取 L 链分子并写为 PDB 格式流
    io_obj = PDBIO()
    io_obj.set_structure(structure)
    pdb_stream = io.StringIO()
    try:
        io_obj.save(pdb_stream, select=LigandSelect('B'))
    except Exception as e:
        return None
        
    pdb_block = pdb_stream.getvalue()
    if not pdb_block.strip():
        return None  # 没找到小分子
        
    # 用 RDKit 加载 PDB block
    mol = Chem.MolFromPDBBlock(pdb_block, sanitize=True, removeHs=False)
    if mol is None:
        return None
        
    # 分配 CIP 标签
    rdCIPLabeler.AssignCIPLabels(mol)
    
    # 查找名为 C1 的原子
    c1_atom = None
    for atom in mol.GetAtoms():
        pdb_info = atom.GetPDBResidueInfo()
        if pdb_info is not None and pdb_info.GetName().strip() == "C0":
            c1_atom = atom
            break
            
    if c1_atom is None or not c1_atom.HasProp("_CIPCode"):
        return None
        
    cip = c1_atom.GetProp("_CIPCode")
    if cip == "S":
        return True
    elif cip == "R":
        return False
    else:
        return None

def main():
    # ================= 路径配置 =================
    rf3_outputs_dir = "/data/foundry/rf3_outputs"
    csv_filename = "rf3_S_chirality_top20.csv"
    zip_filename = "top20_S_candidates.zip"
    # ============================================

    results = []
    
    print(f"🔍 正在扫描 {rf3_outputs_dir} 目录下的所有结果并计算手性...")

    # 1. 遍历解析所有结果文件夹
    for design_dir in glob.glob(os.path.join(rf3_outputs_dir, "*")):
        if not os.path.isdir(design_dir):
            continue
            
        design_id = os.path.basename(design_dir)
        summary_file = os.path.join(design_dir, f"{design_id}_summary_confidences.json")
        
        # 寻找对应的 cif 文件
        cif_files = glob.glob(os.path.join(design_dir, "*.cif"))
        if not os.path.exists(summary_file) or not cif_files:
            continue
            
        # 这里默认取找到的第一个 cif 结构文件
        cif_file = cif_files[0]
            
        # 读取手性，只有为 S (True) 的才继续保留
        is_S = get_chirality_of_C1_from_cif(cif_file)
        if is_S is not True:
            continue  # 丢弃 R 构型或无法判断的结果
            
        # 解析分数
        with open(summary_file, 'r') as f:
            conf = json.load(f)
            
        ranking_score = conf.get("ranking_score", 0.0)
        ptm = conf.get("ptm", 0.0)
        iptm = conf.get("iptm", 0.0)
        plddt_raw = conf.get("overall_plddt", 0.0)
        plddt = plddt_raw * 100 if plddt_raw <= 1.0 else plddt_raw
        has_clash = conf.get("has_clash", True)
        
        # ======== 提取序列长度 (Length) ========
        seq_length = conf.get("length") or conf.get("seq_length") or conf.get("L")
        
        # 如果 json 里有 sequence 字段，直接算长度
        if not seq_length and "sequence" in conf:
            seq = conf.get("sequence")
            if isinstance(seq, str):
                seq_length = len(seq)
            elif isinstance(seq, dict) and "A" in seq:
                seq_length = len(seq["A"])
                
        # 如果 json 里全没找到，读取 cif 文件统计链 A 的 CA 原子数量
        if not seq_length:
            try:
                ca_count = 0
                with open(cif_file, 'r') as f_cif:
                    for line in f_cif:
                        # 粗略匹配 CIF 中的 ATOM 行、CA 原子 以及 链 A
                        if line.startswith("ATOM") and " CA " in line and " A " in line:
                            ca_count += 1
                if ca_count > 0:
                    seq_length = ca_count
            except Exception:
                pass
        # ========================================
        
        interface_pae = None
        try:
            chain_pair_pae_min = conf.get("chain_pair_pae_min", [])
            if len(chain_pair_pae_min) > 0 and len(chain_pair_pae_min[0]) > 1:
                val = chain_pair_pae_min[0][1]
                if val is not None:
                    interface_pae = float(val)
        except Exception:
            pass
            
        results.append({
            "design_id": design_id,
            "length": seq_length if seq_length else pd.NA,  # 新增 length 列
            "ranking_score": round(ranking_score, 4),
            "pTM": round(ptm, 4),
            "ipTM": round(iptm, 4),
            "pLDDT": round(plddt, 2),
            "interface_PAE": round(interface_pae, 2) if interface_pae is not None else None,
            "has_clash": has_clash,
            "C1_Chirality": "S"
        })
        
    if not results:
        print("❌ 未提取到任何 S 构型的有效数据，请检查输出目录和小分子结构。")
        return
        
    # 2. 转为 DataFrame 并按 ranking_score 降序排列
    df = pd.DataFrame(results)
    df = df.sort_values(by="ranking_score", ascending=False)
    
    # 确保 length 列为整数类型（处理可能存在的空值）
    if 'length' in df.columns:
        df['length'] = df['length'].astype('Int64')
    
    # 提取 Top 20 
    df_top20 = df.head(20)
    
    # 保存结果 CSV
    df_top20.to_csv(csv_filename, index=False)
    print(f"✅ 成功找到并排序了 {len(df)} 个 S 构型任务，Top 20 得分榜已保存至: {csv_filename}")
    
    # 打印前 10 名供预览
    print("\n🏆 Top 10 (S 构型) Binder 排行榜预览:")
    print(df_top20.head(10).to_string(index=False))

    # 3. 提取 Top 20 对应的 design_id 并进行 ZIP 打包
    top20_ids = df_top20["design_id"].tolist()
    
    print(f"\n📦 正在将 Top 20 的文件夹打包至 {zip_filename} ...")
    success_count = 0
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for d_id in top20_ids:
            folder_path = os.path.join(rf3_outputs_dir, d_id)
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, rf3_outputs_dir)
                        zipf.write(file_path, arcname)
                success_count += 1
            else:
                print(f"⚠️ 找不到对应的文件夹: {folder_path}")

    print(f"\n🎉 大功告成！成功打包了 {success_count} 个 S 构型文件夹。")
    print(f"⬇️ 请下载 {zip_filename} 到本地，使用 PyMOL 查看最终结构！")

if __name__ == "__main__":
    main()