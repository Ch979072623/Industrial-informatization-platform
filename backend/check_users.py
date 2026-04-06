"""
检查用户列表
"""
import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import select
from app.models.user import User


async def check_users():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        print(f"共有 {len(users)} 个用户:")
        for u in users:
            print(f"  - {u.username} (ID: {u.id}): {u.role}")


if __name__ == "__main__":
    asyncio.run(check_users())
