# Manual checks: what people must do by hand

Some results can only be trusted after people check them. Our rule is **no LLM in ground truth**, so
this work cannot be handed to ChatGPT, Claude or any other model. This page lists every manual task,
who does it, and exactly how.

## Tasks and owners

| # | Task | Why it matters | People | Due | Time per person |
|---|---|---|---|---|---|
| 1 | **Ladder check** (WP-2.2, AC-06.6) | The ladder results in the mid-submission report are provisional until every rung is checked | Naveen + Anurag Kaushal (**done 28 Oct**) | **29 Oct** (before the mid-submission) | 3–4 h |
| 2 | **Answer-key spot-check** (WP-3.7, AC-01.10) | Reports how often our scripted answer keys are wrong | Naveen + Anurag Kaushal (**done 28 Oct**) | 3 Nov | 2–3 h |
| 3 | **Review the mid-submission report** (gate G-2) | The plan requires two members to read the report before submission | Anurag Kaushal + one more member (to be confirmed) | 29 Oct | 30 min |
| 4 | Real-flow labels (SPEC-08), later | Two independent labels per real data flow | to be assigned | 4–8 Nov | — |
| 5 | Open-source case study checks (SPEC-08), later | Every pipeline finding checked by hand | to be assigned | 7–10 Nov | — |

Ishaan will update the owners here when assignments change. Tasks 4 and 5 will get their own
instructions when their data is ready.

## Rules for tasks 1 and 2

1. **Two people, independently.** Each checker fills in **their own copy** of the sheet. Do not open
   the other person's copy, and do not discuss individual cases until both of you have finished.
   Agreement between two independent checkers is part of what we report.
2. **No AI tools** for reading or judging. Read the policy text yourself.
3. **When unsure,** mark the row `no` and write the reason in `notes`. A rejected rung is reported,
   not hidden; a wrongly accepted one is a silent error.
4. Write short, concrete notes: quote the sentence that decided it, e.g.
   *"para 5: 'we may share information with advertisers' is still there"*.

## Setup (once, about 2 minutes)

You need only `git` and Python 3 — no virtual environment or GPU.

```bash
git clone https://github.com/Anurag-1205/DPDP-Audit.git   # or: cd DPDP-Audit && git pull
cd DPDP-Audit
git checkout -b checks-<yourname>                          # e.g. checks-naveen

# reading packs (one Markdown file per ladder / per case), written to outputs/review/
PYTHONPATH=src python3 scripts/review_pack.py ladder
PYTHONPATH=src python3 scripts/review_pack.py spotcheck

# your own copies of the two sheets (use your first name, lower case)
PYTHONPATH=src python3 scripts/review_pack.py copies <yourname>
```

This creates:

| File | What it is |
|---|---|
| `outputs/review/ladder/L<id>.md` (35 files) | What to read for each ladder |
| `outputs/review/spot_check/<case>.md` (20 files) | What to read for each spot-check case |
| `data/benchmark/ladder/check_sheet_<yourname>.csv` | **Your** ladder answers (140 rows) |
| `data/spot_check/main_spot_check_<yourname>.csv` | **Your** spot-check answers (87 rows) |

Open the `.md` files in VS Code with the Markdown preview (Ctrl+Shift+V) and the `.csv` files in VS
Code, LibreOffice or Excel. If you use a spreadsheet program, save back as **CSV (comma-separated,
UTF-8)**, keep the column order, and do not add or delete rows.

---

## Task 1 — Ladder check

### What the ladder is

For each of 35 held-out policies we picked one data flow of an app (for example: the app sends the
user's **location** to **Mixpanel**). We then:

1. built a **base policy** by deleting every sentence that the OPP-115 annotators marked as being
   about that practice (for that data type or for "personal information" in general);
2. made four versions ("rungs") of the policy that differ by **one inserted sentence**:

| Rung | Case id | Inserted sentence (sharing example) | The correct label |
|---|---|---|---|
| r1 clear | `L<id>_r1` | "We share your precise location with our analytics provider Mixpanel to understand how the app is used." | **clear** — the flow is disclosed |
| r2 explicit | `L<id>_r2` | "We do not share your precise location with third parties." | **incorrect** — the policy contradicts the app |
| r3 vague | `L<id>_r3` | "We may share information with our partners." | **vague** — only generic wording covers it |
| r4 deleted | `L<id>_r4` | nothing (this is the base policy) | **omitted** — nothing covers it |

Collection ladders work the same way with "We collect your …", "We do not collect your …" and
"We may collect information about you when you use our services."

Your job is to confirm that each rung really deserves its label. The deletion was done by a script
using the annotations, and annotations miss sentences, so the main risk is a **base policy that
still talks about the flow**.

### How to check one ladder (about 5–7 minutes)

Open `outputs/review/ladder/L<id>.md`. It shows the app's flow, the four rungs, the insertion point,
the **residual flags** (base-policy sentences that still mention the data type or generic data next
to a practice word), the removed sentences and the full base policy.

1. Read the **residual flags** first, then skim the whole **base policy** for anything about this
   practice: for a *sharing* ladder, any sentence about giving data to third parties, partners,
   advertisers, affiliates or service providers; for a *collection* ladder, any sentence about the
   company collecting this kind of data.
2. Decide each rung with the table below and write `ok` or `no` in the **`ok`** column of the
   four rows of this ladder in your sheet.

| Rung | Write `ok` when… | Write `no` when… |
|---|---|---|
| **r4 deleted** | the base policy says nothing that covers this practice for this data type — not even "we may share your personal information with partners" | anything covers it: a sentence naming the data type (then it is clear or contradicted, not omitted) or a generic statement (then it is vague) |
| **r3 vague** | with the generic sentence added, the flow is covered **only** generically | the base policy already discloses the flow specifically (then it is clear) |
| **r2 explicit** | the inserted denial contradicts the app's flow and no other sentence permits the flow | another sentence in the policy discloses or permits the flow (the policy is then self-contradictory, not a clean denial) |
| **r1 clear** | the inserted sentence clearly discloses the flow (data type, recipient, purpose) and nothing contradicts it | a remaining sentence contradicts it ("we never share location"), or the sentence is garbled where it was inserted |

Notes:
- If the base policy still discloses the flow, **r4 and usually r3 are `no`** — say which sentence.
- A residual flag is a lead, not a verdict: "you provide us with your location" is about
  *collection*, so it does not matter for a *sharing* ladder.
- Data types: **Contact** = name, email, phone, postal address; **IP address and device IDs** = IP
  address, device or advertising identifiers; **Computer information** = browser, operating system,
  device type; **Personal identifier** = government IDs such as SSN, passport, driver's licence;
  **Location** = precise or approximate location.

### Example of how rows are filled in (made-up ladder, not a real verdict)

```
case_id,  …, rung,     gold_label, inserted_sentence,                              …, ok, notes
Lxxxx_r1, …, clear,    clear,      We share your precise location with … Mixpanel …, ok,
Lxxxx_r2, …, explicit, incorrect,  We do not share your precise location with …,     ok,
Lxxxx_r3, …, vague,    vague,      We may share information with our partners.,     ok,
Lxxxx_r4, …, deleted,  omitted,    ,                                                no, "para 4: 'we may forward your information to third parties' still covers sharing"
```

---

## Task 2 — Answer-key spot-check

### What you are checking

The main benchmark has 102 cases. Each case is a real OPP-115 privacy policy plus a small made-up
app (a list of data flows: data type → recipient → purpose → retention). A script computed the
correct answer for every flow from the annotators' labels. We check 20 of these cases (87 flows) by
hand to report the script's error rate.

### How to check one case (about 6–8 minutes)

Open `outputs/review/spot_check/<case>.md`. It lists the case's flows with the **gold label** and
**gold findings** the script produced, the sentences the annotators marked, and the full policy.
For **each flow**, read the policy and decide whether the gold answer is right.

**The label** says how the policy covers the flow's main practice — collection if the recipient is
`first_party`, sharing if it is an SDK such as `admob`, `mixpanel` or `firebase_analytics`:

| Label | Meaning |
|---|---|
| clear | the policy explicitly names this data type for this practice (for an SDK: sharing with that company, e.g. Google for AdMob or Firebase, for a stated purpose) |
| vague | only generic wording covers it ("personal information", "partners", "third parties", no purpose) |
| omitted | nothing in the policy covers it |
| incorrect | the policy says it does **not** do this |

**The gold findings** list the gaps for the flow (`none` if there are none). Besides the label, check:
- **purpose_mismatch** — the app uses the data for a purpose (e.g. Advertising) that the policy
  never states for this data type;
- **retention_mismatch** — the app keeps the data `Indefinitely` while the policy limits retention
  ("only as long as necessary", "for 2 years"), or says nothing about retention;
- **childrens_data** — the app is child-directed and sends data to an advertising or tracking SDK.

Fill in your sheet, one row per flow:

| Column | What to write |
|---|---|
| `agrees` | `yes` if both the gold label and the gold findings are right; `no` otherwise |
| `checker_label` | only if `no`: the label you would give |
| `checker_gap` | only if `no`: the gap you would give, as `gap_type/level` (e.g. `undisclosed_sharing/vague`), or `none` |
| `notes` | only if `no`: the sentence that shows it |

Gap levels: `explicit` (the policy contradicts the app), `vague` (only generic wording),
`omission` (not mentioned).

### Example of how rows are filled in (made-up case, not a real verdict)

```
case_id,   flow_id, data_type, recipient,   …, gold_label, gold_findings,             …, agrees, checker_label, checker_gap,                  notes
xxxx_v1,   f1,      Contact,   first_party, …, clear,      none,                      …, yes,    ,              ,
xxxx_v1,   f4,      Location,  admob,       …, vague,      undisclosed_sharing/vague, …, no,     omitted,       undisclosed_sharing/omission, "no sentence about sharing with anyone; 'partners' appears only for contests"
```

---

## When you finish

1. Check your sheet: every row has `ok`/`no` (ladder) or `yes`/`no` (spot-check).
2. Commit **only your own sheet(s)** and push your branch:
   ```bash
   git add data/benchmark/ladder/check_sheet_<yourname>.csv data/spot_check/main_spot_check_<yourname>.csv
   git commit -m "Ladder check and spot-check by <yourname>"
   git push -u origin checks-<yourname>
   ```
3. Tell Ishaan in the group. When both checkers of a task have pushed, he merges them:
   ```bash
   PYTHONPATH=src python3 scripts/review_pack.py merge <name1> <name2>
   python scripts/score_ladder.py --systems S1 S2 B2 full full_finetuned   # ladder, accepted rungs only
   python scripts/spot_check.py score                                       # answer-key error rate
   ```
   This reports how often the two checkers agreed, re-scores the ladder on the rungs both accepted,
   and computes the error rate for AC-01.10. Disagreements are then settled together and recorded in
   `notes`.

## Next: settling the disagreements (Naveen and Anurag together, before 29 Oct evening)

Both checks are in (ladder: 100 of 140 rungs accepted by both, agreement 76%, κ = 0.19; spot-check:
agreement 77%, κ = 0.04). The disagreements are settled **together, in one sitting** (about 2 hours:
33 ladder rungs and 22 spot-check flows, 2–3 minutes each).

1. Get the lists (already generated on the `pipeline-v2` branch):
   ```bash
   git fetch && git checkout -b settle-checks origin/pipeline-v2
   ```
   - `data/benchmark/ladder/disagreements.csv`: one row per rung you answered differently, with
     `naveen_ok`, `naveen_notes`, `anurag_ok`, `anurag_notes` side by side;
   - `data/spot_check/disagreements.csv`: one row per flow you answered differently (also flows you
     both rejected with a different corrected label).
2. For each row, open the reading pack (`outputs/review/ladder/L<id>.md` or
   `outputs/review/spot_check/<case>.md`; run `review_pack.py ladder` / `spotcheck` if missing), read
   both notes, re-read the policy, and agree on one answer:
   - ladder: write `ok` or `no` in **`agreed`**;
   - spot-check: write `yes` (the answer key is right) or `no` (it is wrong) in **`agreed`**;
   - write one short sentence in **`agreed_notes`** (quote the deciding sentence).
   Apply the rules of Tasks 1 and 2 as written. Most ladder disagreements are on the deleted rung: it
   is `no` when even a generic statement ("we may share information with third parties") covers the
   flow.
3. Do not change any other column or file. Commit only the two files and push:
   ```bash
   git add data/benchmark/ladder/disagreements.csv data/spot_check/disagreements.csv
   git commit -m "Settle check disagreements"
   git push -u origin settle-checks
   ```
4. Ishaan then re-scores (a few minutes, no GPU):
   ```bash
   python scripts/score_ladder.py --systems S1 S2 B2 full full_finetuned full_v2 full_v2_finetuned
   python scripts/spot_check.py score
   ```
   A rung counts when both of you marked it `ok`, or when you settled on `ok`; a row left empty
   stays rejected. The spot-check then reports one final error rate instead of a range.

## Task 3 — Reviewing the mid-submission report

Read `docs/mid-submission-report.md` and check that:
- every number matches `results/scores/main.json`, `ladder.json` and `tagger.json`;
- every claim is backed by a table in the report;
- the negative results (H3, H6, unused tools, purpose gaps) are stated plainly.

Leave comments in the group or on the pull request.

## Questions

Ask Ishaan (Stage 2 runs and scripts) or Anurag (benchmark and ladder design).
