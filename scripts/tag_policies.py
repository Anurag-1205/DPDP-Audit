"""Tag policy paragraphs once, offline, and cache the claims (pipeline stage 1).

  python scripts/tag_policies.py --tagger prompted --splits main dev [--heldout] [--shard 0/2] [--out FILE]

Collects every distinct paragraph of the chosen splits' policies (and, with --heldout, every
segment of the 35 held-out OPP-115 policies, for the tagger evaluation), skips paragraphs
already in results/tagger/claims/<tagger>.jsonl, and tags the rest with the model served at
OPENAI_BASE_URL / OPENAI_MODEL (greedy decoding: the claims do not depend on the run seed).
--out writes a shard's records to their own file; merge them with --merge FILE ...
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dpdp_audit.cases import case_dirs, load_case
from dpdp_audit.llm import LLM
from dpdp_audit.pipeline.claims import (TAGGER_SYSTEM, load_claims, para_hash, parse_tagger_reply,
                                        save_claims, tagger_prompt)
from dpdp_audit.tools.policy_search import split_paragraphs


def paragraphs(splits, heldout):
    seen = {}
    for split in splits:
        for d in case_dirs(split):
            for p in split_paragraphs(load_case(d)["policy"]):
                seen.setdefault(para_hash(p), p)
    if heldout:
        from dpdp_audit.opp115 import load_all
        from dpdp_audit.split import load_split
        keep = set(load_split()["heldout"])
        for pol in load_all():
            if f"{pol.policy_id}_{pol.name}" in keep:
                for seg in pol.segments:
                    if seg.strip():
                        seen.setdefault(para_hash(seg), seg)
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tagger", default="prompted")
    ap.add_argument("--splits", nargs="*", default=["main"])
    ap.add_argument("--heldout", action="store_true")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--out", default=None)
    ap.add_argument("--merge", nargs="*", default=None, help="merge shard files into the tagger's claims file")
    args = ap.parse_args()

    if args.merge is not None:
        recs = [json.loads(line) for f in args.merge for line in open(f) if line.strip()]
        print("merged", len(recs), "records into", save_claims(args.tagger, recs))
        return

    shard, n = map(int, args.shard.split("/"))
    done = load_claims(args.tagger)
    todo = sorted((h, t) for h, t in paragraphs(args.splits, args.heldout).items() if h not in done)
    todo = [x for i, x in enumerate(todo) if i % n == shard]
    print(f"shard {args.shard}: {len(todo)} paragraphs to tag ({len(done)} cached)", flush=True)
    llm = LLM(temperature=0.0, max_tokens=2048)
    t0 = time.time()

    def work(item):
        h, text = item
        try:
            resp = llm.complete(tagger_prompt(text), system=TAGGER_SYSTEM, seed=0)
            rec = parse_tagger_reply(resp.text)
        except Exception as exc:  # keep going; the paragraph stays untagged
            rec = {"categories": [], "claims": [], "parse_error": f"call failed: {exc}"[:300]}
        return dict(rec, hash=h, model=llm.model)

    with ThreadPoolExecutor(args.workers) as pool:
        recs = list(pool.map(work, todo))
    bad = sum(1 for r in recs if r.get("parse_error"))
    print(f"shard {args.shard}: tagged {len(recs)} paragraphs in {time.time() - t0:.0f}s, {bad} unparseable",
          flush=True)
    good = [r for r in recs if not str(r.get("parse_error", "")).startswith("call failed")]
    if args.out:
        Path(args.out).write_text("".join(json.dumps(r) + "\n" for r in good))
    else:
        save_claims(args.tagger, good)


if __name__ == "__main__":
    main()
