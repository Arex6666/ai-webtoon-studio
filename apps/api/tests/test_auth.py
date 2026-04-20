"""
Authentication API tests
"""
import os
import pytest
from fastapi.testclient import TestClient


class TestAuthLogin:
    """Test /api/v1/auth/login endpoint"""

    def setup_method(self):
        """Setup test environment"""
        os.environ["ENABLE_AUTH"] = "false"
        os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"

    def test_login_missing_username(self, test_client):
        """Test login with missing username"""
        response = test_client.post(
            "/api/v1/auth/login",
            json={"password": "password"}
        )
        assert response.status_code == 422  # Validation error

    def test_login_missing_password(self, test_client):
        """Test login with missing password"""
        response = test_client.post(
            "/api/v1/auth/login",
            json={"username": "testuser"}
        )
        assert response.status_code == 422  # Validation error


class TestAuthMe:
    """Test /api/v1/auth/me endpoint"""

    def setup_method(self):
        """Setup test environment"""
        os.environ["ENABLE_AUTH"] = "false"
        os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"

    @pytest.mark.skip(reason="Requires database connection")
    def test_me_returns_user_info(self, test_client, test_user):
        """Test /me returns correct user info - requires database"""
        response = test_client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "username" in data


class TestAuthHealth:
    """Test health check endpoint"""

    def test_health_check(self, test_client):
        """Test root health check"""
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_endpoint(self, test_client):
        """Test root endpoint"""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
