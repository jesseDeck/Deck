from __future__ import annotations

from openrouter_savings.openrouter_client import parse_endpoint


def test_parse_endpoint_reads_known_field_names() -> None:
    raw = {
        "provider_name": "azure",
        "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
        "uptime_last_30m": 99.8,
    }
    endpoint = parse_endpoint(raw)
    assert endpoint.provider == "azure"
    assert endpoint.prompt_price == 0.0000025
    assert endpoint.completion_price == 0.00001
    assert endpoint.uptime_pct == 99.8


def test_parse_endpoint_is_defensive_about_missing_fields() -> None:
    raw = {"pricing": {}}
    endpoint = parse_endpoint(raw)
    assert endpoint.provider == "unknown"
    assert endpoint.prompt_price is None
    assert endpoint.completion_price is None
    assert endpoint.uptime_pct is None


def test_parse_endpoint_falls_back_across_alternate_keys() -> None:
    raw = {"name": "together", "pricing": {"prompt": 0.000001, "completion": 0.000002}, "uptime": 95.0}
    endpoint = parse_endpoint(raw)
    assert endpoint.provider == "together"
    assert endpoint.uptime_pct == 95.0
