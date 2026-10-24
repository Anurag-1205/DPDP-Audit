# 2. Concepts you need

## Privacy policy and data flow

A **privacy policy** is the text an app publishes about what personal data it collects, why, and who
receives it.

A **data flow** is one thing the app actually does with data. We write it as four fields:

```
data type  ->  recipient  ->  purpose  ->  retention
Location   ->  admob      ->  Advertising  ->  Unspecified
```

- **Recipient** is either `first_party` (the app's own company) or a third-party SDK such as `admob`
  or `mixpanel`.
- **Collection** means the first party takes the data. **Sharing** means it goes to a third party.

## The DPDP Act and Rules (what we cite)

The official texts are in `data/raw/dpdp/` (not in git; download links are in `data/dpdp/SOURCES.md`).
`data/dpdp/sections.jsonl` splits them into 153 citable units such as `Sec. 5(1)` and `Rule 3`.

| Unit | What it requires | Used for |
|---|---|---|
| Sec. 5(1) | Notice of what personal data is processed and for what purpose | undisclosed collection/sharing, purpose mismatch |
| Sec. 6(1) | Consent is specific and limited to that purpose | same |
| Rule 3 | The notice must give "an itemised description of such personal data" and the specified purpose | why vague wording counts as a gap |
| Sec. 8(7) + Rule 8 + Third Schedule | Erase data once the purpose is served | retention mismatch |
| Sec. 9(3) + Rule 10 | No tracking or targeted advertising directed at children; verifiable parental consent | children's data |

## OPP-115

**OPP-115** is a public research corpus: 115 website privacy policies in which law students marked every
data practice, paragraph by paragraph. One annotated practice looks like this:

```
category:      Third Party Sharing/Collection
data type:     Location
does/does not: Does Not
third party:   Unnamed third party
purpose:       Unspecified
```

We use the "consolidated" version, where annotators agreed: 19,720 practices. They fall into 10
categories, of which we use four:
- First Party Collection/Use
- Third Party Sharing/Collection
- Data Retention
- International and Specific Audiences, which is where children's statements live.

The 115 policies are **split by policy**: 80 for training (the future fine-tuned tagger) and 35 held out
(every test case comes from these 35). This is in `data/splits.json`.

## Gap types

| Gap type | What the app does | Gold citation |
|---|---|---|
| `undisclosed_collection` | Collects a data type the policy does not cover | Sec. 5(1), 6(1) |
| `undisclosed_sharing` | Sends a data type to a third party the policy does not cover | Sec. 5(1), 6(1) |
| `purpose_mismatch` | Uses data for a purpose not stated for it (e.g. advertising) | Sec. 5(1), 6(1) |
| `retention_mismatch` | Keeps data indefinitely when the policy limits retention | Sec. 8(7) |
| `childrens_data` | Is child-directed and sends data to an ad or tracking SDK | Sec. 9(3) |

PoliCheck and PoliGraph can only detect the first two. We call those two the **common subset**.

## Levels and labels

Every gap has a **level**: how the policy relates to it. Every data flow also has a **disclosure
label**, which uses the same words as PoliCheck.

| Level | Example policy wording for "location sent to an ad SDK" | Flow label |
|---|---|---|
| explicit | "We do not share your location." (the policy contradicts the app) | `incorrect` |
| vague | "We may share information with partners." (only generic words cover it) | `vague` |
| omission | Location is never mentioned | `omitted` |
| (no gap) | "We share your precise location with Google AdMob for ads." | `clear` |

**Important difference:** PoliCheck treats a vague disclosure as *fine*. We treat it as a gap, because
DPDP Rule 3 asks for an itemised description. To be fair to the tools, we score them both ways (see
"native reading" in [05_baselines_and_scoring.md](05_baselines_and_scoring.md)).

## Metrics in plain words

- **Precision:** of the gaps a system reported, the share that were real.
- **Recall:** of the real gaps, the share the system found.
- **F1:** a single number that balances precision and recall.
- **False-alarm rate:** the share of *compliant* apps (controls) where the system reported any gap.
  Lower is better.
- **Citation correct:** for correctly found gaps, the share that cite an accepted DPDP section.
- **Label macro-F1:** how well a system labels each flow clear / vague / omitted / incorrect, averaged
  over the four labels.
- **Bootstrap interval:** a 95% range for a score, made by re-sampling *whole policies*. Cases built
  from the same policy are not independent, so we never re-sample single cases.

## Systems (names used everywhere)

| Name | What it is | Status |
|---|---|---|
| B1 | One prompt to Qwen2.5-7B with the raw policy and raw app files | Run (3 seeds) |
| B2 | One prompt to the same model with the policy, parsed app facts and retrieved DPDP text | Run (3 seeds) |
| B4 | B2's prompt sent to Gemini (`gemini-3-flash-preview`) | Not run yet |
| S1 | PoliCheck | Smoke test on 2 cases |
| S2 | PoliGraph | Script ready (needs ≥32 GB RAM) |
| S3 | PurPliance | Dropped to related work (its released code has no flow checker) |
| full, A1–A5 | DPDP-Audit and its ablations | Stage 2 onwards |

Next: [03_repository_guide.md](03_repository_guide.md).
