"""
安全相关模块
包含 JWT 认证、密码哈希、权限校验等功能
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uuid

from app.core.config import settings

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer 认证
security_bearer = HTTPBearer(auto_error=False)


class TokenData(BaseModel):
    """Token 数据模型"""
    user_id: Optional[str] = None
    username: Optional[str] = None
    role: Optional[str] = None
    production_line_id: Optional[str] = None


class TokenPair(BaseModel):
    """Token 对（访问令牌 + 刷新令牌）"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码
        
    Returns:
        验证是否通过
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    获取密码哈希
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码
    """
    return pwd_context.hash(password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建访问令牌
    
    Args:
        data: 要编码到令牌中的数据
        expires_delta: 过期时间增量
        
    Returns:
        JWT 访问令牌
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    
    # 添加标准声明
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
        "jti": str(uuid.uuid4())  # 唯一令牌标识
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm
    )
    return encoded_jwt


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建刷新令牌
    
    Args:
        data: 要编码到令牌中的数据
        expires_delta: 过期时间增量
        
    Returns:
        JWT 刷新令牌
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )
    
    # 刷新令牌只包含最少信息
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
        "jti": str(uuid.uuid4())
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm
    )
    return encoded_jwt


def create_token_pair(user_id: str, username: str, role: str, 
                     production_line_id: Optional[str] = None) -> TokenPair:
    """
    创建 Token 对（访问令牌 + 刷新令牌）
    
    Args:
        user_id: 用户ID
        username: 用户名
        role: 用户角色
        production_line_id: 产线ID
        
    Returns:
        TokenPair 对象
    """
    token_data = {
        "sub": user_id,
        "username": username,
        "role": role,
        "production_line_id": production_line_id
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": user_id})
    
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60
    )


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    解码 JWT 令牌
    
    Args:
        token: JWT 令牌
        
    Returns:
        解码后的载荷，失败返回 None
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        return payload
    except JWTError:
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """
    验证 JWT 令牌
    
    Args:
        token: JWT 令牌
        token_type: 令牌类型 (access/refresh)
        
    Returns:
        TokenData 对象，验证失败返回 None
    """
    payload = decode_token(token)
    
    if payload is None:
        return None
    
    # 验证令牌类型
    if payload.get("type") != token_type:
        return None
    
    # 验证过期时间
    exp = payload.get("exp")
    if exp is None or datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
        return None
    
    return TokenData(
        user_id=payload.get("sub"),
        username=payload.get("username"),
        role=payload.get("role"),
        production_line_id=payload.get("production_line_id")
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_bearer)
) -> TokenData:
    """
    获取当前用户（依赖函数）
    
    Args:
        credentials: HTTP Bearer 凭据
        
    Returns:
        TokenData 对象
        
    Raises:
        HTTPException: 认证失败时抛出
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = verify_token(credentials.credentials)
    
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_data


def require_roles(allowed_roles: List[str]):
    """
    角色权限校验装饰器
    
    Args:
        allowed_roles: 允许的角色列表
        
    Returns:
        依赖函数
    """
    async def role_checker(current_user: TokenData = Depends(get_current_user)) -> TokenData:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足，无法访问此资源"
            )
        return current_user
    return role_checker


# 预定义的权限校验依赖
require_admin = require_roles(["admin"])
require_user = require_roles(["user", "admin"])
