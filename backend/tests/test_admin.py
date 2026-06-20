from fastapi import status
from app.models.user import User


def test_create_admin_user(client):
    """Test creating an admin user"""
    response = client.post(
        "/api/v1/admin/",
        json={
            "email": "test@example.com",
            "password": "testpassword123",
            "username": "testuser",
            "full_name": "Test User",
            "is_admin": true
        }
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["is_admin"] == true
    assert data["is_active"] == true
    assert data["is_verified"] == false


def test_get_users(client):
    """Test getting users"""
    response = client.get("/api/v1/admin/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    # Should have at least the admin user we created
    assert len(data) >= 1


def test_get_system_stats(client):
    """Test getting system stats"""
    response = client.get("/api/v1/admin/stats/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "total_users" in data
    assert "admin_users" in data
    assert "active_users" in data