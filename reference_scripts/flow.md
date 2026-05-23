Foundry
设计配置

pdb要求配体不为A链
pdb上传到foundry/
创建sm_binder_design.json:
{
"Cys-Gly-3M3SH": {
"input": "./lcg3m3sh.pdb",
"ligand": "LIG", // 残基名
"length": "40-210", // 生成的蛋白Binder的长度范围
"select_fixed_atoms": {
"LIG": "" // 固定配体坐标
}
"select_buried": {
"LIG": ""  
 }
"select_exposed": {
"LIG": "" // 固定配体坐标
}
}
}

---

rfd3设计骨架
执行
rfd3 design \
 out_dir=./rfd3_outputs \
 inputs=./sm_binder_design.json \
 n_batches=10 \
 diffusion_batch_size=10
会生成100个骨架

---

LigandMPNN设计序列
上传batchligandmpnn.py到foundry/
运行batchligandmpnn.py ,生成500个序列 (为每个骨架生成5个序列)

---

准备rf3结构预测输入
上传prepare_rf3.py到foundry/
运行prepare_rf3.py
给Rosetta Fold3准备输入
替换SMILES:C(SC[C@@H](<C(NCC(O)=O)=O>)N)(CCC)(CCO)C

---

RF3预测结构
运行以预测500个序列的结构:
rf3 fold \
 inputs='rf3_batch_input.json' \
 ckpt_path='./checkpoints/rf3/rf3_foundry_01_24_latest_remapped.ckpt' \
 out_dir='./rf3_outputs' \
 early_stopping_plddt_threshold=0.7

---

提取前20个
上传gettop20.py到foundry/
运行gettop20.py, 获取根据ranking_score=(0.8*pTM+0.2*ipTM)排名的前20个B链C0构型为S的
自动打包到top20_candidates.zip
解压并提取cif到foundry/top20_cif
unzip top20_candidates.zip -d ./top20_candidates
mkdir top20_cif
find ./top20_candidates -mindepth 2 -maxdepth 2 -type f -name "\*.cif" -exec cp {} ./top20_cif/ \;

---

上传cif2pdb.py到foundry/top20_cif
安装gemmi
python -m pip install gemmi
运行将cif转换到pdb
cif2pdb.py
在foundry/下创建top20_pdb文件夹，并将pdb移动到此文件夹：
mkdir top20_pdb
mv top20_cif/\*.pdb top20_pdb/
