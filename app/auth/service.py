"""
Authentication service — password hashing, JWT tokens, user management.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.auth.models import User, Role


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(user_id: int, username: str, role_name: str, clearance_level: int) -> str:
    """
    Create a JWT access token containing user identity and role info.
    """
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role_name,
        "clearance_level": clearance_level,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token. Returns the payload dict or None if invalid.
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user by username and password.
    Returns the User object if valid, None otherwise.
    Raises ValueError if the account is currently locked.
    """
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        return None

    # Check lockout status
    if user.lockout_until:
        # Compare with timezone-naive datetime since SQLite/PostgreSQL columns might be naive
        now = datetime.now()
        # If user.lockout_until has timezone, make now timezone-aware
        if user.lockout_until.tzinfo is not None:
            now = datetime.now(timezone.utc)
            
        if user.lockout_until > now:
            lock_remaining = int((user.lockout_until - now).total_seconds())
            minutes = max(1, lock_remaining // 60)
            raise ValueError(f"Account is temporarily locked. Please try again in {minutes} minutes.")

    if not verify_password(password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            # Set lockout for 15 minutes
            now = datetime.now() if user.created_at.tzinfo is None else datetime.now(timezone.utc)
            user.lockout_until = now + timedelta(minutes=15)
            db.commit()
            raise ValueError("Too many failed login attempts. Account locked for 15 minutes.")
        db.commit()
        return None

    # Reset attempts on successful login
    user.failed_login_attempts = 0
    user.lockout_until = None
    db.commit()
    return user


import re

def validate_password_strength(password: str) -> None:
    """Validate password complexity requirements."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValueError("Password must contain at least one special character")


def register_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    role_name: str = "employee",
) -> User:
    """
    Register a new user with the specified role.
    Raises ValueError if username/email already exists, role not found,
    or password does not meet complexity requirements.
    """
    # Enforce password complexity
    validate_password_strength(password)

    # Check for existing user
    existing = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()
    if existing:
        raise ValueError("Username or email already registered")

    # Find the role
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise ValueError(f"Role '{role_name}' does not exist")

    # Create user
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role_id=role.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Retrieve a user by their ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_all_users(db: Session) -> list[User]:
    """Retrieve all users."""
    return db.query(User).all()


def update_user_role(db: Session, user_id: int, role_name: str) -> User:
    """
    Change a user's role.
    Raises ValueError if user or role not found.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise ValueError(f"Role '{role_name}' does not exist")

    user.role_id = role.id
    db.commit()
    db.refresh(user)
    return user
