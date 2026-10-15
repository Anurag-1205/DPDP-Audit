import pytest

from dpdp_audit.opp115 import OPP_DIR, load_all

pytestmark = pytest.mark.skipif(not OPP_DIR.exists(), reason="OPP-115 not downloaded")


def test_corpus_size_and_categories():
    policies = load_all()
    assert len(policies) == 115
    cats = {p.category for pol in policies for p in pol.practices}
    assert {"First Party Collection/Use", "Third Party Sharing/Collection", "Data Retention"} <= cats


def test_practice_segments_exist():
    for pol in load_all()[:10]:
        assert all(0 <= p.segment_id < len(pol.segments) for p in pol.practices)
