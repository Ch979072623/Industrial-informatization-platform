"""
用户管理 API 路由（管理员功能）
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.schemas.common import APIResponse, PaginatedResponse, PaginationParams
from app.models.user import User
from app.core.security import TokenData, require_roles

router = APIRouter(
    prefix="/users", 
    tags=["用户管理"], 
    dependencies=[Depends(require_roles(["admin"]))]
)


@router.get("", response_model=APIResponse[PaginatedResponse[UserResponse]])
async def list_users(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户列表（管理员）
    """
    # 获取总数
    count_result = await db.execute(select(User))
    total = len(count_result.scalars().all())
    
    # 获取分页数据
    result = await db.execute(
        select(User)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    users = result.scalars().all()
    
    user_responses = [UserResponse.model_validate(user) for user in users]
    
    return APIResponse.success_response(
        data=PaginatedResponse.create(
            items=user_responses,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )
    )


@router.post("", response_model=APIResponse[UserResponse])
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    创建用户（管理员可以指定角色）
    """
    user = await AuthService.register(db, user_data)
    
    return APIResponse.success_response(
        data=UserResponse.model_validate(user),
        message="用户创建成功"
    )


@router.get("/{user_id}", response_model=APIResponse[UserResponse])
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取用户详情（管理员）
    """
    user = await AuthService.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return APIResponse.success_response(
        data=UserResponse.model_validate(user)
    )


@router.put("/{user_id}", response_model=APIResponse[UserResponse])
async def update_user(
    user_id: str,
    update_data: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    更新用户信息（管理员）
    """
    user = await AuthService.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    updated_user = await AuthService.update_user(db, user, update_data)
    
    return APIResponse.success_response(
        data=UserResponse.model_validate(updated_user),
        message="用户更新成功"
    )


@router.delete("/{user_id}", response_model=APIResponse)
async def delete_user(
    user_id: str,
    current_user: TokenData = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    删除用户（管理员）
    
    - 不能删除自己
    """
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除当前登录用户"
        )
    
    user = await AuthService.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    await db.delete(user)
    await db.commit()
    
    return APIResponse.success_response(message="用户删除成功")
