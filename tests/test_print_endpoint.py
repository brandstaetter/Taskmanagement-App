from unittest.mock import Mock, patch

from fastapi import Response
from fastapi.testclient import TestClient


def test_print_endpoint_success(client: TestClient) -> None:
    printer = Mock()
    printer.print.return_value = Response(content=b"ok", media_type="text/plain")

    with patch(
        "taskmanagement_app.api.v1.endpoints.print.PrinterFactory.create_printer",
        return_value=printer,
    ):
        response = client.post(
            "/api/v1/print/",
            json={
                "title": "T",
                "content": [{"description": "D"}],
                "printer_type": "pdf",
            },
        )

    assert response.status_code == 200
    assert response.content == b"ok"


def test_print_endpoint_error_returns_500(client: TestClient) -> None:
    with patch(
        "taskmanagement_app.api.v1.endpoints.print.PrinterFactory.create_printer",
        side_effect=RuntimeError("no printer"),
    ):
        response = client.post(
            "/api/v1/print/",
            json={
                "title": "T",
                "content": [{"description": "D"}],
                "printer_type": "pdf",
            },
        )

    assert response.status_code == 500
