"""
Training API 集成测试

测试覆盖:
- 创建训练任务 (POST /api/v1/training/jobs)
- 列表查询 (GET /api/v1/training/jobs)
- 详情查询 (GET /api/v1/training/jobs/{id})
- 进度查询 (GET /api/v1/training/jobs/{id}/progress)
- 任务控制 (POST /api/v1/training/jobs/{id}/control)
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.training_job import TrainingJob
from app.models.ml_module import ModelBuilderConfig
from app.models.dataset import Dataset
from app.models.production_line import ProductionLine
from app.models.user import User


# ==================== Fixtures ====================

@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession) -> User:
    """创建测试用户, id 与 admin_client fixture 对齐"""
    user = User(id="admin-123", username="train_test", email="train@test.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_config(db_session: AsyncSession, sample_user: User) -> ModelBuilderConfig:
    """创建测试模型构建器配置"""
    config = ModelBuilderConfig(
        name="test_config",
        architecture_json={},
        created_by=sample_user.id,
    )
    db_session.add(config)
    await db_session.commit()
    await db_session.refresh(config)
    return config


@pytest_asyncio.fixture
async def sample_dataset(db_session: AsyncSession, sample_user: User) -> Dataset:
    """创建测试数据集"""
    dataset = Dataset(
        name="test_dataset",
        path="/tmp/test_ds",
        format="YOLO",
        created_by=sample_user.id,
    )
    db_session.add(dataset)
    await db_session.commit()
    await db_session.refresh(dataset)
    return dataset


@pytest_asyncio.fixture
async def sample_line(db_session: AsyncSession, sample_user: User) -> ProductionLine:
    """创建测试产线"""
    line = ProductionLine(name="test_line", created_by=sample_user.id)
    db_session.add(line)
    await db_session.commit()
    await db_session.refresh(line)
    return line


@pytest_asyncio.fixture
async def sample_job(
    db_session: AsyncSession,
    sample_config: ModelBuilderConfig,
    sample_dataset: Dataset,
    sample_line: ProductionLine,
) -> TrainingJob:
    """创建测试训练任务"""
    job = TrainingJob(
        model_builder_config_id=sample_config.id,
        dataset_id=sample_dataset.id,
        production_line_id=sample_line.id,
        hyperparams={"epochs": 100, "batch": 16, "imgsz": 640},
        status="pending",
        progress=0.0,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


# ==================== 创建任务测试 ====================

class TestCreateTrainingJob:
    """创建训练任务测试"""

    @pytest.mark.asyncio
    async def test_create_training_job_success(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_config: ModelBuilderConfig,
        sample_dataset: Dataset,
        sample_line: ProductionLine,
    ) -> None:
        """成功创建训练任务,返回 job_id + status='pending'"""
        payload = {
            "model_builder_config_id": sample_config.id,
            "dataset_id": sample_dataset.id,
            "production_line_id": sample_line.id,
            "hyperparams": {"epochs": 50, "batch": 8},
        }
        
        with patch("app.services.training_service.train_model.delay") as mock_delay:
            mock_task = MagicMock()
            mock_task.id = "celery-task-123"
            mock_delay.return_value = mock_task
            
            response = await admin_client.post("/api/v1/training/jobs", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "pending"
        assert data["data"]["progress"] == 0.0
        assert "id" in data["data"]
        assert data["data"]["hyperparams"]["epochs"] == 50
        assert data["data"]["hyperparams"]["batch"] == 8
        assert data["data"]["hyperparams"]["imgsz"] == 640  # default applied
    
    @pytest.mark.asyncio
    async def test_create_training_job_applies_defaults(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_config: ModelBuilderConfig,
        sample_dataset: Dataset,
        sample_line: ProductionLine,
    ) -> None:
        """不传 epochs/batch/imgsz,创建后 hyperparams 里有 default 值"""
        payload = {
            "model_builder_config_id": sample_config.id,
            "dataset_id": sample_dataset.id,
            "production_line_id": sample_line.id,
            "hyperparams": {},
        }
        
        with patch("app.services.training_service.train_model.delay") as mock_delay:
            mock_task = MagicMock()
            mock_task.id = "celery-task-456"
            mock_delay.return_value = mock_task
            
            response = await admin_client.post("/api/v1/training/jobs", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["hyperparams"]["epochs"] == 150
        assert data["data"]["hyperparams"]["batch"] == 32
        assert data["data"]["hyperparams"]["imgsz"] == 640
    
    @pytest.mark.asyncio
    async def test_create_training_job_invalid_config(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_dataset: Dataset,
        sample_line: ProductionLine,
    ) -> None:
        """model_builder_config_id 不存在,返回 404"""
        payload = {
            "model_builder_config_id": "non-existent-id",
            "dataset_id": sample_dataset.id,
            "production_line_id": sample_line.id,
        }
        
        response = await admin_client.post("/api/v1/training/jobs", json=payload)
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_create_training_job_unauthorized_config(
        self,
        user_client: AsyncClient,
        db_session: AsyncSession,
        sample_config: ModelBuilderConfig,
        sample_dataset: Dataset,
        sample_line: ProductionLine,
    ) -> None:
        """
        ModelBuilderConfig 属于其他用户,返回 403 (对齐 augmentation 现役约定)
        注: user_client 的 user_id 是 user-123,而 fixture 数据属于 admin-123
        """
        payload = {
            "model_builder_config_id": sample_config.id,
            "dataset_id": sample_dataset.id,
            "production_line_id": sample_line.id,
        }
        
        response = await user_client.post("/api/v1/training/jobs", json=payload)
        # augmentation 返回 403,对齐现役
        assert response.status_code == 403


# ==================== 列表查询测试 ====================

class TestListTrainingJobs:
    """列表查询测试"""

    @pytest.mark.asyncio
    async def test_list_training_jobs(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_job: TrainingJob,
    ) -> None:
        """返回训练任务列表,分页生效"""
        response = await admin_client.get("/api/v1/training/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["items"]) >= 1
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 20
    
    @pytest.mark.asyncio
    async def test_list_training_jobs_filter_by_status(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_job: TrainingJob,
    ) -> None:
        """status=running 过滤生效"""
        response = await admin_client.get("/api/v1/training/jobs?status=pending")
        assert response.status_code == 200
        data = response.json()
        items = data["data"]["items"]
        assert all(item["status"] == "pending" for item in items)
        
        response2 = await admin_client.get("/api/v1/training/jobs?status=running")
        assert response2.status_code == 200
        data2 = response2.json()
        items2 = data2["data"]["items"]
        assert len(items2) == 0


# ==================== 详情查询测试 ====================

class TestGetTrainingJob:
    """详情查询测试"""

    @pytest.mark.asyncio
    async def test_get_training_job(
        self,
        admin_client: AsyncClient,
        sample_job: TrainingJob,
    ) -> None:
        """返回任务详情"""
        response = await admin_client.get(f"/api/v1/training/jobs/{sample_job.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == sample_job.id
        assert data["data"]["status"] == sample_job.status
    
    @pytest.mark.asyncio
    async def test_get_training_job_not_found(
        self,
        admin_client: AsyncClient,
    ) -> None:
        """job_id 不存在,返回 404"""
        response = await admin_client.get("/api/v1/training/jobs/non-existent-id")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_training_job_other_user(
        self,
        user_client: AsyncClient,
        sample_job: TrainingJob,
    ) -> None:
        """
        查别人的任务
        注: TrainingJob ORM 目前缺少 created_by 字段,无法做用户隔离,
            当前行为是返回 200。需在后续轮次补充 created_by 后改为 404。
        """
        response = await user_client.get(f"/api/v1/training/jobs/{sample_job.id}")
        # 由于缺少 created_by,当前无法做权限隔离,返回 200
        assert response.status_code == 200


# ==================== 进度查询测试 ====================

class TestGetTrainingJobProgress:
    """进度查询测试"""

    @pytest.mark.asyncio
    async def test_get_training_job_progress(
        self,
        admin_client: AsyncClient,
        sample_job: TrainingJob,
    ) -> None:
        """返回 progress 字段集合,字段名为 processed_epochs/total_epochs"""
        response = await admin_client.get(f"/api/v1/training/jobs/{sample_job.id}/progress")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        progress = data["data"]
        assert "job_id" in progress
        assert "status" in progress
        assert "progress" in progress
        assert "processed_epochs" in progress
        assert "total_epochs" in progress
        assert "current_operation" in progress
        assert "error_message" in progress


# ==================== 任务控制测试 ====================

class TestControlTrainingJob:
    """任务控制测试"""

    @pytest.mark.asyncio
    async def test_control_training_job_cancel(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        sample_job: TrainingJob,
    ) -> None:
        """action=cancel,任务进入 cancelled 状态"""
        payload = {"action": "cancel"}
        
        with patch("app.services.training_service.AsyncResult") as mock_async_result:
            mock_result = MagicMock()
            mock_async_result.return_value = mock_result
            
            response = await admin_client.post(
                f"/api/v1/training/jobs/{sample_job.id}/control",
                json=payload,
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "cancelled"
        assert data["data"]["action"] == "cancel"
    
    @pytest.mark.asyncio
    async def test_control_training_job_invalid_action(
        self,
        admin_client: AsyncClient,
        sample_job: TrainingJob,
    ) -> None:
        """action=stop(不支持),返回 422 验证错误"""
        payload = {"action": "stop"}
        
        response = await admin_client.post(
            f"/api/v1/training/jobs/{sample_job.id}/control",
            json=payload,
        )
        
        assert response.status_code == 422
