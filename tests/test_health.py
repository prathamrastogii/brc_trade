from app.api.health import health


def test_health_route() -> None:
    assert health() == {"status": "ok"}
