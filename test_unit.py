from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_missing_auth():
    resp = client.post("/parse", json={"file_url": "https://example.com/test.pdf"})
    print("Test Missing Auth Status:", resp.status_code)
    print("Test Missing Auth Response:", resp.json())
    assert resp.status_code == 401

def test_missing_file_url():
    resp = client.post("/parse", headers={"Authorization": "Bearer mock_token"}, json={})
    print("Test Missing file_url Status:", resp.status_code)
    print("Test Missing file_url Response:", resp.json())
    assert resp.status_code == 400 or resp.status_code == 422

def test_health():
    resp = client.get("/health")
    print("Test Health Status:", resp.status_code)
    print("Test Health Response:", resp.json())
    assert resp.status_code == 200

if __name__ == "__main__":
    test_missing_auth()
    test_missing_file_url()
    test_health()
    print("All unit tests passed successfully!")
