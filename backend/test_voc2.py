from pathlib import Path
import shutil
from app.utils.dataset_parser import DatasetAnalyzer, DatasetConverter

# 测试解析原始YOLO数据集
print("=== 测试VOC转换 ===")
analyzer = DatasetAnalyzer('uploads/datasets/neu-1_20260406_190440/extracted/neu', 'yolo')
preview = analyzer.get_preview_images(5)  # 这会触发parse
info = analyzer._dataset_info

print(f"DatasetInfo path: {info.path}")
print(f"Images count: {len(info.images)}")

if info.images:
    img = info.images[0]
    print(f"\nFirst image: {img.filename}")
    print(f"  filepath: {img.filepath}")
    print(f"  split: {img.split}")
    print(f"  filepath exists: {Path(img.filepath).exists()}")

# 手动测试转换一个图像
output_dir = Path("uploads/datasets/test_voc_output")
if output_dir.exists():
    shutil.rmtree(output_dir)
output_dir.mkdir(parents=True, exist_ok=True)

# 创建目录
(output_dir / "JPEGImages" / "train").mkdir(parents=True, exist_ok=True)
(output_dir / "Annotations" / "train").mkdir(parents=True, exist_ok=True)

# 测试复制一个图像
img = info.images[0]
src_path = Path(img.filepath)
print(f"\n测试复制图像:")
print(f"  src_path: {src_path}")
print(f"  src_path exists: {src_path.exists()}")

dst_path = output_dir / "JPEGImages" / "train" / img.filename
print(f"  dst_path: {dst_path}")

if src_path.exists():
    shutil.copy2(src_path, dst_path)
    print(f"  复制成功: {dst_path.exists()}")
else:
    print(f"  复制失败: 源文件不存在")
    # 尝试其他路径
    alt_path = Path(info.path) / src_path
    print(f"  尝试 alt_path: {alt_path}")
    print(f"  alt_path exists: {alt_path.exists()}")
