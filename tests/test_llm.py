import pytest

from dpdp_audit.llm import LLM, parse_json


def test_parse_json_handles_fences_and_prose():
    assert parse_json('Here:\n```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('result [1, 2] done') == [1, 2]
    with pytest.raises(ValueError):
        parse_json("no json here")


def test_cache_key_depends_on_seed():
    llm = LLM(backend="gemini", model="m")
    assert llm._key("s", "p", 0) != llm._key("s", "p", 1)


def test_gemini_key_rotation(monkeypatch):
    import pytest
    from dpdp_audit import llm as L
    monkeypatch.setenv("GEMINI_API_KEY", "k1")
    monkeypatch.setenv("GEMINI_API_KEYS", "k1, k2")
    pool = L.GeminiKeys()
    monkeypatch.setattr(pool, "clients", {"k1": "c1", "k2": "c2"})
    assert pool.current() == ("k1", "c1")
    pool.exhausted("k1")
    assert pool.current() == ("k2", "c2")
    pool.exhausted("k2")
    with pytest.raises(L.QuotaExhausted):
        pool.current()
    assert L.is_daily_quota("429 RESOURCE_EXHAUSTED ... Generate content requests per day limit")
    assert not L.is_daily_quota("429 RESOURCE_EXHAUSTED per minute")
