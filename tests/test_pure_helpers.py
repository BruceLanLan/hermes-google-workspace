"""Tests for pure helpers — no network, no Google client dependency."""

from datetime import timedelta

import pytest

from google_api import (
    _add_to_iso,
    _ensure_rfc3339_z_if_naive,
    _extract_gmail_body,
    _parse_duration,
)
from _gws_common import missing_scopes_from_payload
from scopes import SCOPES


class TestEnsureRFC3339:
    @pytest.mark.parametrize(
        "ts",
        [
            "2026-04-20T09:00:00Z",
            "2026-04-20T09:00:00-05:00",
            "2026-04-20T09:00:00+08:00",
            "2026-04-20",  # date only, untouched
        ],
    )
    def test_passthrough(self, ts):
        assert _ensure_rfc3339_z_if_naive(ts) == ts

    def test_naive_datetime_gets_z(self):
        assert _ensure_rfc3339_z_if_naive("2026-04-20T09:00:00") == "2026-04-20T09:00:00Z"

    def test_date_in_tz_offset_sign_not_confused(self):
        """A '-' in the date portion must NOT be treated as a timezone offset."""
        assert _ensure_rfc3339_z_if_naive("2026-04-20T09:00:00") == "2026-04-20T09:00:00Z"


class TestParseDuration:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("30m", timedelta(minutes=30)),
            ("1h", timedelta(hours=1)),
            ("2H", timedelta(hours=2)),
            ("1h30m", timedelta(hours=1, minutes=30)),
            ("  1H45M ", timedelta(hours=1, minutes=45)),
        ],
    )
    def test_valid(self, text, expected):
        assert _parse_duration(text) == expected

    @pytest.mark.parametrize("text", ["", "abc", "10", "1hx", "h", "30"])
    def test_invalid(self, text):
        with pytest.raises(ValueError):
            _parse_duration(text)


class TestAddToIso:
    def test_offset_preserved(self):
        out = _add_to_iso("2026-04-20T09:00:00-05:00", timedelta(minutes=30))
        assert out == "2026-04-20T09:30:00-05:00"

    def test_z_preserved(self):
        out = _add_to_iso("2026-04-20T09:00:00Z", timedelta(hours=1))
        assert out == "2026-04-20T10:00:00Z"

    def test_invalid(self):
        with pytest.raises(ValueError):
            _add_to_iso("not-a-date", timedelta(hours=1))


class TestExtractGmailBody:
    def test_single_part_plain(self):
        # Gmail uses URL-safe base64.
        import base64
        encoded = base64.urlsafe_b64encode(b"hello world").decode()
        payload = {"body": {"data": encoded}}
        assert _extract_gmail_body(payload) == "hello world"

    def test_prefers_plain_over_html(self):
        import base64
        plain = base64.urlsafe_b64encode(b"plain text").decode()
        html = base64.urlsafe_b64encode(b"<p>html</p>").decode()
        payload = {
            "parts": [
                {"mimeType": "text/html", "body": {"data": html}},
                {"mimeType": "text/plain", "body": {"data": plain}},
            ]
        }
        assert _extract_gmail_body(payload) == "plain text"

    def test_nested_multipart(self):
        import base64
        plain = base64.urlsafe_b64encode(b"deep plain").decode()
        payload = {
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": plain}},
                    ],
                }
            ]
        }
        assert _extract_gmail_body(payload) == "deep plain"


class TestMissingScopes:
    def test_all_present(self):
        payload = {"scopes": list(SCOPES)}
        assert missing_scopes_from_payload(payload) == []

    def test_missing_one(self):
        payload = {"scopes": [s for s in SCOPES if not s.endswith("/gmail.modify")]}
        missing = missing_scopes_from_payload(payload)
        assert missing == [s for s in SCOPES if s.endswith("/gmail.modify")]

    def test_string_scope(self):
        payload = {"scope": " ".join(SCOPES)}
        assert missing_scopes_from_payload(payload) == []

    def test_empty_payload(self):
        assert missing_scopes_from_payload({}) == []
