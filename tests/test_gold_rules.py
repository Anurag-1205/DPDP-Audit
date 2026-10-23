from dpdp_audit import gold_rules as g
from dpdp_audit.opp115 import Policy, Practice


def practice(cat, **attrs):
    spans = attrs.pop("spans", {})
    return Practice("p", 0, cat, attrs, spans)


POLICY = Policy("p", "demo", ["seg"], [
    practice(g.FIRST_PARTY, **{"Personal Information Type": "Location", "Purpose": "Basic service/feature",
                               "Does/Does Not": "Does"}),
    practice(g.FIRST_PARTY, **{"Personal Information Type": "Health", "Does/Does Not": "Does Not"}),
    practice(g.FIRST_PARTY, **{"Personal Information Type": "Generic personal information",
                               "Purpose": "Unspecified", "Does/Does Not": "Does"}),
    practice(g.THIRD_PARTY_SHARING, **{"Personal Information Type": "IP address and device IDs",
                                       "Third Party Entity": "Named third party", "Purpose": "Advertising",
                                       "Does/Does Not": "Does", "spans": {"Third Party Entity": "Google"}}),
    practice(g.THIRD_PARTY_SHARING, **{"Personal Information Type": "Location", "Does/Does Not": "Does Not"}),
    practice(g.RETENTION, **{"Personal Information Type": "Generic personal information",
                             "Retention Period": "Stated Period"}),
    practice(g.AUDIENCES, **{"Audience Type": "Children"}),
])
COV = g.build_coverage(POLICY)


def test_collection_levels():
    assert g.collection_level(COV, "Location") is None
    assert g.collection_level(COV, "Health") == "explicit"
    assert g.collection_level(COV, "Contact") == "vague"      # generic collection exists


def test_sharing_levels():
    assert g.sharing_level(COV, "IP address and device IDs", "admob") is None   # Google named
    assert g.sharing_level(COV, "IP address and device IDs", "mixpanel") == "vague"
    assert g.sharing_level(COV, "Location", "admob") == "explicit"


def test_purpose_retention_children():
    assert g.purpose_level(COV, "Location", "first_party", "Advertising") == "omission"
    assert g.retention_level(COV, "Location", "Indefinitely") == "explicit"
    assert g.children_level(COV, True, "admob") == "explicit"
    assert g.children_level(COV, True, "sentry") is None


def test_answer_key_for_control_and_variant():
    control = [{"flow_id": "f1", "data_type": "Location", "recipient": "first_party",
                "purpose": "Basic service/feature", "retention": "Unspecified"}]
    assert g.answer_key("c", POLICY, COV, control, False, "control")["findings"] == []
    variant = control + [{"flow_id": "f2", "data_type": "Location", "recipient": "admob",
                          "purpose": "Advertising", "retention": "Unspecified"}]
    key = g.answer_key("v", POLICY, COV, variant, False, "variant")
    assert key["flow_labels"] == {"f1": "clear", "f2": "incorrect"}
    assert [(f["gap_type"], f["level"]) for f in key["findings"]] == [("undisclosed_sharing", "explicit")]
