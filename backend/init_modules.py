"""
初始化机器学习模块数据
"""
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.db.seeds.ml_modules_seed import seed_builtin_modules


async def init_modules():
    """初始化内置模块"""
    async with AsyncSessionLocal() as db:
        try:
            await seed_builtin_modules(db)
            print("✅ 模块初始化完成")
        except Exception as e:
            print(f"❌ 初始化失败: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(init_modules())
