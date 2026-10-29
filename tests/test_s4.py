"""S4: tool statements mapped to the taggers' claims (WP-3.6)."""
import json

import pytest

from dpdp_audit import s4
from dpdp_audit.tagger_eval import evaluate_tuples


@pytest.mark.parametrize("term,value", [
    ("email address", "Contact"), ("person name", "Contact"), ("user name", "User profile"),
    ("ip address", "IP address and device IDs"), ("device identifier", "IP address and device IDs"),
    ("cookie / pixel tag", "Cookies and tracking elements"), ("geographical location", "Location"),
    ("zip code", "Location"), ("credit card number", "Financial"), ("browser type", "Computer information"),
    ("usage information", "User online activities"), ("age", "Demographic"), ("page", "Other"),
    ("account information", "User profile"), ("pii", "Generic personal information"),
    ("personal information", "Generic personal information"), ("information", "Unspecified"),
    ("UNSPECIFIED_DATA", "Unspecified"), ("social security number", "Personal identifier"),
    ("survey response", "Survey data"), ("medical history", "Health"), ("facebook profile", "Social media data"),
])
def test_data_terms_follow_the_opp115_definitions(term, value):
    assert s4.map_term(term, "data") == value


@pytest.mark.parametrize("term,value", [
    ("we", "first party"), ("third party", "Unnamed third party"), ("partners", "Unnamed third party"),
    ("advertiser", "Named third party"), ("google", "Named third party"),
    ("analytic provider", "Named third party"), ("affiliates", "Other part of company/affiliate"),
    ("other users", "Other users"), ("public", "Public"),
])
def test_entity_terms_follow_the_opp115_definitions(term, value):
    assert s4.map_term(term, "entity") == value


def test_statements_become_claims():
    assert s4.to_claim("we", False, "email address") == {
        "category": s4.FIRST, "data_type": "Contact", "does": "Does Not", "third_party": ""}
    assert s4.to_claim("advertiser", True, "ip address") == {
        "category": s4.THIRD, "data_type": "IP address and device IDs", "does": "Does",
        "third_party": "Named third party"}


def test_policylint_reader(tmp_path):
    p = tmp_path / "pl.json"
    p.write_text(json.dumps({"segments": {
        "s4_1028_3": {"raw": [["we", "collect", "email", "s", "collect"]],
                      "statements": [["we", "collect", "email address", "We collect your email."]]},
        "s4_1028_4": {"raw": [], "statements": []}}, "ontology": {}}))
    claims, stats = s4.policylint_claims(p)
    assert claims[("1028", 3)][0]["data_type"] == "Contact" and claims[("1028", 4)] == []
    assert stats == {"segments": 2, "statements": 1, "raw_statements": 1}


def test_poligraph_sentences_go_to_the_segments_that_contain_them(tmp_path):
    segs = [{"policy_id": "7", "segment_id": 0, "text": "We collect your e-mail address.\nMore text."},
            {"policy_id": "7", "segment_id": 1, "text": "We share cookies with advertisers."}]
    p = tmp_path / "pg.json"
    p.write_text(json.dumps({"7": [
        {"source": "we", "target": "email address", "key": "COLLECT", "text": ["We collect your e-mail address."]},
        {"source": "advertiser", "target": "cookie", "key": "COLLECT", "text": ["We share cookies with advertisers."]},
        {"source": "UNSPECIFIED_ACTOR", "target": "ip address", "key": "COLLECT", "text": ["x"]},
        {"source": "personal information", "target": "email address", "key": "SUBSUME", "text": []},
        {"source": "we", "target": "location", "key": "COLLECT", "text": ["Not in any segment."]}]}))
    claims, stats = s4.poligraph_claims(segs, p)
    assert [c["data_type"] for c in claims[("7", 0)]] == ["Contact"]
    assert claims[("7", 1)][0]["third_party"] == "Named third party"
    assert stats["no_actor_edges"] == 1 and stats["sentences_unmatched"] == 1 and stats["collect_edges"] == 4


def test_tools_are_scored_like_the_taggers():
    gold = [{"policy_id": "7", "segment_id": 0, "claims": [s4.to_claim("we", True, "email address")]},
            {"policy_id": "7", "segment_id": 1, "claims": []}]
    pred = s4.as_predictions(gold, {("7", 0): [s4.to_claim("we", True, "email")],
                                    ("7", 1): [s4.to_claim("we", True, "location")]})
    r = evaluate_tuples(gold, pred)
    assert r["tuple_does"]["precision"] == 0.5 and r["tuple_does"]["recall"] == 1.0
