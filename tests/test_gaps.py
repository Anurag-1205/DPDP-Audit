import json

from dpdp_audit.gaps import GAP_TYPES, citation_ok, gap_table
from dpdp_audit.paths import DATA


def test_table_covers_all_gap_types():
    assert set(gap_table()) == set(GAP_TYPES)


def test_every_cited_unit_exists():
    with (DATA / "dpdp" / "sections.jsonl").open() as f:
        ids = {json.loads(l)["id"] for l in f}
    for row in gap_table().values():
        for cid in row["accepted"]:
            assert cid in ids, cid


def test_citation_check():
    assert citation_ok("retention_mismatch", ["Sec. 8(7)"])
    assert not citation_ok("retention_mismatch", ["Sec. 6(1)"])
