from pathlib import Path
import shutil
from app.utils.dataset_parser import DatasetAnalyzer, DatasetConverter

# 测试解析原始YOLO数据集
print("=== 测试完整VOC转换 ===")
analyzer = DatasetAnalyzer('uploads/datasets/neu-1_20260406_190440/extracted/neu', 'yolo')
preview = analyzer.get_preview_images(5)
info = analyzer._dataset_info

print(f"DatasetInfo path: {info.path}")
print(f"Images count: {len(info.images)}")

# 使用转换器
converter = DatasetConverter()
output_dir = "uploads/datasets/test_voc_output2"

# 清理并转换
import shutil
if Path(output_dir).exists():
    shutil.rmtree(output_dir)

print("\n开始转换...")
result = converter.to_voc(info, output_dir)
print(f"转换完成: {result}")

# 检查结果
jpeg_train = Path(output_dir) / "JPEGImages" / "train"
print(f"\nJPEGImages/train存在: {jpeg_train.exists()}")
if jpeg_train.exists():
    files = list(jpeg_train.glob("*.jpg"))
    print(f"文件数量: {len(files)}")
    print(f"前5个: {[f.name for f in files[:5]]}")

# 检查Annotations
anno_train = Path(output_dir) / "Annotations" / "train"
print(f"\nAnnotations/train存在: {anno_train.exists()}")
if anno_train.exists():
    files = list(anno_train.glob("*.xml"))
    print(f"文件数量: {len(files)}")
    print(f"前5个: {[f.name for f in files[:5]]}")

# 检查错误
print(f"\n转换错误: {converter.errors}")
