# Open-source case study (SPEC-08, AC-08.4)

Three open-source Android apps with their own privacy policy:
- their data flows are written by hand from the code;
- the pipeline and B2 run unchanged (frozen configurations, seeds 0–2);
- every output is checked by hand against the policy.

This is the only data with current code, current policies, an Indian app and purpose/retention
fields. It is qualitative: there are no answer keys and no statistics (SPEC-08 non-goal).

| App | Repository @ commit (date) | Policy (date) |
|---|---|---|
| Aarogya Setu (Government of India) | `nic-delhi/AarogyaSetu_Android` @ `b81f31a` (2020-06-01) | aarogyasetu.gov.in/privacy-policy, Wayback 2020-07-25 (earliest copy after the commit) |
| Wikipedia | `wikimedia/apps-android-wikipedia` @ `f0f9ded` (2026-11-09) | Wikimedia Foundation Privacy Policy, revision of 2026-02-21 |
| DuckDuckGo | `duckduckgo/Android` @ `9cc5d19` (2026-11-09) | duckduckgo.com/privacy, last updated 2026-03-06 |

## Files

| File | Content |
|---|---|
| `apps.json` | per app: repository, commit, policy source and date, permissions, SDK coordinates and the flows; every flow cites the file and line it comes from |
| `policies/<package>.txt` | the policy, one paragraph per HTML block (cleaned with `scripts/sample_real_flows.py`'s `paragraphs`) |
| `findings.csv` | the hand check: for every flow, the label from reading the policy, what each system said on its 3 seeds, and a verdict (correct / partly correct / wrong / not run) |

**Build and run:**
- `python scripts/build_case_study.py` writes `data/benchmark/case_study/cases/`.
- Kaggle job `kaggle/case_study/` runs `full_v2_finetuned_rv` and B2. It uses the 29 Oct QLoRA adapter
  from dataset `ishaan2312/dpdp-qlora-adapter`, the same adapter as on main.
- Runs are saved in `results/runs/case_study/`.

**Modelling choices:**
- **Recipients** are `first_party` or an SDK from `data/tools/sdk_table.csv`. SDKs outside the table
  (Firebase Messaging, Google Pay, ML Kit) are left out.
- **Aarogya Setu's SDK coordinates:** the app uses `firebase-analytics-ktx` and Fabric's
  `com.crashlytics.sdk.android:crashlytics`. `build.gradle` lists the SDK table's Firebase Analytics
  and Firebase Crashlytics coordinates instead, with the original in a comment.
- **Retention** is `Unspecified` throughout. The code shows only device-side deletion: Aarogya Setu
  deletes its local Bluetooth contact log after 30 days (`CorUtility.kt:791`).
- **Health data:** Aarogya Setu's self-assessment answers are entered in a web view, so the app code
  shows no health-data flow, and none is modelled.

## Result in one line

The pipeline:
- found the most serious gap: Aarogya Setu's policy says no personal information goes to any third
  party, yet the app sends usage events and crash reports to Google;
- labelled that gap *vague* rather than *incorrect*;
- reported no false alarm. Its one wrong gap, on DuckDuckGo's Email Protection address, was held back
  as uncertain.

B2 raised a gap on almost every flow. It could not run on Wikipedia, whose policy is too long for its
context. Details: `docs/stage-4-report.md` §3.
