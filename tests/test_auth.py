"""
Tests for authentication service and API.
"""
import pytest
from app.auth.service import hash_password, verify_password, create_access_token, decode_access_token


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "test_password_123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password(self):
        hashed = hash_password("correct_password")
        assert not verify_password("wrong_password", hashed)

    def test_different_hashes(self):
        pwd = "same_password"
        hash1 = hash_password(pwd)
        hash2 = hash_password(pwd)
        assert hash1 != hash2  # bcrypt uses random salt


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(
            user_id=1, username="testuser", role_name="admin", clearance_level=3
        )
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["username"] == "testuser"
        assert payload["role"] == "admin"
        assert payload["clearance_level"] == 3

    def test_invalid_token(self):
        payload = decode_access_token("invalid.token.here")
        assert payload is None

    def test_token_contains_expiry(self):
        token = create_access_token(
            user_id=1, username="test", role_name="employee", clearance_level=1
        )
        payload = decode_access_token(token)
        assert "exp" in payload
        assert "iat" in payload
