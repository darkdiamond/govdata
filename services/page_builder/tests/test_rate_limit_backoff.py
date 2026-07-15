"""429 detection for the between-attempt backoff in agent_runner."""
from services.page_builder.agent_runner import _is_rate_limited


class _FakeModelHTTPError(Exception):
    def __init__(self, status_code: int, msg: str = "provider error"):
        super().__init__(msg)
        self.status_code = status_code


def test_direct_429():
    assert _is_rate_limited(_FakeModelHTTPError(429))


def test_wrapped_429_via_cause():
    try:
        try:
            raise _FakeModelHTTPError(429)
        except Exception as inner:
            raise RuntimeError("session died") from inner
    except RuntimeError as outer:
        assert _is_rate_limited(outer)


def test_string_fallback():
    assert _is_rate_limited(Exception("status_code: 429, model_name: x"))


def test_non_429_http_error():
    assert not _is_rate_limited(_FakeModelHTTPError(500))


def test_unrelated_error():
    assert not _is_rate_limited(ValueError("Expecting value: line 621"))
