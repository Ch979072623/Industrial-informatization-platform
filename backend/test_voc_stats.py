from app.utils.dataset_parser import DatasetAnalyzer

# 测试VOC数据集
voc_path = 'uploads/datasets/neu-1_YOLO_to_VOC_20260406_215052'
analyzer = DatasetAnalyzer(voc_path, 'voc')
preview = analyzer.get_preview_images(5)

print(f'找到 {len(preview)} 张预览图像')
for p in preview[:3]:
    print(f"\n{p['filename']}:")
    print(f"  split: {p['split']}")
    print(f"  annotation_count: {p['annotation_count']}")
    print(f"  bboxes: {len(p.get('bboxes', []))}")

# 测试analyze_labels
print("\n\n测试 analyze_labels:")
analysis = analyzer.analyze_labels()
print(f"class_names: {analysis.get('class_names')}")
print(f"annotations_per_class: {analysis.get('annotations_per_class')}")
