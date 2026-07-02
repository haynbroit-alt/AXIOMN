from fastapi.testclient import TestClient

from axiomn.api.main import app

client = TestClient(app)


def test_web_demo_is_served():
    response = client.get("/ui/")
    assert response.status_code == 200
    assert "AXIOMN" in response.text
    assert "/intent" in response.text


def test_demo_has_voice_controls():
    text = client.get("/ui/").text
    assert 'id="mic"' in text  # speech-in
    assert "SpeechSynthesisUtterance" in text  # speech-out (voice_reply spoken)


def test_embeddable_widget_is_served():
    response = client.get("/ui/widget.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "data-axiomn-key" in response.text  # the documented embed contract
    assert "attachShadow" in response.text  # host-page CSS isolation


def test_cors_lets_third_party_origins_call_the_api():
    # The widget runs on other websites: the browser preflights /v1/intent
    # from that origin and must be told yes.
    response = client.options(
        "/v1/intent",
        headers={
            "Origin": "https://some-customer-site.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-api-key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "x-api-key" in response.headers["access-control-allow-headers"].lower()
