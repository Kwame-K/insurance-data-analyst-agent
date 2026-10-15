from fastapi import FastAPI
from fastapi.testclient import TestClient

from insurance_data_analyst_agent.api.errors import register_exception_handlers
from insurance_data_analyst_agent.api.schemas import AnalyzeRequest
from insurance_data_analyst_agent.services.router import UnsupportedQuestionError


def build_client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/validate")
    def validate(payload: AnalyzeRequest) -> dict:
        return {"ok": True}

    @app.get("/unsupported")
    def unsupported() -> None:
        raise UnsupportedQuestionError("Question not supported.")

    @app.get("/missing-db")
    def missing_db() -> None:
        raise FileNotFoundError("/secret/path/insurance.db")

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return TestClient(app, raise_server_exceptions=False)


def test_validation_error_contract() -> None:
    response = build_client().post("/validate", json={"question": "x"})
    body = response.json()

    assert response.status_code == 422
    assert body["api_version"] == "v1"
    assert body["status"] == "error"
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]
    assert "X-Correlation-ID" in response.headers


def test_unsupported_question_returns_422() -> None:
    response = build_client().get("/unsupported")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_question"


def test_missing_database_does_not_leak_path() -> None:
    response = build_client().get("/missing-db")

    assert response.status_code == 503
    assert "/secret/path" not in response.text


def test_unexpected_error_does_not_leak_details() -> None:
    response = build_client().get("/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in response.text


def test_unknown_route_uses_error_contract() -> None:
    response = build_client().get("/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"
