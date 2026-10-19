from dpdp_audit.retrieval import search


def test_children_query_finds_section_9():
    ids = [h["id"] for h in search("app for children sends data to an ad tracking SDK", 4)]
    assert any(i.startswith("Sec. 9") or i == "Rule 10" for i in ids)


def test_retention_query_finds_erasure_rules():
    ids = [h["id"] for h in search("personal data kept indefinitely after the purpose is served", 4)]
    assert {"Sec. 8(7)", "Rule 8", "Third Schedule"} & set(ids)


def test_parallel_first_calls_do_not_race():
    from concurrent.futures import ThreadPoolExecutor

    import dpdp_audit.retrieval as r
    r._MODEL = None
    with ThreadPoolExecutor(8) as pool:
        hits = list(pool.map(lambda q: r.search(q, 2), ["children advertising"] * 8))
    assert all(len(h) == 2 for h in hits)
