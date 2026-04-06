"""
检查数据集列表
"""
import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models.dataset import Dataset


async def check_datasets():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Dataset))
        datasets = result.scalars().all()
        print(f"共有 {len(datasets)} 个数据集:")
        for d in datasets:
            print(f"  - {d.name}: {d.total_images}张图片, 格式={d.format}, 创建者={d.created_by}")


if __name__ == "__main__":
    asyncio.run(check_datasets())
