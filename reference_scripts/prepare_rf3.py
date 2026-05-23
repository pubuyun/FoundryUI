import os
import glob
import json

def main():
    mpnn_outputs_dir = "/data/foundry/mpnn_outputs"
    # 小分子配体的 SMILES 字符串 (请替换为你的真实 SMILES)
    ligand_smiles = "CCCC(C)(CCO)SC[C@@H](C(=O)NCC(=O)O)N" 
    
    fasta_files = glob.glob(os.path.join(mpnn_outputs_dir, "*.fa"))
    
    rf3_jobs = []

    for fa_file in fasta_files:
        base_name = os.path.basename(fa_file).replace(".fa", "")
        
        with open(fa_file, 'r') as f:
            lines = f.read().strip().split('\n')
            
        for i in range(0, len(lines), 2):
            if not lines[i].startswith(">"): continue
            seq = lines[i+1]
            
            d_idx = f"d{i//2}" 
            design_id = f"{base_name}_{d_idx}"
            
            # 构造 RF3 所需的单一任务配置
            job = {
                "name": design_id,
                "components": [
                    {
                        "seq": seq,
                        "chain_id": "A"
                    },
                    {
                        "smiles": ligand_smiles
                    }
                ]
            }
            rf3_jobs.append(job)

    # 将所有任务保存到一个 JSON 文件中
    out_json = "rf3_batch_input.json"
    with open(out_json, 'w') as jf:
        json.dump(rf3_jobs, jf, indent=4)

    print(f"✅ 成功提取了 {len(rf3_jobs)} 条候选序列！")
    print(f"✅ 批量输入文件已保存至: {out_json}")

if __name__ == "__main__":
    main()
