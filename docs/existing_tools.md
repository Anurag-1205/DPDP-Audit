# Existing tools: what the released code can and cannot do

Checked against the authors' repositories (cloned to `data/external/`).

## PoliCheck / PolicyLint — `benandow/PrivacyPolicyAnalysis`
- Runs in Docker (Python 2.7, spaCy 2.0.12). Setup: `scripts/tools/setup_policheck.sh`.
  The 2020 Dockerfile's `apt-get update/upgrade` lines fail on archived Debian mirrors and are removed.
- Needs the authors' pretrained NLP model (Google Drive) in `ext/NlpFinalModel`.
- Input: `ext/plaintext_policies/<package>.txt` and `ext/data/flows.csv` with columns
  `package_name, app_name, version_name, version_code, data_type, dest_domain, dest_ip, arb_number, privacy_policy`.
- Flow data types are a fixed vocabulary: `aaid, androidid, geolatlon, hwid, routerssid, routermac, imei,
  phone, email, wifimac, package_dump, simid, real_name, gsfid` (`fingerprint`, `invasive` are skipped).
  The recipient is resolved from the destination domain.
- Output: `ext/policheck_results.csv`, one row per flow with `consistencyResult` in
  {clear, vague, omitted, ambiguous, incorrect}.
- **Real flows:** the repository's `ext/data/flows.csv` is not a toy example: it holds ~186k flows from the
  paper's dataset with policy URLs. Policies must be fetched from those URLs (many are now dead; use
  archived copies where possible).

## PoliGraph — `UCI-Networking-Group/PoliGraph`
- Conda environment, Playwright, extra data from Google Drive; ~32 GB RAM recommended, GPU optional.
- Its flow check (`analyses/flow-consistency/`) reads the same PoliCheck-format `flows.csv`, so our
  PoliCheck export serves both tools. Run with `scripts/tools/run_poligraph.sh` on a larger machine.
- The released code contains the NLP PoliGraph-er only; **PoliGrapher-LM is not in the repository**.

## PurPliance — `ducalpha/PurPlianceOpenSource`
- The public release contains **only the privacy-statement extractor** (policy sentences → statement
  tuples with purposes; spaCy 2.3 + AllenNLP 1.1 SRL + a NER model from Google Drive).
- The paper's flow-to-policy purpose-consistency checker and its traffic-purpose inference are **not
  released**, so PurPliance cannot run end to end on our cases.
- Consequence for the proposal: S3 cannot be an end-to-end baseline. Options: (a) treat PurPliance as
  related work (the plan's rule for tools that cannot run), or (b) use its extractor as a component
  baseline for purpose extraction. Decision pending with the team.

## Stage 1 smoke tests

| Tool | Result |
|---|---|
| PoliCheck | Runs. Docker image built (spaCy model installed from a host-downloaded file; ~3.4 GB image). On `1028_control` and `1028_v1` it labels the three compliant first-party flows **vague** (gold: clear) and the planted `serial number -> Google Ads` flow **ambiguous** (gold: vague), citing "We DO NOT Share Personal Information with Third Parties". Raw output: `outputs/tools/policheck/main/policheck_results.csv`. |
| PoliGraph | Not run here: needs ~32 GB RAM. `scripts/tools/run_poligraph.sh` is ready for a larger machine. |
| PurPliance | Dropped to related work (plan rule): the public code cannot check flows against a policy. |

PoliCheck reports flows by ontology terms ("email address", "advertising identifier") and resolved entities ("we",
"google ads"); `tool_runs.policheck_outputs` maps them back to our flows. The approximate data-type mapping
(e.g. Contact -> email address) makes PoliCheck read a policy's "contact information" as only a vague match, one
cause of its false alarms on compliant controls; the mapping coverage is reported in `export/policheck/coverage.json`.
