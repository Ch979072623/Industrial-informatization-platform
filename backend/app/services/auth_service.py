"""
认证服务模块
处理用户认证相关的业务逻辑
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.user import User
from app.core.security import (
    verify_password,
    get_password_hash,
    create_token_pair,
    verify_token
)
from app.schemas.user import UserCreate, UserLogin, UserUpdate
from app.schemas.token import Token, TokenRefresh


class AuthService:
    """认证服务类"""
    
    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        username: str,
        password: str
    ) -> Optional[User]:
        """
        验证用户凭据
        
        Args:
            db: 数据库会话
            username: 用户名
            password: 密码
            
        Returns:
            验证成功返回用户对象，失败返回 None
        """
        result = await db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        if not user.is_active:
            return None
        
        return user
    
    @staticmethod
    async def login(
        db: AsyncSession,
        login_data: UserLogin
    ) -> tuple[User, Token]:
        """
        用户登录
        
        Args:
            db: 数据库会话
            login_data: 登录数据
            
        Returns:
            (用户对象, Token对)
            
        Raises:
            HTTPException: 认证失败时抛出
        """
        user = await AuthService.authenticate_user(
            db, login_data.username, login_data.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 创建 Token 对
        tokens = create_token_pair(
            user_id=user.id,
            username=user.username,
            role=user.role,
            production_line_id=user.production_line_id
        )
        
        return user, tokens
    
    @staticmethod
    async def register(
        db: AsyncSession,
        user_data: UserCreate
    ) -> User:
        """
        用户注册
        
        Args:
            db: 数据库会话
            user_data: 用户创建数据
            
        Returns:
            创建的用户对象
            
        Raises:
            HTTPException: 用户名或邮箱已存在时抛出
        """
        # 检查用户名是否已存在
        result = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        
        # 检查邮箱是否已存在
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )
        
        # 创建用户
        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            role=user_data.role,
            production_line_id=user_data.production_line_id
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        return user
    
    @staticmethod
    async def refresh_access_token(
        refresh_token: str
    ) -> dict:
        """
        刷新访问令牌
        
        Args:
            refresh_token: 刷新令牌
            
        Returns:
            包含新访问令牌的字典
            
        Raises:
            HTTPException: 令牌无效时抛出
        """
        from app.core.security import create_access_token, settings
        
        # 验证刷新令牌
        token_data = verify_token(refresh_token, token_type="refresh")
        
        if not token_data or not token_data.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的刷新令牌",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # 创建新的访问令牌（只包含用户ID）
        new_access_token = create_access_token(
            data={"sub": token_data.user_id}
        )
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60
        }
    
    @staticmethod
    async def get_user_by_id(
        db: AsyncSession,
        user_id: str
    ) -> Optional[User]:
        """
        根据ID获取用户
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            
        Returns:
            用户对象或 None
        """
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_user(
        db: AsyncSession,
        user: User,
        update_data: UserUpdate
    ) -> User:
        """
        更新用户信息
        
        Args:
            db: 数据库会话
            user: 用户对象
            update_data: 更新数据
            
        Returns:
            更新后的用户对象
        """
        update_dict = update_data.model_dump(exclude_unset=True)
        
        # 如果更新密码，需要哈希
        if "password" in update_dict and update_dict["password"]:
            update_dict["hashed_password"] = get_password_hash(update_dict.pop("password"))
        
        for field, value in update_dict.items():
            setattr(user, field, value)
        
        await db.commit()
        await db.refresh(user)
        return user
