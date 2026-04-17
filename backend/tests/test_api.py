def test_read_root_404(client):
    response = client.get("/")
    assert response.status_code == 404

def test_get_modules_unauthorized(client):
    response = client.get("/modules")
    # Should be 401 Unauthorized
    assert response.status_code == 401

def test_login_and_get_modules(client):
    # 1. Login
    # Using admin credentials from seed (password set in seed.py)
    login_data = {"username": "admin@aneriam.com", "password": "adminpass"}
    response = client.post("/auth/login", json=login_data)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    token = data["access_token"]
    
    # 2. Get modules with token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/modules", headers=headers)
    assert response.status_code == 200
    modules = response.json()
    assert isinstance(modules, list)
    # Check if seed modules are present
    assert len(modules) >= 5
    # Verify sorting (module1 should be first, unless sort_order is different)
    assert modules[0]["key"] == "module1"

def test_login_failure(client):
    login_data = {"username": "admin@aneriam.com", "password": "wrongpassword123"}
    response = client.post("/auth/login", json=login_data)
    assert response.status_code == 401
