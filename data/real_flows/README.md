# Real-flow sample (SPEC-08, AC-08.1 and AC-08.2)

Real Android network flows with the app's privacy policy of the same time, labelled by two team
members. The benchmark built from it is `data/benchmark/real_flows/` (33 cases, one per app).

## Source

- **Flows:** PoliCheck's released flows (`ext/data/flows.csv` in
  [benandow/PrivacyPolicyAnalysis](https://github.com/benandow/PrivacyPolicyAnalysis)): 186,578 flows
  from 22,422 apps, captured about 2017–2019.
- **Policies:** the Wayback Machine snapshot closest to **15 Feb 2019** (when PoliCheck's authors
  downloaded theirs), only if it falls within Jun 2018 – Dec 2019. An old flow paired with a policy
  from the same time is a fair pair; a current policy would not be.
- **Sampler:** `scripts/sample_real_flows.py`, apps in a random order (seed 13), one Wayback request
  at a time. It ran on Kaggle (`kaggle/real_flows/`) because the Wayback Machine rate-limits the
  laptop's address.

## Yield and filters

| Step | Count |
|---|---|
| Apps tried (`progress.jsonl`) | 149 |
| Usable policies: snapshot in range, English, ≥ 300 words, mentions privacy (`policies/`, `apps.json`) | 39 (26%) |
| Excluded by hand (`excluded.csv`: a Terms of Service, not a privacy policy) | 1 |
| Apps with at least one flow that maps to a data type and recipient | **33** |
| Flows in the sample (at most 4 per app, distinct data type and destination) | **61** |

The failure rule (AC-08.5: stop and fall back to the case study if fewer than 20 usable apps after 120
tried) was not triggered.

**Mapping:**
- PoliCheck tokens map to data types through the frozen table `data/tools/real_token_mapping.csv`.
- Destinations map to the app's own company (`first_party`), or to an SDK through
  `data/tools/sdk_domains.csv`.
- Wi-Fi name, router MAC and build fingerprint are left out, because their data type is debatable.

**Mix of the 61 flows:**
- Data types: 52 IP address and device IDs (39 `aaid`, 10 `androidid`, 3 `imei`), 7 Location and 2 Contact.
- Gap types: 45 sharing (third-party SDKs) and 16 first-party collection.
- Recipients:
  - Unity Ads 12, AppsFlyer 8, AppLovin 7;
  - AdMob, Meta Audience Network and Crashlytics 4 each;
  - Adjust 2.

**What the real flows test:** purpose and retention are unknown for real traffic, so these flows test
only **collection and sharing disclosure** (the common view). Purpose, retention and children's data
are covered by the case study (`data/case_study/`).

## Labels (AC-08.2)

Two members labelled every flow independently with `scripts/real_flow_labels.py`, following
`docs/real-flow-labelling.md`. Each first did 8 practice flows from accepted ladder rungs.

| | |
|---|---|
| Labeller 1 | Naveen (`labels_naveen.csv`, `practice_naveen.csv`) |
| Labeller 2 | Anurag (`labels_anurag.csv`, `practice_anurag.csv`) |
| Agreement | 52 of 61 flows (85%) |
| Cohen's κ | **0.728** |
| Disagreements | 9, all settled together with a reason (`disagreements.csv`):<br>• 7 where Naveen said *clear* and Anurag *vague*, settled *vague* (the SDK is named but not the data type);<br>• 2 where Naveen said *omitted* and Anurag *vague*, settled *omitted* |
| Settled labels (`sample.csv`) | 40 vague, 14 clear, 5 omitted, 2 incorrect |

The answer keys in `data/benchmark/real_flows/answer_keys/` are written from the settled labels only
(`scripts/real_flow_labels.py keys`). The labellers never saw any system output.

## Files

| File | Content |
|---|---|
| `apps.json` | usable apps: policy URL and snapshot time |
| `progress.jsonl` | every app tried, so the sampler can resume |
| `flows_raw.csv` | PoliCheck's own rows for the usable apps |
| `policies/<package>.txt` | policy text, one paragraph per HTML block |
| `excluded.csv` | apps dropped by hand, with the reason |
| `sample.csv` | the 61 flows, both labels and the settled label |
| `labels_*.csv`, `practice_*.csv`, `disagreements.csv` | the labelling sheets |

Scores: `python scripts/score_real_flows.py` → `results/scores/real_flows.json`.
