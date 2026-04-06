"""
创建管理员用户的脚本
用法: python create_admin.py
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate


async def create_admin_user():
    """创建管理员用户"""
    # 管理员用户信息（可以修改）
    admin_data = UserCreate(
        username="admin",
        email="admin@example.com",
        password="admin123",
        role="admin",
        production_line_id=None
    )
    
    async with AsyncSessionLocal() as db:
        try:
            # 检查用户是否已存在
            from app.models.user import User
            from sqlalchemy import select
            
            result = await db.execute(
                select(User).where(User.username == admin_data.username)
            )
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"[警告] 用户 '{admin_data.username}' 已存在")
                if existing_user.role != "admin":
                    print(f"   当前角色: {existing_user.role}")
                    response = input("   是否升级为管理员? (y/n): ")
                    if response.lower() == 'y':
                        existing_user.role = "admin"
                        await db.commit()
                        print(f"[成功] 用户 '{admin_data.username}' 已升级为管理员")
                return
            
            # 创建管理员用户
            user = await AuthService.register(db, admin_data)
            print("[成功] 管理员用户创建成功!")
            print(f"   用户名: {user.username}")
            print(f"   邮箱: {user.email}")
            print(f"   角色: {user.role}")
            print(f"   密码: admin123")
            
        except Exception as e:
            print(f"[错误] 创建失败: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    print("=" * 50)
    print("创建管理员用户")
    print("=" * 50)
    
    # 支持命令行参数自定义
    if len(sys.argv) > 1:
        print("用法: python create_admin.py")
        print("或直接编辑脚本修改默认账号密码")
        sys.exit(1)
    
    asyncio.run(create_admin_user())
