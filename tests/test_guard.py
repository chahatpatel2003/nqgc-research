import datetime as dt
import pytest
from nqgc.guard import Access, HoldoutViolation, UNLOCK_PHRASE


def test_development_window_enforced(tmp_path, monkeypatch):
    import nqgc.guard as g
    monkeypatch.setattr(g, "RUNS_DIR", tmp_path)
    a = Access("development", "NQ")
    a.check_range("2021-01-04", "2023-12-31")
    with pytest.raises(HoldoutViolation):
        a.check_range("2023-01-01", "2024-01-02")
    assert a.clip("2020-01-01", "2030-01-01") == (dt.date(2021, 1, 4), dt.date(2023, 12, 31))


def test_validation_needs_spec(tmp_path, monkeypatch):
    import nqgc.guard as g
    monkeypatch.setattr(g, "RUNS_DIR", tmp_path)
    with pytest.raises(HoldoutViolation):
        Access("validation1", "NQ")
    Access("validation1", "NQ", spec_id="abc123")
    a2 = Access("validation2", "NQ", spec_id="abc123")
    assert a2.window() == (dt.date(2025, 1, 1), dt.date(2026, 6, 17)) and not a2.locked


def test_holdout_needs_spec_and_phrase(tmp_path, monkeypatch):
    import nqgc.guard as g
    monkeypatch.setattr(g, "RUNS_DIR", tmp_path)      # never write the real access log / holdout ledger from tests
    with pytest.raises(HoldoutViolation):
        Access("holdout", "GC", spec_id="abc")
    with pytest.raises(HoldoutViolation):
        Access("holdout", "GC", spec_id="abc", unlock="please")
    with pytest.raises(HoldoutViolation):
        Access("holdout", "NQ", spec_id="abc")
    a = Access("holdout", "GC", spec_id="abc", unlock=UNLOCK_PHRASE, purpose="unit test")
    assert a.window()[0] == dt.date(2025, 1, 1) and a.locked


def test_infrastructure_window_excludes_locked(tmp_path, monkeypatch):
    import nqgc.guard as g
    monkeypatch.setattr(g, "RUNS_DIR", tmp_path)
    a = Access("infrastructure", "NQ", purpose="unit test")
    assert a.window() == (dt.date(2021, 1, 4), dt.date(2026, 6, 17))
