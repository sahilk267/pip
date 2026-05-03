from __future__ import annotations

import threading
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth.utils import create_access_token, decode_token, get_password_hash, verify_password
from ..auth.schemas import PasswordChange, Token, UserLogin, UserRegister, UserResponse
from ..auth.user_model import User
from ..services import email_service

router = APIRouter(prefix='/api/v1/auth', tags=['auth'])
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
    payload = decode_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid or expired token')
    user_id = payload.get('sub')
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token payload')
    user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found or inactive')
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Admin access required')
    return current_user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    user_id = payload.get('sub')
    if not user_id:
        return None
    return db.query(User).filter(User.id == int(user_id), User.is_active == True).first()


@router.post('/register', response_model=Token, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> Token:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail='Email already registered')
    allowed_roles = {'admin', 'sales_rep', 'customer', 'vendor'}
    if payload.role not in allowed_roles:
        raise HTTPException(status_code=400, detail=f'Role must be one of: {", ".join(sorted(allowed_roles))}')
    user = User(
        email=payload.email.lower(),
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create_access_token({'sub': str(user.id), 'email': user.email, 'role': user.role})
    # Send welcome email in background (non-blocking)
    threading.Thread(
        target=email_service.send_welcome_email,
        args=(user.email, user.full_name or user.email, user.role),
        daemon=True,
    ).start()
    return Token(access_token=token, user=UserResponse.model_validate(user))


@router.post('/login', response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid email or password')
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Account is disabled')
    token = create_access_token({'sub': str(user.id), 'email': user.email, 'role': user.role})
    return Token(access_token=token, user=UserResponse.model_validate(user))


@router.get('/me', response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch('/me/password', response_model=UserResponse)
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserResponse:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail='Current password is incorrect')
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.get('/users', response_model=list[UserResponse])
def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserResponse]:
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse.model_validate(u) for u in users]
