def test_health_endpoint_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 201
    assert response.get_json() == {"status": "ok"}
