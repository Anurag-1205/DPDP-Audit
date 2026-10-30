"""Sample apps from PoliCheck's released flows and fetch their policies as of early 2019 (SPEC-08, AC-08.1).

  python scripts/sample_real_flows.py [--flows data/external/PrivacyPolicyAnalysis/ext/data/flows.csv]
                                      [--n 30] [--max-tried 150]

PoliCheck's flows were captured about 2017-2019 and its authors downloaded the policies in February
2019. For a random order of apps (seed 13), the Wayback Machine snapshot closest to 2019-02-15 is
fetched; apps whose snapshot is outside 2018-06..2019-12, is not English, or is too short to be a
policy are skipped. One request at a time: the Wayback Machine answers 429 to anything faster.

Policies keep their paragraphs (one HTML block per paragraph, a blank line between them), because
the tagger and `search_policy` split a policy on blank lines. Writes data/real_flows/:
  policies/<package>.txt   policy text
  progress.jsonl           every app tried, so a restart resumes where it stopped
  apps.json                package -> policy URL and snapshot timestamp, for the usable apps
  flows_raw.csv            PoliCheck's own rows for the usable apps (with a header)
Stops at --n usable apps or --max-tried apps tried (failure rule, AC-08.5: docs/stage-4-plan.md §2).
"""
import argparse
import csv
import json
import random
import re
import time

import requests
from bs4 import BeautifulSoup

from build_real_flows import pick, registered
from dpdp_audit.paths import DATA

OUT = DATA / "real_flows"
FLOWS = DATA / "external" / "PrivacyPolicyAnalysis" / "ext" / "data" / "flows.csv"
HEADER = ["package_name", "app_name", "version_name", "version_code", "data_type",
          "dest_domain", "dest_ip", "arb_number", "privacy_policy"]
ENGLISH = {"the", "and", "of", "to", "we", "your", "information", "you", "or", "data", "privacy"}
BLOCKS = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "dt", "dd", "blockquote", "pre"]
PAUSE = 1.5   # seconds between Wayback requests


def get(url: str, **kw) -> requests.Response:
    """The Wayback Machine answers 429 when requests come too fast: wait and retry."""
    wait = 30
    while True:
        time.sleep(PAUSE)
        r = requests.get(url, **kw)
        if r.status_code != 429:
            return r
        print(f"rate limited, waiting {wait}s", flush=True)
        time.sleep(wait)
        wait = min(wait * 2, 300)


def snapshot(url: str) -> str | None:
    r = get("https://archive.org/wayback/available", params={"url": url, "timestamp": "20190215"},
            timeout=30)
    snap = r.json().get("archived_snapshots", {}).get("closest")
    if not snap or snap.get("status") != "200":
        return None
    ts = snap["timestamp"]
    return ts if "20180601" <= ts[:8] <= "20191231" else None


def paragraphs(html: str) -> list[str]:
    """One paragraph per innermost HTML block (p, li, headings, cells); page chrome removed.
    Pages without such blocks fall back to one paragraph per text line."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "form", "button"]):
        tag.decompose()
    out = []
    for el in soup.find_all(BLOCKS):
        if el.find(BLOCKS):   # an outer block: its inner blocks are taken on their own
            continue
        text = re.sub(r"\s+", " ", el.get_text(" ")).strip()
        text = re.sub(r" ([.,;:!?)])", r"\1", text).replace("( ", "(")   # "partners ." -> "partners."
        if text:
            out.append(text)
    if len(out) < 5:
        out = [t for t in (re.sub(r"\s+", " ", s).strip() for s in soup.get_text("\n").splitlines()) if t]
    return out


def policy_text(url: str, ts: str) -> str | None:
    r = get(f"https://web.archive.org/web/{ts}id_/{url}", timeout=60)
    if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
        return None
    text = "\n\n".join(paragraphs(r.text))
    words = re.findall(r"[a-z]+", text.lower())
    if len(words) < 300 or "privacy" not in words:
        return None
    if sum(w in ENGLISH for w in words) / len(words) < 0.08:
        return None
    return text


def stratified_order(by_app: dict[str, list]) -> list[tuple[str, str]]:
    """Apps worth a Wayback request, in the order to try them: only apps with at least one flow
    build_real_flows.py would keep (known token, first party or a known SDK), alternating between
    apps with a Location or Contact flow and the rest, each group in a fixed random order (seed 13).
    Random order alone gives device-ID flows only (they are ~95% of usable flows)."""
    tokens = {r["policheck_token"]: r["data_type"]
              for r in csv.DictReader((DATA / "tools" / "real_token_mapping.csv").open())}
    sdk_by_domain = {registered(r["domain"]): r["sdk_id"]
                     for r in csv.DictReader((DATA / "tools" / "sdk_domains.csv").open())}
    rich, plain = [], []
    for pkg in sorted(by_app):
        url = by_app[pkg][0][8]
        flows = pick(pkg, url, by_app[pkg], tokens, sdk_by_domain, per_app=4)
        if flows:
            (rich if any(f["data_type"] != "IP address and device IDs" for f in flows) else plain).append((pkg, url))
    rng = random.Random(13)
    rng.shuffle(rich)
    rng.shuffle(plain)
    order = [a for pair in zip(rich, plain) for a in pair]
    longer = rich if len(rich) > len(plain) else plain
    return order + longer[min(len(rich), len(plain)):]


def fetch(url: str, ts: str | None = None) -> tuple[str | None, str | None]:
    try:
        ts = ts or snapshot(url)
        return ts, (policy_text(url, ts) if ts else None)
    except Exception:   # dead snapshot, timeout, bad HTML: skip this app
        return ts, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flows", default=str(FLOWS))
    ap.add_argument("--n", type=int, default=45, help="usable apps wanted (~40 give 60-80 flows; spare for A3)")
    ap.add_argument("--max-tried", type=int, default=250)
    args = ap.parse_args()
    rows = [r for r in csv.reader(open(args.flows)) if len(r) == 9 and r[8].startswith("http")]
    by_app: dict[str, list] = {}
    for r in rows:
        by_app.setdefault(r[0], []).append(r)
    apps = stratified_order(by_app)
    pol_dir = OUT / "policies"
    pol_dir.mkdir(parents=True, exist_ok=True)
    progress = OUT / "progress.jsonl"
    done = [json.loads(line) for line in progress.open()] if progress.exists() else []
    seen = {d["package"] for d in done}
    chosen = {}
    for d in done:
        if not d["usable"]:
            continue
        if not (pol_dir / f"{d['package']}.txt").exists():   # fetched before paragraphs were kept
            _, text = fetch(d["policy_url"], d["snapshot"])
            if not text:
                continue
            (pol_dir / f"{d['package']}.txt").write_text(text)
        chosen[d["package"]] = {"policy_url": d["policy_url"], "snapshot": d["snapshot"]}
    print(f"resumed: {len(chosen)} usable of {len(done)} tried", flush=True)
    tried, t0 = len(done), time.time()
    for pkg, url in apps:
        if len(chosen) >= args.n or tried >= args.max_tried:
            break
        if pkg in seen:
            continue
        ts, text = fetch(url)
        tried += 1
        if text:
            (pol_dir / f"{pkg}.txt").write_text(text)
            chosen[pkg] = {"policy_url": url, "snapshot": ts}
        with progress.open("a") as f:
            f.write(json.dumps({"package": pkg, "policy_url": url, "snapshot": ts, "usable": bool(text)}) + "\n")
        if tried % 10 == 0:
            print(f"{len(chosen)} usable of {tried} tried, {time.time() - t0:.0f}s", flush=True)
    with (OUT / "flows_raw.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for pkg in sorted(chosen):
            w.writerows(by_app[pkg])
    (OUT / "apps.json").write_text(json.dumps({"tried": tried, "apps": chosen}, indent=1))
    print(f"done: {len(chosen)} usable of {tried} tried, {sum(len(by_app[p]) for p in chosen)} flows")


if __name__ == "__main__":
    main()
