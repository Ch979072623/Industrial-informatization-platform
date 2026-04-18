"""
CLI 脚本：手动同步模块定义到数据库

用法：
    python -m app.scripts.sync_modules

功能：
    扫描 app/ml/modules/atomic/*.json 和 app/ml/modules/composite/*/schema.json，
    全量 upsert 到 module_definitions 表，并清理已消失的旧 builtin 模块。
"""
import asyncio
import logging
import sys
from pathlib import Path

# 确保 backend 根目录在 PYTHONPATH 中
BACKEND_ROOT = Path(__file__).parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import AsyncSessionLocal
from app.ml.modules.registry import sync_builtin_modules

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("开始手动同步模块定义...")
    async with AsyncSessionLocal() as db:
        await sync_builtin_modules(db)
    logger.info("手动同步完成")


if __name__ == "__main__":
    asyncio.run(main())
