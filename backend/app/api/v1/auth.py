"""
认证相关 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate, UserLogin, UserResponse, UserUpdate
from app.schemas.token import Token, TokenRefresh, TokenRefreshResponse
from app.schemas.common import APIResponse
from app.core.security import TokenData

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=APIResponse[UserResponse])
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    用户注册
    
    - 默认注册为普通用户（user 角色）
    - 管理员需要通过其他方式创建
    """
    # 强制设置角色为 user
    user_data.role = "user"
    
    user = await AuthService.register(db, user_data)
    
    return APIResponse.success_response(
        data=UserResponse.model_validate(user),
        message="注册成功"
    )


@router.post("/login", response_model=APIResponse[Token])
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    用户登录
    
    - 返回访问令牌和刷新令牌
    - 访问令牌有效期30分钟
    - 刷新令牌有效期7天
    """
    user, tokens = await AuthService.login(db, login_data)
    
    return APIResponse.success_response(
        data=tokens,
        message="登录成功"
    )


@router.post("/refresh", response_model=APIResponse[TokenRefreshResponse])
async def refresh_token(refresh_data: TokenRefresh):
    """
    刷新访问令牌
    
    - 使用刷新令牌获取新的访问令牌
    - 刷新令牌只能使用一次（可选实现）
    """
    try:
        result = await AuthService.refresh_access_token(refresh_data.refresh_token)
        return APIResponse.success_response(
            data=TokenRefreshResponse(**result),
            message="令牌刷新成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"刷新令牌失败: {str(e)}"
        )


@router.get("/me", response_model=APIResponse[UserResponse])
async def get_current_user_info(
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户信息
    
    需要有效的访问令牌
    """
    user = await AuthService.get_user_by_id(db, current_user.user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return APIResponse.success_response(
        data=UserResponse.model_validate(user),
        message="获取成功"
    )


@router.put("/me", response_model=APIResponse[UserResponse])
async def update_current_user(
    update_data: UserUpdate,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新当前用户信息
    
    - 不能修改角色
    - 可以修改用户名、邮箱、密码
    """
    # 禁止修改角色
    update_data.role = None
    
    user = await AuthService.get_user_by_id(db, current_user.user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    updated_user = await AuthService.update_user(db, user, update_data)
    
    return APIResponse.success_response(
        data=UserResponse.model_validate(updated_user),
        message="更新成功"
    )


@router.post("/logout", response_model=APIResponse)
async def logout():
    """
    用户登出
    
    - 客户端需要删除本地存储的令牌
    - 可选：将令牌加入黑名单（需要 Redis 实现）
    """
    # TODO: 实现令牌黑名单
    return APIResponse.success_response(message="登出成功")
