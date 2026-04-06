"""
前后端共享常量

这些常量用于确保前后端在关键数据上保持一致
"""

# ==================== 用户角色 ====================
class UserRole:
    """用户角色"""
    ADMIN = "admin"
    USER = "user"
    
    ALL = [ADMIN, USER]


# ==================== 任务状态 ====================
class JobStatus:
    """任务状态"""
    PENDING = "pending"       # 待处理
    RUNNING = "running"       # 运行中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败
    CANCELLED = "cancelled"   # 已取消
    
    ALL = [PENDING, RUNNING, COMPLETED, FAILED, CANCELLED]


# ==================== 数据集相关 ====================
class DatasetFormat:
    """数据集格式"""
    YOLO = "YOLO"
    COCO = "COCO"
    VOC = "VOC"
    
    ALL = [YOLO, COCO, VOC]


class DataSplit:
    """数据划分类型"""
    TRAIN = "train"
    VAL = "val"
    TEST = "test"
    
    ALL = [TRAIN, VAL, TEST]


# ==================== 检测结果 ====================
class DetectionVerdict:
    """检测结论"""
    PASS = "PASS"  # 合格
    NG = "NG"      # 不合格（No Good）
    
    ALL = [PASS, NG]


# ==================== 模型相关 ====================
class ModelStatus:
    """模型状态"""
    TRAINING = "training"
    READY = "ready"
    DEPRECATED = "deprecated"
    
    ALL = [TRAINING, READY, DEPRECATED]


# ==================== 剪枝策略 ====================
class PruningStrategy:
    """剪枝策略"""
    MAGNITUDE = "magnitude"           # 幅度剪枝
    STRUCTURED = "structured"         # 结构化剪枝
    UNSTRUCTURED = "unstructured"     # 非结构化剪枝
    
    ALL = [MAGNITUDE, STRUCTURED, UNSTRUCTURED]


# ==================== 蒸馏策略 ====================
class DistillationStrategy:
    """蒸馏策略"""
    RESPONSE = "response"       # 响应蒸馏
    FEATURE = "feature"         # 特征蒸馏
    ATTENTION = "attention"     # 注意力蒸馏
    
    ALL = [RESPONSE, FEATURE, ATTENTION]


# ==================== API 响应代码 ====================
class APIStatusCode:
    """API 状态码"""
    SUCCESS = 200
    CREATED = 201
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    INTERNAL_ERROR = 500


# ==================== 文件相关 ====================
ALLOWED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "bmp", "tiff", "webp"]
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB

# ==================== 默认超参数 ====================
DEFAULT_HYPERPARAMS = {
    "epochs": 100,
    "batch_size": 16,
    "learning_rate": 0.001,
    "device": "cuda",
    "optimizer": "Adam",
    "scheduler": "cosine"
}

# ==================== 默认数据集划分比例 ====================
DEFAULT_SPLIT_RATIO = {
    "train": 0.7,
    "val": 0.2,
    "test": 0.1
}
