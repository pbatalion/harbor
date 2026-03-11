from src.intelligence.claude import _parse_json_payload


def test_parse_json_payload_accepts_fenced_json() -> None:
    text = """```json
{
  \"source\": \"gmail_work\",
  \"summary\": \"ok\"
}
```"""
    parsed = _parse_json_payload(text)
    assert parsed["source"] == "gmail_work"


def test_parse_json_payload_extracts_embedded_json_object() -> None:
    text = "Here is the result:\n{\"urgent_items\": [], \"day_plan\": \"x\", \"email_digest\": {}}\nThanks"
    parsed = _parse_json_payload(text)
    assert parsed["day_plan"] == "x"
