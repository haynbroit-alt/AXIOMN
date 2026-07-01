from fastapi.testclient import TestClient

from axiomn.api.main import app

client = TestClient(app)


def test_web_demo_is_served():
    response = client.get("/ui/")
    assert response.status_code == 200
    assert "AXIOMN" in response.text
    assert "/intent" in response.text
