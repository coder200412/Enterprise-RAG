"""
Tests for security hardening features:
- Password strength validator
- Brute force login lockout
- JWT Token revocation checks
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from app.auth.service import validate_password_strength, authenticate_user, register_user
from app.auth.dependencies import get_current_user
from app.auth.models import User, RevokedToken, Role


def test_password_strength_validator():
    # Valid password
    validate_password_strength("StrongPass123!")
    
    # Too short
    with pytest.raises(ValueError, match="Password must be at least 8 characters long"):
        validate_password_strength("Wea1!")
        
    # No uppercase
    with pytest.raises(ValueError, match="Password must contain at least one uppercase letter"):
        validate_password_strength("weakpass123!")
        
    # No lowercase
    with pytest.raises(ValueError, match="Password must contain at least one lowercase letter"):
        validate_password_strength("WEAKPASS123!")
        
    # No number
    with pytest.raises(ValueError, match="Password must contain at least one digit"):
        validate_password_strength("WeakPass!")
        
    # No special character
    with pytest.raises(ValueError, match="Password must contain at least one special character"):
        validate_password_strength("WeakPass123")


@patch("app.auth.service.verify_password")
def test_login_brute_force_lockout(mock_verify):
    """Test that 5 failed login attempts locks the user account."""
    db_mock = MagicMock()
    user_mock = MagicMock()
    user_mock.is_active = True
    user_mock.failed_login_attempts = 4
    user_mock.lockout_until = None
    user_mock.created_at = datetime.now()

    db_mock.query.return_value.filter.return_value.first.return_value = user_mock
    mock_verify.return_value = False  # Always wrong password

    # 5th attempt should lock the account and raise ValueError
    with pytest.raises(ValueError, match="Too many failed login attempts"):
        authenticate_user(db_mock, "testuser", "wrongpassword")

    assert user_mock.failed_login_attempts == 5
    assert user_mock.lockout_until is not None
    db_mock.commit.assert_called()


def test_login_locked_account_rejection():
    """Test that locked account rejects login immediately without checking password."""
    db_mock = MagicMock()
    user_mock = MagicMock()
    user_mock.is_active = True
    user_mock.failed_login_attempts = 5
    # Locked until 10 minutes in the future
    user_mock.lockout_until = datetime.now() + timedelta(minutes=10)

    db_mock.query.return_value.filter.return_value.first.return_value = user_mock

    with pytest.raises(ValueError, match="Account is temporarily locked"):
        authenticate_user(db_mock, "testuser", "anypassword")


@pytest.mark.anyio
@patch("app.auth.dependencies.decode_access_token")
@patch("app.auth.dependencies.get_user_by_id")
async def test_get_current_user_revoked_token_rejection(mock_get_user, mock_decode):
    """Verify that get_current_user raises 401 when token is revoked."""
    db_mock = MagicMock()
    cred_mock = MagicMock()
    cred_mock.credentials = "revoked_token_123"

    # Simulate token is present in RevokedToken table
    mock_revoked = MagicMock()
    db_mock.query.return_value.filter.return_value.first.return_value = mock_revoked

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(credentials=cred_mock, db=db_mock)

    assert exc_info.value.status_code == 401
    assert "revoked" in exc_info.value.detail
    
    # decode_access_token should not be called since it gets blocked early
    mock_decode.assert_not_called()
