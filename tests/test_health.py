"""
Health Check Tests
"""


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "AI Study Companion API"
    assert data["status"] == "operational"


def test_health_endpoint(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data


def test_health_endpoint_returns_503_when_database_unhealthy(client, monkeypatch):
    """When check_database_connection() fails, /health must report 503
    (not 200) so upstream health checks/load balancers can detect it."""
    monkeypatch.setattr("src.api.main.check_database_connection", lambda: False)

    response = client.get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["database"] == "disconnected"
