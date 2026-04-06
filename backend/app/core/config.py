"""
应用配置模块
使用 Pydantic Settings 管理环境变量和配置
"""
from typing import List, Optional, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
import os


def parse_comma_separated(value: Any) -> List[str]:
    """解析逗号分隔的字符串为列表"""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        if not value.strip():
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


class Settings(BaseSettings):
    """应用配置类"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_parse_none_str="None"  # 正确处理 None 字符串
    )
    
    # 应用基础配置
    app_name: str = Field(default="工业缺陷检测平台", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    
    # 数据库配置
    database_url: str = Field(default="sqlite+aiosqlite:///./app.db", alias="DATABASE_URL")
    
    # Redis 配置
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND")
    
    # JWT 认证配置
    secret_key: str = Field(default="your-secret-key", alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    
    # 文件存储配置
    upload_dir: str = Field(default="uploads", alias="UPLOAD_DIR")
    max_upload_size: int = Field(default=100 * 1024 * 1024, alias="MAX_UPLOAD_SIZE")  # 100MB
    
    # 使用字符串存储列表配置，通过 validator 解析
    allowed_image_extensions_str: str = Field(
        default="jpg,jpeg,png,bmp,tiff,webp",
        alias="ALLOWED_IMAGE_EXTENSIONS"
    )
    
    # ML 模型配置
    models_dir: str = Field(default="./models", alias="MODELS_DIR")
    default_device: str = Field(default="cuda", alias="DEFAULT_DEVICE")
    default_batch_size: int = Field(default=16, alias="DEFAULT_BATCH_SIZE")
    default_learning_rate: float = Field(default=0.001, alias="DEFAULT_LEARNING_RATE")
    default_epochs: int = Field(default=100, alias="DEFAULT_EPOCHS")
    
    # LLM 配置
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4", alias="OPENAI_MODEL")
    dashscope_api_key: Optional[str] = Field(default=None, alias="DASHSCOPE_API_KEY")
    dashscope_model: str = Field(default="qwen-max", alias="DASHSCOPE_MODEL")
    
    # 日志配置
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")
    
    # CORS 配置
    allowed_origins_str: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="ALLOWED_ORIGINS"
    )
    
    @field_validator("allowed_image_extensions_str")
    @classmethod
    def validate_extensions(cls, v):
        """验证扩展名配置"""
        if not v or not v.strip():
            return "jpg,jpeg,png,bmp,tiff,webp"
        return v
    
    @field_validator("allowed_origins_str")
    @classmethod
    def validate_origins(cls, v):
        """验证来源配置"""
        if not v or not v.strip():
            return "http://localhost:5173,http://127.0.0.1:5173"
        return v
    
    @property
    def allowed_image_extensions(self) -> List[str]:
        """获取允许的图片扩展名列表"""
        return parse_comma_separated(self.allowed_image_extensions_str)
    
    @property
    def allowed_origins(self) -> List[str]:
        """获取允许的跨域来源列表"""
        return parse_comma_separated(self.allowed_origins_str)
    
    @property
    def is_production(self) -> bool:
        """检查是否为生产环境"""
        return self.environment.lower() == "production"
    
    @property
    def is_sqlite(self) -> bool:
        """检查是否使用 SQLite 数据库"""
        return "sqlite" in self.database_url.lower()


# 全局配置实例
settings = Settings()

# 确保上传目录存在
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.models_dir, exist_ok=True)
