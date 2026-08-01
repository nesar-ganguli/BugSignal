import unittest
from unittest.mock import patch

from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app
from app.schemas.project_schema import ProjectCreate
from app.services.rate_limit_service import enforce_expensive_rate_limit


class FakeRedis:
    def __init__(self, result: list[int]):
        self.result = result
        self.closed = False

    def eval(self, *args):
        return self.result

    def close(self) -> None:
        self.closed = True


class SecurityControlTests(unittest.TestCase):
    def test_security_headers_and_untrusted_hosts(self) -> None:
        with TestClient(create_app()) as client:
            healthy = client.get("/health/live")
            rejected = client.get("/health/live", headers={"Host": "evil.example"})

        self.assertEqual(healthy.status_code, 200)
        self.assertEqual(healthy.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(healthy.headers["X-Frame-Options"], "DENY")
        self.assertEqual(rejected.status_code, 400)

    def test_oversized_request_is_rejected_before_routing(self) -> None:
        settings = Settings(max_request_size_bytes=10)
        with patch("app.main.get_settings", return_value=settings):
            with TestClient(create_app()) as client:
                response = client.post(
                    "/not-important",
                    content=b"01234567890",
                    headers={"Content-Type": "application/octet-stream"},
                )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["detail"], "Request body is too large.")

    def test_production_disables_docs_and_enables_hsts(self) -> None:
        settings = Settings(environment="production", allowed_hosts="testserver")
        with patch("app.main.get_settings", return_value=settings):
            with TestClient(create_app()) as client:
                docs = client.get("/docs")
                live = client.get("/health/live")

        self.assertEqual(docs.status_code, 404)
        self.assertIn("max-age=31536000", live.headers["Strict-Transport-Security"])

    def test_project_name_and_slug_are_strict(self) -> None:
        with self.assertRaises(ValidationError):
            ProjectCreate(name="   ", slug="valid-slug")
        with self.assertRaises(ValidationError):
            ProjectCreate(name="Valid", slug="Invalid Slug")

    def test_expensive_rate_limit_returns_retry_after(self) -> None:
        settings = Settings(expensive_rate_limit_requests=1)
        fake_redis = FakeRedis([2, 37])
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/workflows/ticket-processing",
                "headers": [(b"x-project-id", b"7")],
                "client": ("127.0.0.1", 1234),
                "scheme": "http",
                "server": ("testserver", 80),
                "query_string": b"",
            }
        )
        with (
            patch("app.services.rate_limit_service.get_settings", return_value=settings),
            patch("app.services.rate_limit_service.Redis.from_url", return_value=fake_redis),
            self.assertRaises(HTTPException) as raised,
        ):
            enforce_expensive_rate_limit(request)

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(raised.exception.headers["Retry-After"], "37")
        self.assertTrue(fake_redis.closed)


if __name__ == "__main__":
    unittest.main()
