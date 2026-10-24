# 4. The benchmark: how test cases are built

Code: `src/dpdp_audit/gold_rules.py`, `cells.py`, `generator.py`. Command: `python scripts/generate_cases.py`.

## Step 1 — read what each policy says

For each of the 35 held-out policies, `gold_rules.build_coverage` turns its OPP-115 annotations into a
lookup:
- which data types the first party collects, and for which purposes;
- which data types it shares, with which named or unnamed parties, and for which purposes;
- which data types it says it does **not** collect or share;
- any retention promises (stated period, limited, indefinitely);
- whether it has a statement about children.

## Step 2 — the rules (the answer key)

For every data flow of an app, fixed rules decide its disclosure label and any gap. Examples:

- **Location collected by the first party, and the policy has a practice "First Party Collection, Location,
  Does":** clear, no gap.
- **Location sent to AdMob, and the policy says "Third Party Sharing, Location, Does Not":** explicit
  `undisclosed_sharing`, label `incorrect`.
- **Location sent to AdMob, and the policy only shares "Generic personal information" with "Unnamed third
  party":** vague `undisclosed_sharing`, label `vague`.
- **App keeps data "Indefinitely", and the policy has a "Stated Period" retention practice:** explicit
  `retention_mismatch`.

The full table is in [answer_key_rules.md](answer_key_rules.md). Two points matter:
- **Every flow is checked, not just the planted one.** If a planted flow also triggers another rule, the
  key lists both gaps.
- **Generic negative statements do not count as explicit.** Lines like "we do not sell your personal
  information" or "except as described" are almost always hedged, so only negatives that name the data
  type count.

## Step 3 — count what each policy can host (cells)

`cells.py` lists every single flow that could be planted in a policy, with the level the rules would
give it. Counting policies per gap type × level gives `data/benchmark/cell_counts.csv`:

| Gap type | explicit | vague | omission |
|---|---|---|---|
| collection | 3 | 33 | 2 |
| sharing | 2 | 33 | 3 |
| purpose | 0 | 32 | 29 |
| retention | 12 | 15 | 12 |
| children | 27 | – | 8 |

OPP-115 policies rarely name a data type in a "we do not..." sentence, so explicit and omitted
collection/sharing gaps are rare. The plan's rule is that cells with fewer than 10 policies keep their
true labels but are reported as **exploratory**. The Stage 2 vagueness ladder fixes this by inserting a
controlled sentence into every policy.

## Step 4 — build the cases

For each held-out policy, `generator.generate`:

1. **Builds a compliant control.** It takes up to 3 first-party collection flows that the policy covers
   with a specific purpose, and up to 2 sharing flows where the policy names the SDK's vendor (e.g.
   "Google" for AdMob) with a specific purpose. It then checks with the rules that the control has
   **zero** findings.
2. **Makes two variants.** Each adds 1–2 planted flows to the control. The planted flows are chosen
   from the cells used least so far, so the rare cells fill first.
3. **Writes app files** from the flows:
   - `build.gradle`, with the SDKs' real package names;
   - `AndroidManifest.xml`, with permissions such as `ACCESS_FINE_LOCATION` and a `child_directed` flag;
   - `dataflows.json`.
4. **Writes the answer key** by applying the rules to the whole app.

One policy has no clearly covered flow, so it gets no control. The result is 34 controls + 68 variants
= **102 cases**, with 118 gold findings and 433 flows (385 clear, 35 vague, 7 omitted, 6 incorrect).

The case folders never contain the answer. `meta.json` only holds the case and policy ids, and whether a
case is a control is stored only in the answer key.

## Worked example: case `1028_v1` (policy: redorbit.com)

`app/dataflows.json`:

| flow | data type | recipient | purpose |
|---|---|---|---|
| f1 | Contact | first_party | Marketing |
| f2 | IP address and device IDs | first_party | Analytics/Research |
| f3 | Computer information | first_party | Analytics/Research |
| f4 | Computer information | **admob** | Advertising ← planted |

`app/build.gradle` therefore includes `com.google.android.gms:play-services-ads:23.0.0`, and the manifest
asks for `READ_CONTACTS` and `AD_ID`.

Answer key (`answer_keys/1028_v1.json`):
- `f1`, `f2`, `f3`: label `clear`, no gap, because the policy covers them specifically.
- `f4`: label `vague`, with one finding: `undisclosed_sharing`, level `vague`, cite `Sec. 5(1), 6(1)`.
  The policy only shares generic information with unnamed partners ("With whom RedOrbit, Inc. may share
  user information...").

What B2 answered on this case (seed 0): it found the `f4` sharing gap (correct). It also reported
collection gaps on `f1`, `f2` and `f3`, which are false alarms. That pattern of over-flagging compliant
flows is the main weakness of the single-pass baselines.

## Export for the existing tools

`export_policheck.py` writes every case as `plaintext_policies/<package>.txt` plus a `flows.csv` in
PoliCheck's format. PoliCheck only knows 16 data tokens (`geolatlon`, `aaid`, `email`, ...), so our types
are mapped through `data/tools/datatype_mapping.csv`:
- `Location` → `geolatlon` is **exact**.
- `Contact` → `email` and `IP address and device IDs` → `aaid` are **approximate**.
- Types such as `Health` have no token and are **not exported**.

Result: 65% of flows can be exported, only 12% exactly (`coverage.json`).

Next: [05_baselines_and_scoring.md](05_baselines_and_scoring.md).
