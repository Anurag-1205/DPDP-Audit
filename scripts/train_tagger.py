"""QLoRA fine-tuning of the clause tagger (SPEC-05, AC-05.3): Qwen2.5-3B-Instruct, 4-bit, rank 16, 2 epochs.

  python scripts/train_tagger.py --out outputs/qlora [--merge outputs/qlora_merged]

Training examples are the annotated segments of the 80 training policies; the target is the
claims JSON the pipeline reads (tagger_data.claims_examples), the prompt is the prompted
tagger's own (pipeline.claims.tagger_prompt), so the fine-tuned and prompted taggers differ
only in their weights. The loss covers the answer tokens only. Hyper-parameters are fixed in
advance; 8 training policies (the PrivBERT dev policies, seed 13) report a dev loss but do not
pick anything. --merge writes fp16 weights with the adapter merged, for serving with vLLM.
Needs a CUDA GPU with torch, transformers, peft and bitsandbytes.
"""
import argparse
import json
import math
import random
import time

SEED = 13
BASE = "Qwen/Qwen2.5-3B-Instruct"
# effective batch 16 = 1 x 16 accumulation steps: logits over Qwen's 152k vocabulary make a batch
# of 4 x 2,048 tokens alone ~5 GB, which does not fit a T4 next to the model
HP = {"rank": 16, "alpha": 32, "dropout": 0.05, "epochs": 2, "lr": 2e-4, "batch": 1, "accum": 16,
      "max_len": 2048, "warmup": 0.05}


def target(rec):
    return json.dumps({"categories": rec["categories"], "claims": rec["claims"]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--merge", default=None)
    ap.add_argument("--limit", type=int, default=None, help="train on the first N examples (smoke test)")
    args = ap.parse_args()

    import os
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, get_cosine_schedule_with_warmup

    from dpdp_audit.pipeline.claims import TAGGER_SYSTEM, tagger_prompt
    from dpdp_audit.tagger_data import claims_examples

    random.seed(SEED)
    torch.manual_seed(SEED)
    train = claims_examples("train")
    policies = sorted({r["policy_id"] for r in train})
    dev_ids = set(random.Random(SEED).sample(policies, 8))
    fit = [r for r in train if r["policy_id"] not in dev_ids][: args.limit]
    dev = [r for r in train if r["policy_id"] in dev_ids][: (args.limit or 10 ** 9) // 4 or None]
    print(f"{len(fit)} training / {len(dev)} dev segments", flush=True)

    tok = AutoTokenizer.from_pretrained(BASE)
    tok.pad_token = tok.pad_token or tok.eos_token

    def encode(rec):
        msgs = [{"role": "system", "content": TAGGER_SYSTEM}, {"role": "user", "content": tagger_prompt(rec["text"])}]
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
        a_ids = tok(target(rec) + tok.eos_token, add_special_tokens=False)["input_ids"]
        ids = (p_ids + a_ids)[: HP["max_len"]]
        labels = ([-100] * len(p_ids) + a_ids)[: HP["max_len"]]
        return ids, labels

    fit_enc = [encode(r) for r in fit]
    dev_enc = [encode(r) for r in dev]
    truncated = sum(1 for r, (ids, _) in zip(fit, fit_enc) if len(ids) == HP["max_len"])
    print(f"truncated examples: {truncated}", flush=True)

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, torch_dtype=torch.float16,
                                                 device_map={"": 0})
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    lora = LoraConfig(r=HP["rank"], lora_alpha=HP["alpha"], lora_dropout=HP["dropout"], task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    def batches(enc, bs, shuffle, epoch=0):
        order = list(range(len(enc)))
        if shuffle:
            random.Random(SEED + epoch).shuffle(order)
        else:  # similar lengths together for evaluation
            order.sort(key=lambda i: len(enc[i][0]))
        for i in range(0, len(order), bs):
            chunk = [enc[j] for j in order[i:i + bs]]
            n = max(len(x[0]) for x in chunk)
            ids = torch.full((len(chunk), n), tok.pad_token_id)
            lab = torch.full((len(chunk), n), -100)
            att = torch.zeros((len(chunk), n), dtype=torch.long)
            for k, (x, y) in enumerate(chunk):
                ids[k, :len(x)] = torch.tensor(x)
                lab[k, :len(y)] = torch.tensor(y)
                att[k, :len(x)] = 1
            yield ids.cuda(), lab.cuda(), att.cuda()

    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=HP["lr"], weight_decay=0.0)
    steps = HP["epochs"] * math.ceil(len(fit_enc) / HP["batch"] / HP["accum"])
    sched = get_cosine_schedule_with_warmup(opt, int(HP["warmup"] * steps), steps)
    scaler = torch.amp.GradScaler("cuda")
    history, t0, step = [], time.time(), 0
    for epoch in range(HP["epochs"]):
        model.train()
        for i, (ids, lab, att) in enumerate(batches(fit_enc, HP["batch"], True, epoch)):
            with torch.autocast("cuda", dtype=torch.float16):
                loss = model(input_ids=ids, attention_mask=att, labels=lab).loss / HP["accum"]
            scaler.scale(loss).backward()
            if (i + 1) % HP["accum"] == 0:
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                scaler.step(opt)
                scaler.update()
                opt.zero_grad()
                sched.step()
                step += 1
                if step % 20 == 0:
                    print(f"epoch {epoch + 1} step {step}/{steps} loss {loss.item() * HP['accum']:.4f} "
                          f"{time.time() - t0:.0f}s", flush=True)
        model.eval()
        tot = n = 0
        with torch.no_grad():
            for ids, lab, att in batches(dev_enc, 1, False):
                with torch.autocast("cuda", dtype=torch.float16):
                    out = model(input_ids=ids, attention_mask=att, labels=lab)
                k = int((lab != -100).sum())
                tot += out.loss.item() * k
                n += k
        history.append({"epoch": epoch + 1, "dev_loss": tot / max(n, 1), "seconds": round(time.time() - t0)})
        print(history[-1], flush=True)
    model.save_pretrained(args.out)
    tok.save_pretrained(args.out)
    info = {"base": BASE, "hyperparameters": HP, "train_segments": len(fit), "dev_segments": len(dev),
            "dev_policies": sorted(dev_ids), "truncated": truncated, "history": history,
            "train_seconds": round(time.time() - t0)}
    with open(f"{args.out}/training_info.json", "w") as f:
        json.dump(info, f, indent=1)
    if args.merge:
        del model
        torch.cuda.empty_cache()
        from peft import PeftModel
        base = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.float16, device_map={"": "cpu"})
        merged = PeftModel.from_pretrained(base, args.out).merge_and_unload()
        merged.save_pretrained(args.merge, safe_serialization=True)
        tok.save_pretrained(args.merge)
        print("merged weights written to", args.merge, flush=True)


if __name__ == "__main__":
    main()
