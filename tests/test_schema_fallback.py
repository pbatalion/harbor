from src.intelligence.schema import deterministic_fallback_digest, validate_json_schema


def test_schema_validation_rejects_bad_payload() -> None:
    result = validate_json_schema({"unexpected": "shape"})
    assert result.valid is False


def test_fallback_contains_digest() -> None:
    payload = {"gmail_work": [{"subject": "Urgent issue"}]}
    fallback = deterministic_fallback_digest(payload)
    assert "email_digest" in fallback
    assert isinstance(fallback["urgent_items"], list)
