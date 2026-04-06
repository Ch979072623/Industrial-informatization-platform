from pathlib import Path
from app.utils.dataset_parser import DatasetAnalyzer, DatasetConverter

# 测试解析原始YOLO数据集
print("=== 测试YOLO解析 ===")
import logging
logging.basicConfig(level=logging.DEBUG)

yolo_path = Path('uploads/datasets/neu-1_20260406_190440/extracted/neu')
print(f"YOLO路径: {yolo_path}")
print(f"存在: {yolo_path.exists()}")
print(f"目录内容: {list(yolo_path.iterdir())}")

# 检查train/images
train_img = yolo_path / 'train' / 'images'
print(f"\ntrain/images: {train_img}")
print(f"存在: {train_img.exists()}")
if train_img.exists():
    files = list(train_img.glob('*.jpg'))[:5]
    print(f"文件: {[f.name for f in files]}")

analyzer = DatasetAnalyzer(str(yolo_path), 'yolo')
preview = analyzer.get_preview_images(5)
print(f'\n预览图像数量: {len(preview)}')
print('原始YOLO数据集图像路径:')
for p in preview[:3]:
    print(f"  {p['filename']}: {p['filepath']}")
    path = Path(p['filepath'])
    print(f"    绝对: {path.is_absolute()}")
    print(f"    存在: {path.exists()}")

# 测试VOC转换
print("\n=== 测试VOC转换 ===")
from app.utils.dataset_parser import DatasetInfo, DatasetFormat

# 获取DatasetInfo
info = analyzer._dataset_info
print(f"DatasetInfo path: {info.path}")
print(f"Images count: {len(info.images)}")
if info.images:
    img = info.images[0]
    print(f"First image: {img.filename}")
    print(f"  filepath: {img.filepath}")
    print(f"  split: {img.split}")

# 测试转换
converter = DatasetConverter()
output_dir = "uploads/datasets/test_voc_output"
import shutil
if Path(output_dir).exists():
    shutil.rmtree(output_dir)

result = converter.to_voc(info, output_dir)
print(f"\n转换结果: {result}")

# 检查输出
jpeg_path = Path(output_dir) / "JPEGImages" / "train"
print(f"\nJPEGImages/train存在: {jpeg_path.exists()}")
if jpeg_path.exists():
    files = list(jpeg_path.glob("*.jpg"))[:5]
    print(f"文件: {[f.name for f in files]}")
