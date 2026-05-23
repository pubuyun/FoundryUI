import os
import subprocess
from pathlib import Path

def main():
    # ================= 配置路径 =================
    # 你的 rfd3 输出目录 (请根据实际情况修改)
    rfd3_outputs_dir = "/data/foundry/rfd3_outputs"  
    # LigandMPNN 的输出目录
    mpnn_outputs_dir = "/data/foundry/mpnn_outputs"  
    
    # 展开波浪号以获取绝对路径
    checkpoint_path = os.path.expanduser("~/.foundry/checkpoints/ligandmpnn_v_32_010_25.pt")
    
    # 推理脚本的相对路径（假设你在 foundry 根目录下运行此脚本）
    inference_script = "models/mpnn/src/mpnn/inference.py"
    # ============================================

    # 1. 确保输出目录存在
    os.makedirs(mpnn_outputs_dir, exist_ok=True)

    # 2. 检查模型权重文件是否存在
    if not os.path.exists(checkpoint_path):
        print(f"❌ 错误: 找不到模型权重文件 {checkpoint_path}")
        return

    # 3. 查找所有的 .cif.gz 文件
    rfd3_dir_path = Path(rfd3_outputs_dir)
    cif_files = list(rfd3_dir_path.glob("*.cif.gz"))

    if not cif_files:
        print(f"⚠️ 在 {rfd3_outputs_dir} 中没有找到任何 .cif.gz 文件！")
        return

    print(f"🔍 找到 {len(cif_files)} 个骨架文件，开始进行 LigandMPNN 批量序列设计...")

    # 4. 遍历并运行 LigandMPNN
    for i, cif_file in enumerate(cif_files, start=1):
        print(f"\n[{i}/{len(cif_files)}] 正在处理: {cif_file.name}")
        
        # 构建执行命令
        cmd = [
            "python", inference_script,
            "--model_type", "ligand_mpnn",
            "--checkpoint_path", checkpoint_path,
            "--is_legacy_weights", "True",
            "--structure_path", str(cif_file),
            "--out_directory", mpnn_outputs_dir,
            "--batch_size", "5",  # 为每个骨架生成5条序列
            "--write_fasta", "True",
            "--write_structures", "True"
        ]
        
        # 执行命令
        try:
            # check=True 会在命令执行失败（返回非0状态码）时抛出异常
            subprocess.run(cmd, check=True)
            print(f"✅ 成功完成: {cif_file.name}")
        except subprocess.CalledProcessError as e:
            print(f"❌ 处理 {cif_file.name} 时发生错误: {e}")

    print(f"\n🎉 全部批处理完成！序列和结构已保存至: {mpnn_outputs_dir}")

if __name__ == "__main__":
    main()
