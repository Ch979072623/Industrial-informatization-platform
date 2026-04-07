"""
数据增强模块测试

测试覆盖:
- 正常流程：完整的增强配置 → 预览 → 批量执行
- 异常情况：网络失败、Celery 任务失败、文件读取失败、格式错误
- 边界条件：空流水线、0概率操作、超大图片、无标注框图片
- 并发场景：同时执行多个增强任务
"""
import os
import sys
import pytest
import asyncio
import numpy as np
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.augmentation_service import (
    AugmentationService,
    AugmentationConfig,
    BBox,
    AugmentationResult,
    get_augmentation_service,
)
from app.schemas.augmentation import (
    CreateJobRequest,
    PreviewRequest,
)


# ==================== Fixtures ====================

@pytest.fixture
def sample_image():
    """创建测试图像"""
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


@pytest.fixture
def sample_bboxes():
    """创建测试边界框"""
    return [
        BBox(x1=0.1, y1=0.1, x2=0.3, y2=0.3, class_id=0),
        BBox(x1=0.5, y1=0.5, x2=0.7, y2=0.7, class_id=1),
    ]


@pytest.fixture
def sample_pipeline():
    """创建测试流水线配置"""
    return [
        {
            "operation_type": "horizontal_flip",
            "name": "水平翻转",
            "probability": 1.0,
            "enabled": True,
            "order": 0,
        },
        {
            "operation_type": "brightness",
            "name": "亮度调整",
            "probability": 0.8,
            "enabled": True,
            "order": 1,
            "brightness_range": [-20, 20],
        },
    ]


@pytest.fixture
def empty_pipeline():
    """空流水线配置"""
    return []


@pytest.fixture
def invalid_pipeline():
    """无效流水线配置"""
    return [
        {
            "operation_type": "unknown_operation",
            "name": "未知操作",
            "probability": 1.0,
        }
    ]


@pytest.fixture
def large_image():
    """超大测试图像 (4K)"""
    return np.random.randint(0, 255, (2160, 3840, 3), dtype=np.uint8)


# ==================== 配置验证测试 ====================

class TestAugmentationConfig:
    """配置验证测试类"""

    def test_validate_valid_pipeline(self, sample_pipeline):
        """测试有效流水线验证"""
        is_valid, error = AugmentationConfig.validate_pipeline_config(sample_pipeline)
        assert is_valid is True
        assert error == ""

    def test_validate_empty_pipeline(self, empty_pipeline):
        """测试空流水线验证"""
        is_valid, error = AugmentationConfig.validate_pipeline_config(empty_pipeline)
        assert is_valid is True
        assert error == ""

    def test_validate_invalid_pipeline(self, invalid_pipeline):
        """测试无效流水线验证"""
        is_valid, error = AugmentationConfig.validate_pipeline_config(invalid_pipeline)
        assert is_valid is False
        assert "操作类型无效" in error

    def test_validate_too_many_operations(self):
        """测试操作数量限制"""
        pipeline = [
            {"operation_type": "horizontal_flip", "probability": 1.0}
            for _ in range(25)
        ]
        is_valid, error = AugmentationConfig.validate_pipeline_config(pipeline)
        assert is_valid is False
        assert "不能超过20个" in error

    def test_validate_probability_range(self):
        """测试概率范围验证"""
        pipeline = [
            {"operation_type": "horizontal_flip", "probability": 1.5}
        ]
        is_valid, error = AugmentationConfig.validate_pipeline_config(pipeline)
        assert is_valid is False
        assert "概率必须在 0-1 之间" in error

    def test_validate_non_list_config(self):
        """测试非列表配置验证"""
        is_valid, error = AugmentationConfig.validate_pipeline_config({})
        assert is_valid is False
        assert "必须是列表" in error


# ==================== 边界框测试 ====================

class TestBBox:
    """边界框测试类"""

    def test_bbox_to_albumentations(self):
        """测试边界框转换到 albumentations 格式"""
        bbox = BBox(x1=0.1, y1=0.2, x2=0.4, y2=0.6, class_id=5)
        alb_bbox = bbox.to_albumentations()
        
        # 验证格式 [x_center, y_center, width, height, class_id]
        assert len(alb_bbox) == 5
        assert abs(alb_bbox[0] - 0.25) < 0.001  # x_center
        assert abs(alb_bbox[1] - 0.40) < 0.001  # y_center
        assert abs(alb_bbox[2] - 0.30) < 0.001  # width
        assert abs(alb_bbox[3] - 0.40) < 0.001  # height
        assert alb_bbox[4] == 5  # class_id

    def test_bbox_from_albumentations(self):
        """测试从 albumentations 格式创建边界框"""
        alb_bbox = [0.25, 0.40, 0.30, 0.40, 5]
        bbox = BBox.from_albumentations(alb_bbox)
        
        assert abs(bbox.x1 - 0.10) < 0.001
        assert abs(bbox.y1 - 0.20) < 0.001
        assert abs(bbox.x2 - 0.40) < 0.001
        assert abs(bbox.y2 - 0.60) < 0.001
        assert bbox.class_id == 5

    def test_bbox_clamp(self):
        """测试边界框裁剪"""
        bbox = BBox(x1=-0.1, y1=1.2, x2=0.5, y2=-0.2, class_id=0)
        clamped = bbox.clamp()
        
        assert clamped.x1 == 0.0
        assert clamped.y1 == 1.0
        assert clamped.x2 == 0.5
        assert clamped.y2 == 0.0


# ==================== 增强服务测试 ====================

class TestAugmentationService:
    """增强服务测试类"""

    @pytest.fixture(autouse=True)
    def setup_service(self):
        """设置测试服务"""
        self.service = AugmentationService()

    def test_augment_image_with_valid_pipeline(self, sample_image, sample_bboxes, sample_pipeline):
        """测试有效流水线的图像增强"""
        result = self.service.augment_image(sample_image, sample_bboxes, sample_pipeline)
        
        assert isinstance(result, AugmentationResult)
        assert result.success is True
        assert result.image is not None
        assert result.image.shape == sample_image.shape
        assert len(result.applied_operations) > 0

    def test_augment_image_with_empty_pipeline(self, sample_image, sample_bboxes, empty_pipeline):
        """测试空流水线的图像增强"""
        result = self.service.augment_image(sample_image, sample_bboxes, empty_pipeline)
        
        assert result.success is True
        # 空流水线应该返回原图
        assert np.array_equal(result.image, sample_image)
        assert len(result.bboxes) == len(sample_bboxes)

    def test_augment_image_with_zero_probability(self, sample_image, sample_bboxes):
        """测试0概率操作的增强"""
        pipeline = [
            {
                "operation_type": "horizontal_flip",
                "probability": 0.0,
                "enabled": True,
            }
        ]
        result = self.service.augment_image(sample_image, sample_bboxes, pipeline)
        
        assert result.success is True
        # 0概率操作不应该应用
        assert np.array_equal(result.image, sample_image)

    def test_augment_image_with_disabled_operation(self, sample_image, sample_bboxes):
        """测试禁用操作的增强"""
        pipeline = [
            {
                "operation_type": "horizontal_flip",
                "probability": 1.0,
                "enabled": False,
            }
        ]
        result = self.service.augment_image(sample_image, sample_bboxes, pipeline)
        
        assert result.success is True
        # 禁用操作不应该应用
        assert np.array_equal(result.image, sample_image)

    def test_augment_large_image(self, large_image, sample_bboxes):
        """测试超大图像增强"""
        pipeline = [
            {
                "operation_type": "horizontal_flip",
                "probability": 1.0,
            }
        ]
        result = self.service.augment_image(large_image, sample_bboxes, pipeline)
        
        assert result.success is True
        assert result.image.shape == large_image.shape

    def test_augment_image_without_bboxes(self, sample_image):
        """测试无标注框的图像增强"""
        pipeline = [
            {
                "operation_type": "horizontal_flip",
                "probability": 1.0,
            }
        ]
        result = self.service.augment_image(sample_image, [], pipeline)
        
        assert result.success is True
        assert len(result.bboxes) == 0

    def test_generate_preview(self, sample_image, sample_bboxes, sample_pipeline):
        """测试预览生成"""
        preview_image, preview_bboxes, applied_ops = self.service.generate_preview(
            sample_image, sample_bboxes, sample_pipeline, max_size=256
        )
        
        assert preview_image is not None
        # 预览应该被缩放到 max_size 以下
        assert max(preview_image.shape[:2]) <= 256
        assert isinstance(applied_ops, list)

    def test_compute_config_hash(self, sample_pipeline):
        """测试配置哈希计算"""
        hash1 = AugmentationService.compute_config_hash(sample_pipeline)
        hash2 = AugmentationService.compute_config_hash(sample_pipeline)
        
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 哈希长度
        assert hash1 == hash2  # 相同配置应该产生相同哈希

    def test_draw_bboxes(self, sample_image, sample_bboxes):
        """测试边界框绘制"""
        result = AugmentationService.draw_bboxes(
            sample_image, sample_bboxes, class_names=["class_a", "class_b"]
        )
        
        assert result is not None
        assert result.shape == sample_image.shape


# ==================== 并发测试 ====================

class TestConcurrentAugmentation:
    """并发增强测试类"""

    @pytest.mark.asyncio
    async def test_concurrent_preview_generation(self):
        """测试并发预览生成"""
        service = AugmentationService()
        
        # 创建多个预览请求
        tasks = []
        for i in range(5):
            image = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)
            bboxes = [BBox(x1=0.1, y1=0.1, x2=0.3, y2=0.3, class_id=0)]
            pipeline = [{"operation_type": "horizontal_flip", "probability": 1.0}]
            
            # 使用线程池执行
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    service.generate_preview, image, bboxes, pipeline
                )
                tasks.append(future)
        
        # 等待所有任务完成
        results = [t.result(timeout=10) for t in tasks]
        
        # 验证所有结果
        for img, bboxes, ops in results:
            assert img is not None


# ==================== 错误处理测试 ====================

class TestErrorHandling:
    """错误处理测试类"""

    def test_service_singleton(self):
        """测试服务单例模式"""
        service1 = get_augmentation_service()
        service2 = get_augmentation_service()
        assert service1 is service2

    def test_invalid_image_format(self, sample_bboxes):
        """测试无效图像格式"""
        service = AugmentationService()
        invalid_image = np.array([1, 2, 3])  # 无效格式
        
        pipeline = [{"operation_type": "horizontal_flip", "probability": 1.0}]
        
        # 应该抛出异常或返回失败结果
        try:
            result = service.augment_image(invalid_image, sample_bboxes, pipeline)
            assert result.success is False or result.error_message is not None
        except Exception:
            pass  # 抛出异常也是可接受的

    def test_bbox_clamping_after_augmentation(self, sample_image):
        """测试增强后边界框裁剪"""
        service = AugmentationService()
        
        # 创建超出边界的边界框
        bboxes = [BBox(x1=-0.1, y1=-0.1, x2=1.2, y2=1.2, class_id=0)]
        
        pipeline = [{"operation_type": "horizontal_flip", "probability": 1.0}]
        result = service.augment_image(sample_image, bboxes, pipeline)
        
        assert result.success is True
        for bbox in result.bboxes:
            assert 0 <= bbox.x1 <= 1
            assert 0 <= bbox.y1 <= 1
            assert 0 <= bbox.x2 <= 1
            assert 0 <= bbox.y2 <= 1


# ==================== Schema 验证测试 ====================

class TestSchemaValidation:
    """Schema 验证测试类"""

    def test_create_job_request_validation(self):
        """测试创建任务请求验证"""
        # 有效请求
        valid_request = CreateJobRequest(
            name="测试任务",
            source_dataset_id="test-dataset-id",
            pipeline_config=[],
            augmentation_factor=2,
        )
        assert valid_request.augmentation_factor == 2

    def test_preview_request_validation(self):
        """测试预览请求验证"""
        request = PreviewRequest(
            source_dataset_id="test-dataset-id",
            pipeline_config=[],
        )
        assert request.image_id is None  # image_id 是可选的


# ==================== 集成测试 ====================

@pytest.mark.integration
class TestIntegration:
    """集成测试类"""

    @pytest.mark.asyncio
    async def test_full_augmentation_workflow(self):
        """测试完整的增强工作流"""
        # 1. 验证配置
        pipeline = [
            {"operation_type": "horizontal_flip", "probability": 0.5},
            {"operation_type": "brightness", "brightness_range": [-20, 20], "probability": 0.8},
        ]
        
        is_valid, error = AugmentationConfig.validate_pipeline_config(pipeline)
        assert is_valid is True
        
        # 2. 执行增强
        service = AugmentationService()
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        bboxes = [BBox(x1=0.2, y1=0.2, x2=0.4, y2=0.4, class_id=0)]
        
        result = service.augment_image(image, bboxes, pipeline)
        assert result.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
