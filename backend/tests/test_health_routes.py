import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app import routes
from app.main import app, root


def test_health_check_preserves_existing_response():
    response = routes.health_check()

    assert response == {
        "status": "ok",
        "service": "hetren-api",
    }


def test_liveness_check_reports_api_process_alive():
    response = routes.liveness_check()

    assert response == {
        "status": "ok",
        "service": "hetren-api",
        "check": "liveness",
    }


def test_readiness_check_reports_database_reachable(monkeypatch):
    monkeypatch.setattr(
        routes,
        "check_database_connection",
        lambda: None,
    )

    response = routes.readiness_check()

    assert response == {
        "status": "ready",
        "service": "hetren-api",
        "database": "reachable",
    }


def test_readiness_check_returns_503_when_database_is_unavailable(
    monkeypatch,
):
    def raise_database_error():
        raise SQLAlchemyError("Database connection failed")

    monkeypatch.setattr(
        routes,
        "check_database_connection",
        raise_database_error,
    )

    with pytest.raises(HTTPException) as error:
        routes.readiness_check()

    assert error.value.status_code == 503
    assert error.value.detail == "Database is unavailable"

def test_fastapi_metadata_uses_hetren_brand():
    assert app.title == "Hetren API"


def test_root_endpoint_uses_hetren_brand():
    assert root() == {
        "message": "Hetren backend is running",
        "version": "0.1.0",
    }
