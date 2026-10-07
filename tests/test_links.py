from unittest.mock import patch

import pytest
from sqlalchemy import text


def create(client, url="https://example.com"):
    return client.post("/links", json={"url": url})


def count_rows(engine):
    with engine.connect() as conn:
        return conn.execute(text("SELECT count(*) FROM links")).scalar()


def test_create_link(client):
    response = create(client)
    assert response.status_code == 200
    body = response.json()
    assert len(body["code"]) == 6
    assert body["url"] == "https://example.com/"


def test_same_url_returns_same_code(client, engine):
    first = create(client).json()
    second = create(client).json()
    assert first["code"] == second["code"]
    assert count_rows(engine) == 1


def test_different_urls_get_different_codes(client):
    a = create(client, "https://example.com").json()
    b = create(client, "https://github.com").json()
    assert a["code"] != b["code"]


@pytest.mark.parametrize("payload", [{"url": "not a url"}, {}, {"url": 123}])
def test_bad_input_returns_400_and_stores_nothing(client, engine, payload):
    response = client.post("/links", json=payload)
    assert response.status_code == 400
    error = response.json()["detail"][0]
    assert error["field"] == "url"
    assert error["location"] == "body"
    assert count_rows(engine) == 0


def test_redirect_is_302_to_original_url(client):
    code = create(client).json()["code"]
    response = client.get(f"/links/{code}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/"


def test_following_link_counts_clicks(client):
    code = create(client).json()["code"]
    for _ in range(3):
        client.get(f"/links/{code}", follow_redirects=False)
    stats = client.get(f"/links/{code}/stats").json()
    assert stats["clicks"] == 3


def test_stats_does_not_count_as_click(client):
    code = create(client).json()["code"]
    for _ in range(5):
        client.get(f"/links/{code}/stats")
    assert client.get(f"/links/{code}/stats").json()["clicks"] == 0


@pytest.mark.parametrize("path", ["/links/doesnotexist", "/links/doesnotexist/stats"])
def test_unknown_code_returns_404(client, path):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 404
    assert response.json() == {"detail": "Short link not found"}


def test_code_collision_generates_another_code(client):
    first_code = create(client).json()["code"]

    # Force the generator to return the taken code first, then a fresh one.
    codes = iter([first_code, "fresh1"])
    with patch("app.main.generate_code", side_effect=lambda: next(codes)):
        response = create(client, "https://github.com")

    assert response.status_code == 200
    assert response.json()["code"] == "fresh1"

    # The original link was not overwritten.
    stats = client.get(f"/links/{first_code}/stats").json()
    assert stats["url"] == "https://example.com/"