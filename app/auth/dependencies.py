"""
FastAPI dependencies for authentication and authorization.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.auth.service import decode_access_token, get_user_by_id
from app.auth.models import User

# Bearer token security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that extracts and validates the JWT token,
    then returns the current authenticated User.
    """
    token = credentials.credentials
    
    # Check if token is blacklisted/revoked
    from app.auth.models import RevokedToken
    revoked = db.query(RevokedToken).filter(RevokedToken.token == token).first()
    if revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked (logged out)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload.get("sub", 0))
    user = get_user_by_id(db, user_id)

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    return user


def require_clearance(min_level: int):
    """
    Returns a dependency that checks if the user has at least
    the specified clearance level.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_clearance(3))])
    """

    async def check_clearance(user: User = Depends(get_current_user)):
        if user.role.clearance_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires clearance level {min_level}. You have {user.role.clearance_level}.",
            )
        return user

    return check_clearance


# Convenience shortcuts
require_admin = require_clearance(3)
require_manager = require_clearance(2)
