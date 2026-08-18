import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_export_csv_has_full_headers():
    r = client.get("/api/analysis/feedback/export?format=csv&scope=all")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in r.headers.get("content-disposition", "")
    header = r.text.splitlines()[0]
    for col in ("conversation_id", "feedback_type", "user_remark", "category", "confidence",
                "what_happened", "why_it_happened", "how_to_avoid", "recommended_next_step",
                "ttft_ms", "input_tokens", "transcript_json"):
        assert col in header


def test_export_json_is_a_list_with_full_detail():
    r = client.get("/api/analysis/feedback/export?format=json&scope=all")
    assert r.status_code == 200
    rows = json.loads(r.text)
    assert isinstance(rows, list)
    if rows:  # fixtures may or may not contain feedback; guard the field check
        row = rows[0]
        for key in ("conversation_id", "category", "confidence", "feedback_type", "user_remark",
                    "what_happened", "why_it_happened", "how_to_avoid", "suggestions",
                    "recommended_next_step", "ttft_ms", "transcript"):
            assert key in row
        assert isinstance(row["transcript"], list)


def test_export_pdf_is_a_valid_pdf():
    r = client.get("/api/analysis/feedback/export?format=pdf&scope=all")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


def test_export_rejects_unknown_format():
    r = client.get("/api/analysis/feedback/export?format=xml")
    assert r.status_code == 422
