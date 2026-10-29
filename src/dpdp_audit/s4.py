"""S4 (WP-3.6, AC-05.6): PolicyLint and PoliGraph statements as the taggers' claims.

Both tools extract (entity, collect / not collect, data) statements from policy sentences. Each
statement becomes a claim in the pipeline's format, so the tools are scored with the same tuple
F1 as the taggers (tagger_eval.evaluate_tuples) on the same 1,140 held-out OPP-115 segments:
- entity "we" -> First Party Collection/Use; any other entity -> Third Party Sharing/Collection,
  with its OPP-115 third-party value;
- collect -> "Does", not_collect -> "Does Not" (PoliGraph keeps only positive statements);
- the data term -> an OPP-115 data type.
Terms are mapped by the ordered rules of data/tools/s4_mapping.csv (first match wins), written
from the OPP-115 annotation guidelines before any S4 output was seen.

Sensitivity (added after the first results, 29 Oct): neither tool resolves the company's own
name to the first party ("Honda Motor", "pbs"), so such statements map to a Named third party.
`own_name_rule` treats an entity as the first party when a distinctive word of it appears in the
policy's website domain or title (segment 0). The S4 rows use the frozen mapping; the
`*_own_name` rows show the effect of this one change.

Raw tool outputs (Kaggle, kaggle/policheck and kaggle/poligraph with SPLIT = "s4"):
- results/tools/policylint/s4/policylint_s4.json: per segment file s4_<policy>_<segment>, the
  statements as normalised by PolicyLint itself (its ontologies and filters);
- results/tools/poligraph/s4/poligraph_s4.json: per policy, the COLLECT edges of PoliGraph's
  graph with the sentences they came from; a sentence is assigned to every segment of that
  policy whose text contains it.
"""
from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path

from .paths import DATA, RESULTS

MAPPING = DATA / "tools" / "s4_mapping.csv"
POLICYLINT = RESULTS / "tools" / "policylint" / "s4" / "policylint_s4.json"
POLIGRAPH = RESULTS / "tools" / "poligraph" / "s4" / "poligraph_s4.json"
FIRST = "First Party Collection/Use"
THIRD = "Third Party Sharing/Collection"
NO_ACTOR = "UNSPECIFIED_ACTOR"   # PoliGraph: passive voice, no entity named


@lru_cache(maxsize=1)
def rules() -> dict[str, list[tuple[re.Pattern, str]]]:
    out: dict[str, list] = {"data": [], "entity": []}
    rows = sorted(csv.DictReader(MAPPING.open()), key=lambda r: (r["kind"], int(r["order"])))
    for r in rows:
        out[r["kind"]].append((re.compile(r["pattern"]), r["value"]))
    return out


def map_term(term: str, kind: str) -> str:
    t = re.sub(r"\s+", " ", (term or "").strip().lower())
    for pattern, value in rules()[kind]:
        if pattern.search(t):
            return value
    raise ValueError(f"no {kind} rule matches {term!r}")   # the last rule of each kind matches all


OWN_NAME_STOP = {"inc", "group", "company", "corp", "corporation", "llc", "ltd", "the", "network", "networks",
                 "media", "services", "service", "of", "and", "co", "limited", "holdings", "international",
                 "online", "website", "site", "web"}


def own_name_rule(titles: dict[str, str], domains: dict[str, str]):
    """is_own(entity, policy_id): a distinctive word of the entity is in the policy's domain or title."""
    def is_own(entity: str, pid: str) -> bool:
        words = [w for w in re.findall(r"[a-z0-9]+", entity.lower()) if len(w) >= 3 and w not in OWN_NAME_STOP]
        stem = re.sub(r"\.(com|org|net|edu|gov|co|us|uk)$", "", domains.get(pid, "").lower()).replace("www.", "")
        hay = (stem + " " + _norm(titles.get(pid, ""))).split()
        return any(w in hay or w in stem for w in words)
    return is_own


def to_claim(entity: str, collect: bool, data: str, own: bool = False) -> dict:
    party = "first party" if own else map_term(entity, "entity")
    first = party == "first party"
    return {"category": FIRST if first else THIRD, "data_type": map_term(data, "data"),
            "does": "Does" if collect else "Does Not", "third_party": "" if first else party}


def _norm(text: str) -> str:
    text = text.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def policylint_claims(path: Path = POLICYLINT, is_own=None) -> tuple[dict, dict]:
    """{(policy_id, segment_id): [claims]} and counts. is_own: optional own_name_rule."""
    segs = json.loads(path.read_text())["segments"]
    out, stats = {}, {"segments": len(segs), "statements": 0, "raw_statements": 0}
    for name, v in segs.items():
        m = re.fullmatch(r"s4_(.+)_(\d+)", name)
        key = (m.group(1), int(m.group(2)))
        stats["raw_statements"] += len(v["raw"])
        claims = []
        for entity, action, data, _sentence in v["statements"]:
            claims.append(to_claim(entity, action == "collect", data, own=bool(is_own and is_own(entity, key[0]))))
        stats["statements"] += len(claims)
        out[key] = claims
    return out, stats


def poligraph_claims(segments: list[dict], path: Path = POLIGRAPH, is_own=None) -> tuple[dict, dict]:
    """segments: [{"policy_id", "segment_id", "text"}]; returns {(policy_id, segment_id): [claims]}."""
    graphs = json.loads(path.read_text())
    by_policy: dict[str, list] = {}
    for s in segments:
        by_policy.setdefault(str(s["policy_id"]), []).append((int(s["segment_id"]), _norm(s["text"])))
    out: dict = {}
    stats = {"policies": len(graphs), "collect_edges": 0, "no_actor_edges": 0, "sentences": 0,
             "sentences_unmatched": 0}
    for pid, edges in graphs.items():
        for e in edges:
            if e.get("key") != "COLLECT":
                continue
            stats["collect_edges"] += 1
            if e["source"] == NO_ACTOR:
                stats["no_actor_edges"] += 1
                continue
            claim = to_claim(e["source"], True, e["target"], own=bool(is_own and is_own(e["source"], pid)))
            for sentence in e.get("text") or []:
                stats["sentences"] += 1
                ns = _norm(sentence)
                hits = [seg for seg, text in by_policy.get(pid, []) if ns and ns in text]
                if not hits:
                    stats["sentences_unmatched"] += 1
                for seg in hits:
                    claims = out.setdefault((pid, seg), [])
                    if claim not in claims:
                        claims.append(claim)
    return out, stats


def as_predictions(gold: list[dict], claims: dict) -> list[dict]:
    """One prediction per gold segment (a segment without statements predicts no tuple)."""
    return [{"policy_id": g["policy_id"], "segment_id": g["segment_id"],
             "categories": sorted({c["category"] for c in claims.get((str(g["policy_id"]), int(g["segment_id"])), [])}),
             "claims": claims.get((str(g["policy_id"]), int(g["segment_id"])), [])} for g in gold]
