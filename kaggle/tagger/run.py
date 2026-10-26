"""Kaggle kernel: tagger baselines on OPP-115 segments (S4 PrivBERT, B3 prompted Qwen-3B).

Downloads OPP-115, writes segment examples for the 80 training and 35 held-out policies
(data/splits.json), then on one T4:
  B3  Qwen2.5-3B-Instruct, zero-shot: each held-out segment -> list of OPP-115 categories
  S4  mukund/privbert fine-tuned as a 10-way multi-label classifier on the training
      policies; 8 training policies are kept aside to pick the epoch, never the test set
Both write predictions for the held-out segments and are scored with tagger_eval.
Results: /kaggle/working/results.tar.gz (data, predictions, scores, logs).
"""
import gc
import glob
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tarfile
import time

WORK = "/kaggle/working"
REPO = f"{WORK}/dpdp-audit"
OUT = f"{WORK}/tagger"
T_START = time.time()
SEED = 13


def sh(cmd, **kw):
    print(f"+ [{time.time() - T_START:.0f}s] {cmd}", flush=True)
    return subprocess.run(cmd, shell=True, check=True, **kw)


def log(msg):
    print(f"[{time.time() - T_START:.0f}s] {msg}", flush=True)


def find_repo():
    tars = glob.glob("/kaggle/input/**/repo.tar.gz", recursive=True)
    if tars:
        with tarfile.open(tars[0]) as t:
            t.extractall(REPO)
        return
    roots = [os.path.dirname(p) for p in glob.glob("/kaggle/input/**/pyproject.toml", recursive=True)]
    shutil.copytree(roots[0], REPO)


def read(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def write(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# ----------------------------------------------------------------------- B3
DEFINITIONS = {
    "First Party Collection/Use": "how and why the service provider collects or uses user information",
    "Third Party Sharing/Collection": "how user information is shared with or collected by third parties",
    "User Choice/Control": "choices and control options available to users (opt-in, opt-out, consent)",
    "User Access, Edit and Deletion": "if and how users can access, edit or delete their information",
    "Data Retention": "how long user information is stored",
    "Data Security": "how user information is protected",
    "Policy Change": "if and how users are told about changes to the privacy policy",
    "Do Not Track": "if and how Do Not Track signals are honoured",
    "International and Specific Audiences": "practices for a specific group of users, such as children, "
                                            "Europeans or California residents",
    "Other": "introductory or general text, contact information, or practices not covered above",
}


def b3_prompt(text: str) -> str:
    cats = "\n".join(f"- {c}: {d}" for c, d in DEFINITIONS.items())
    return ("Label this paragraph of a website privacy policy with every OPP-115 category it "
            f"covers. Categories:\n{cats}\n\nParagraph:\n<<<\n{text}\n>>>\n\n"
            'Answer with a JSON list of category names only, e.g. ["Data Retention"].')


def parse_categories(reply: str) -> list[str]:
    names = {c.lower(): c for c in DEFINITIONS}
    m = re.search(r"\[.*?\]", reply, re.S)
    items = []
    if m:
        try:
            items = [str(x) for x in json.loads(m.group(0))]
        except ValueError:
            items = re.findall(r'"([^"]+)"', m.group(0))
    found = {names[i.strip().lower()] for i in items if i.strip().lower() in names}
    if not found:   # fall back to names mentioned anywhere in the reply
        found = {c for low, c in names.items() if low in reply.lower()}
    return sorted(found)


def run_b3(test):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    name = "Qwen/Qwen2.5-3B-Instruct"
    tok = AutoTokenizer.from_pretrained(name, padding_side="left")
    model = AutoModelForCausalLM.from_pretrained(name, torch_dtype=torch.float16, device_map="cuda").eval()
    preds, bs = [], 16
    for i in range(0, len(test), bs):
        batch = test[i:i + bs]
        texts = [tok.apply_chat_template([{"role": "user", "content": b3_prompt(r["text"][:6000])}],
                                         tokenize=False, add_generation_prompt=True) for r in batch]
        enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=3072).to("cuda")
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=64, do_sample=False, pad_token_id=tok.eos_token_id)
        replies = tok.batch_decode(gen[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
        for r, reply in zip(batch, replies):
            preds.append({"policy_id": r["policy_id"], "segment_id": r["segment_id"],
                          "categories": parse_categories(reply), "reply": reply})
        if i // bs % 10 == 0:
            log(f"B3 {i + len(batch)}/{len(test)}")
    del model
    gc.collect()
    torch.cuda.empty_cache()
    return preds


# ----------------------------------------------------------------------- S4
def run_privbert(train, test, categories, evaluate):
    import numpy as np
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup
    torch.manual_seed(SEED)
    policies = sorted({r["policy_id"] for r in train})
    dev_ids = set(random.Random(SEED).sample(policies, 8))
    fit = [r for r in train if r["policy_id"] not in dev_ids]
    dev = [r for r in train if r["policy_id"] in dev_ids]
    log(f"PrivBERT: {len(fit)} train / {len(dev)} dev segments ({len(dev_ids)} dev policies)")
    name = "mukund/privbert"
    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForSequenceClassification.from_pretrained(
        name, num_labels=len(categories), problem_type="multi_label_classification").cuda()

    def tensors(rows):
        enc = tok([r["text"] for r in rows], truncation=True, max_length=512, padding=True, return_tensors="pt")
        y = torch.tensor([[float(c in r["categories"]) for c in categories] for r in rows])
        return enc, y

    def predict(rows, bs=32):
        model.eval()
        out = []
        with torch.no_grad():
            for i in range(0, len(rows), bs):
                enc, _ = tensors(rows[i:i + bs])
                with torch.autocast("cuda", dtype=torch.float16):
                    logits = model(**{k: v.cuda() for k, v in enc.items()}).logits
                out.append(torch.sigmoid(logits.float()).cpu().numpy())
        probs = np.concatenate(out)
        return [{"policy_id": r["policy_id"], "segment_id": r["segment_id"],
                 "categories": [c for c, p in zip(categories, pr) if p >= 0.5]}
                for r, pr in zip(rows, probs)]

    epochs, bs, lr = 6, 16, 2e-5
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    steps = epochs * ((len(fit) + bs - 1) // bs)
    sched = get_linear_schedule_with_warmup(opt, int(0.1 * steps), steps)
    scaler = torch.amp.GradScaler("cuda")
    best, best_epoch, history = -1.0, 0, []
    for epoch in range(1, epochs + 1):
        model.train()
        order = list(range(len(fit)))
        random.Random(SEED + epoch).shuffle(order)
        for i in range(0, len(order), bs):
            enc, y = tensors([fit[j] for j in order[i:i + bs]])
            with torch.autocast("cuda", dtype=torch.float16):
                loss = model(**{k: v.cuda() for k, v in enc.items()}, labels=y.cuda()).loss
            opt.zero_grad()
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            sched.step()
        dev_f1 = evaluate(dev, predict(dev))["macro_f1"]
        history.append({"epoch": epoch, "dev_macro_f1": dev_f1, "loss": float(loss)})
        log(f"PrivBERT epoch {epoch}: dev macro-F1 {dev_f1:.3f}")
        if dev_f1 > best:
            best, best_epoch = dev_f1, epoch
            torch.save(model.state_dict(), f"{WORK}/privbert_best.pt")
    model.load_state_dict(torch.load(f"{WORK}/privbert_best.pt"))
    preds = predict(test)
    os.remove(f"{WORK}/privbert_best.pt")
    return preds, {"best_epoch": best_epoch, "dev_macro_f1": best, "history": history,
                   "dev_policies": sorted(dev_ids), "epochs": epochs, "batch_size": bs, "lr": lr}


def main():
    find_repo()
    sh(f"bash {REPO}/scripts/download_opp115.sh")
    sys.path.insert(0, f"{REPO}/src")
    from pathlib import Path
    from dpdp_audit import tagger_data
    from dpdp_audit.tagger_eval import evaluate
    counts = tagger_data.write(Path(OUT))
    log(f"tagger data: {counts}")
    train, test = read(f"{OUT}/train.jsonl"), read(f"{OUT}/heldout.jsonl")
    scores = {"data": counts}
    for system, fn in (("B3", lambda: run_b3(test)),
                       ("S4", lambda: run_privbert(train, test, tagger_data.CATEGORIES, evaluate))):
        try:
            t0 = time.time()
            res = fn()
            preds, info = res if isinstance(res, tuple) else (res, {})
            write(f"{OUT}/{system}_pred.jsonl", preds)
            r = evaluate(test, preds)
            scores[system] = dict(r, seconds=time.time() - t0, **info)
            log(f"{system}: macro-F1 {r['macro_f1']:.3f}, micro-F1 {r['micro_f1']:.3f}")
        except Exception as exc:   # one failing system must not lose the other
            import traceback
            traceback.print_exc()
            scores[system] = {"error": repr(exc)}
        json.dump(scores, open(f"{OUT}/scores.json", "w"), indent=1)


if __name__ == "__main__":
    try:
        main()
    finally:
        with tarfile.open(f"{WORK}/results.tar.gz", "w:gz") as t:
            if os.path.isdir(OUT):
                t.add(OUT, arcname="tagger")
        shutil.rmtree(REPO, ignore_errors=True)
        shutil.rmtree(OUT, ignore_errors=True)
