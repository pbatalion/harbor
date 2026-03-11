from src.privacy.redaction import redact_sensitive_payload


def test_redacts_token_and_ssn() -> None:
    payload = {
        "text": "token sk-test_12345678901 and ssn 123-45-6789",
        "nested": ["password: abc123"],
    }
    redacted = redact_sensitive_payload(payload, custom_terms=[])
    assert "sk-test_12345678901" not in redacted["text"]
    assert "123-45-6789" not in redacted["text"]
    assert "abc123" not in redacted["nested"][0]


def test_redacts_custom_terms() -> None:
    payload = {"text": "Project Falcon customer outage"}
    redacted = redact_sensitive_payload(payload, custom_terms=["Falcon"])
    assert "Falcon" not in redacted["text"]
