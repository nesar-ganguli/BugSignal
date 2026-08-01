import unittest

from fastapi.testclient import TestClient

from app.main import create_app


class OperationalHealthTests(unittest.TestCase):
    def test_liveness_echoes_or_generates_request_id(self) -> None:
        with TestClient(create_app()) as client:
            response = client.get("/health/live", headers={"X-Request-ID": "test-request-123"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["X-Request-ID"], "test-request-123")

    def test_unhandled_errors_return_safe_correlated_response(self) -> None:
        app = create_app()

        @app.get("/_test/error")
        async def raise_test_error() -> None:
            raise RuntimeError("internal secret")

        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/_test/error", headers={"X-Request-ID": "error-request-123"})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json(),
            {
                "detail": "An unexpected server error occurred.",
                "request_id": "error-request-123",
            },
        )
        self.assertNotIn("internal secret", response.text)


if __name__ == "__main__":
    unittest.main()
