"""
Alembic 迁移环境配置
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# 导入应用配置和模型
from app.core.config import settings
from app.db.base import Base
from app.models import *  # 导入所有模型

# Alembic Config 对象
config = context.config

# 从配置文件中设置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 设置目标元数据
# 这是 Alembic 自动检测模型变化的基础
target_metadata = Base.metadata

# 从环境变量获取数据库 URL
def get_url():
    """获取数据库 URL"""
    return settings.database_url


def run_migrations_offline() -> None:
    """
    离线运行迁移
    
    使用 --sql 标志时调用，直接输出 SQL 而不连接数据库
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """执行迁移"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # 比较列类型变化
        compare_server_default=True,  # 比较默认值
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步运行迁移"""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    在线运行迁移
    
    默认模式，连接数据库并执行迁移
    """
    asyncio.run(run_async_migrations())


# 根据运行模式选择迁移方式
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
