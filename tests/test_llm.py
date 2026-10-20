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
