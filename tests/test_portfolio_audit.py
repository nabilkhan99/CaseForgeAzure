import csv
import json
from types import SimpleNamespace

from app.models import CaseReviewResponse, CaseReviewSection
from app.services.portfolio_audit import PortfolioOutputAuditLogger
from app.services.portfolio_service import PortfolioService


def test_portfolio_output_audit_logger_appends_csv_rows(tmp_path):
    audit_path = tmp_path / "portfolio_outputs.csv"
    logger = PortfolioOutputAuditLogger(csv_path=str(audit_path))

    logger.record(
        operation="generate_review",
        model_deployment="gpt-4.1-mini",
        request_payload={
            "case_description": "Patient submitted notes",
            "selected_capabilities": ["Data gathering"],
        },
        output_text="Generated CCR output\nwith a second line",
        output_payload={"case_title": "Chest pain review"},
    )
    logger.record(
        operation="improve_section",
        model_deployment="gpt-4.1-mini",
        request_payload={"improvement_prompt": "Make it more reflective"},
        output_text="Improved reflection",
    )

    with audit_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert [row["operation"] for row in rows] == ["generate_review", "improve_section"]
    assert json.loads(rows[0]["request_json"])["case_description"] == "Patient submitted notes"
    assert rows[0]["output_text"] == "Generated CCR output\nwith a second line"
    assert json.loads(rows[0]["output_json"])["case_title"] == "Chest pain review"
    assert rows[0]["output_char_count"] == str(len("Generated CCR output\nwith a second line"))


def test_portfolio_service_records_case_review_output():
    recorded = []

    class FakeAuditLogger:
        def record(self, **kwargs):
            recorded.append(kwargs)

    service = PortfolioService.__new__(PortfolioService)
    service.settings = SimpleNamespace(azure_openai_deployment="gpt-4.1-mini")
    service.audit_logger = FakeAuditLogger()
    response = CaseReviewResponse(
        case_title="Chest pain review",
        review_content="Generated CCR output",
        sections=CaseReviewSection(
            brief_description="Brief",
            capabilities={"Data gathering": "Capability text"},
            reflection="Reflection",
            learning_needs="Learning needs",
        ),
    )

    service._record_portfolio_output(
        operation="generate_review",
        request_payload={"case_description": "Patient submitted notes"},
        output_text=response.review_content,
        output_payload=response,
    )

    assert recorded == [
        {
            "operation": "generate_review",
            "model_deployment": "gpt-4.1-mini",
            "request_payload": {"case_description": "Patient submitted notes"},
            "output_text": "Generated CCR output",
            "output_payload": response.model_dump(),
        }
    ]
