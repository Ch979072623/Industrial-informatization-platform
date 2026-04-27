"""
TrainingJob ORM 完整性测试
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.training_job import TrainingJob
from app.models.ml_module import ModelBuilderConfig
from app.models.dataset import Dataset
from app.models.production_line import ProductionLine
from app.models.user import User


@pytest.mark.asyncio
async def test_training_job_create_with_error_message(db_session: AsyncSession) -> None:
    """新增字段 error_message 可写入 + 读出"""
    user = User(username="test1", email="test1@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    config = ModelBuilderConfig(name="cfg1", architecture_json={}, created_by=user.id)
    db_session.add(config)
    await db_session.flush()

    dataset = Dataset(name="ds1", path="/tmp/ds1", format="YOLO", created_by=user.id)
    db_session.add(dataset)
    await db_session.flush()

    line = ProductionLine(name="line1", created_by=user.id)
    db_session.add(line)
    await db_session.flush()

    job = TrainingJob(
        model_builder_config_id=config.id,
        dataset_id=dataset.id,
        production_line_id=line.id,
        hyperparams={},
        error_message="CUDA out of memory",
        created_by=user.id,
    )
    db_session.add(job)
    await db_session.commit()

    result = await db_session.execute(select(TrainingJob).where(TrainingJob.id == job.id))
    fetched = result.scalar_one()
    assert fetched.error_message == "CUDA out of memory"


@pytest.mark.asyncio
async def test_training_job_error_message_default_null(db_session: AsyncSession) -> None:
    """error_message 默认为 None"""
    user = User(username="test2", email="test2@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    config = ModelBuilderConfig(name="cfg2", architecture_json={}, created_by=user.id)
    db_session.add(config)
    await db_session.flush()

    dataset = Dataset(name="ds2", path="/tmp/ds2", format="YOLO", created_by=user.id)
    db_session.add(dataset)
    await db_session.flush()

    line = ProductionLine(name="line2", created_by=user.id)
    db_session.add(line)
    await db_session.flush()

    job = TrainingJob(
        model_builder_config_id=config.id,
        dataset_id=dataset.id,
        production_line_id=line.id,
        hyperparams={},
        created_by=user.id,
    )
    db_session.add(job)
    await db_session.commit()

    result = await db_session.execute(select(TrainingJob).where(TrainingJob.id == job.id))
    fetched = result.scalar_one()
    assert fetched.error_message is None


@pytest.mark.asyncio
async def test_model_builder_config_reverse_relationship(db_session: AsyncSession) -> None:
    """从 ModelBuilderConfig 可查 training_jobs 反向"""
    user = User(username="test3", email="test3@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    config = ModelBuilderConfig(name="cfg3", architecture_json={}, created_by=user.id)
    db_session.add(config)
    await db_session.flush()

    dataset = Dataset(name="ds3", path="/tmp/ds3", format="YOLO", created_by=user.id)
    db_session.add(dataset)
    await db_session.flush()

    line = ProductionLine(name="line3", created_by=user.id)
    db_session.add(line)
    await db_session.flush()

    job1 = TrainingJob(
        model_builder_config_id=config.id,
        dataset_id=dataset.id,
        production_line_id=line.id,
        hyperparams={},
        created_by=user.id,
    )
    job2 = TrainingJob(
        model_builder_config_id=config.id,
        dataset_id=dataset.id,
        production_line_id=line.id,
        hyperparams={},
        created_by=user.id,
    )
    db_session.add_all([job1, job2])
    await db_session.commit()

    result = await db_session.execute(
        select(ModelBuilderConfig)
        .where(ModelBuilderConfig.id == config.id)
        .options(selectinload(ModelBuilderConfig.training_jobs))
    )
    fetched_config = result.scalar_one()
    assert len(fetched_config.training_jobs) == 2


@pytest.mark.asyncio
async def test_model_builder_config_cascade_delete_training_jobs(db_session: AsyncSession) -> None:
    """删 ModelBuilderConfig 级联删 TrainingJob"""
    user = User(username="test4", email="test4@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()

    config = ModelBuilderConfig(name="cfg4", architecture_json={}, created_by=user.id)
    db_session.add(config)
    await db_session.flush()

    dataset = Dataset(name="ds4", path="/tmp/ds4", format="YOLO", created_by=user.id)
    db_session.add(dataset)
    await db_session.flush()

    line = ProductionLine(name="line4", created_by=user.id)
    db_session.add(line)
    await db_session.flush()

    job = TrainingJob(
        model_builder_config_id=config.id,
        dataset_id=dataset.id,
        production_line_id=line.id,
        hyperparams={},
        created_by=user.id,
    )
    db_session.add(job)
    await db_session.commit()

    await db_session.delete(config)
    await db_session.commit()

    result = await db_session.execute(select(TrainingJob).where(TrainingJob.id == job.id))
    assert result.scalar_one_or_none() is None
