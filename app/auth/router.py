"""
Authentication API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    UpdateRoleRequest,
    TokenResponse,
    UserResponse,
    RoleResponse,
)
from app.auth.service import (
    authenticate_user,
    register_user,
    create_access_token,
    get_all_users,
    update_user_role,
)
from fastapi.security import HTTPAuthorizationCredentials
from app.auth.dependencies import get_current_user, require_admin, security
from app.auth.models import User, Role

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a user and return a JWT access token.
    """
    try:
        user = authenticate_user(db, request.username, request.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
        
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role_name=user.role.name,
        clearance_level=user.role.clearance_level,
    )

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Revoke the active JWT access token to log out the user.
    """
    from app.auth.models import RevokedToken
    token = credentials.credentials
    # Add to revoked list if not already there
    existing = db.query(RevokedToken).filter(RevokedToken.token == token).first()
    if not existing:
        revoked = RevokedToken(token=token)
        db.add(revoked)
        db.commit()
    return {"message": "Successfully logged out"}


@router.post("/register", response_model=UserResponse)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Register a new user. Requires admin access.
    """
    try:
        user = register_user(
            db=db,
            username=request.username,
            email=request.email,
            password=request.password,
            role_name=request.role_name,
        )
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get the current authenticated user's profile.
    """
    return UserResponse.model_validate(current_user)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    List all users. Requires admin access.
    """
    users = get_all_users(db)
    return [UserResponse.model_validate(u) for u in users]


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def change_user_role(
    user_id: int,
    request: UpdateRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Update a user's role. Requires admin access.
    """
    try:
        user = update_user_role(db, user_id, request.role_name)
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all available roles.
    """
    roles = db.query(Role).all()
    return [RoleResponse.model_validate(r) for r in roles]
