"""
Test configuration and fixtures - simplified version
"""
import os
import sys
import pytest
from fastapi.testclient import TestClient

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app"""
    # Set test environment before importing app
    os.environ["ENABLE_AUTH"] = "false"
    os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"

    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture
def test_user():
    """Return a test user dict"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "name": "Test User"
    }
