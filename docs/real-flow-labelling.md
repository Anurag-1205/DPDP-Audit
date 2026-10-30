# Real-flow labelling guide (SPEC-08, AC-08.2)

We have **61 real data flows from 33 Android apps** (PoliCheck's released traffic, about 2017 to 2019)
and each app's privacy policy as archived in 2019. Two people label every flow **independently**:
does the policy disclose this flow? These labels are the answer key for the real-flow results, so
the rule **no LLM in ground truth** applies: no ChatGPT, Claude or any other AI tool, and do not
look at any system's output (PoliCheck, B2, our pipeline) before the labels are settled.

| | |
|---|---|
| **Labellers** | Anurag Kaushal and Ishaan Giri (plan WP-4.2) |
| **Time** | about 20 minutes for the practice round, about 2.5 to 3 hours for the 61 flows |
| **Due** | 7 Nov (settled labels) |

## Steps

1. **Setup (once).**
   ```bash
   git pull && git checkout stage-4
   PYTHONPATH=src python3 scripts/real_flow_labels.py pack          # reading packs, in outputs/review/
   PYTHONPATH=src python3 scripts/real_flow_labels.py copies <name> # your own sheets, e.g. copies anurag
   ```
   This makes `data/real_flows/labels_<name>.csv` (61 rows) and `data/real_flows/practice_<name>.csv`
   (8 rows). Open the packs (`outputs/review/real_flows/<package>.md`) in VS Code with the Markdown
   preview (Ctrl+Shift+V). Save sheets as CSV (comma-separated, UTF-8); do not add or delete rows.
2. **Practice round.** Label the 8 flows in `outputs/review/real_flows_practice/P1.md` to `P8.md`
   (their correct label is known), then run
   `PYTHONPATH=src python3 scripts/real_flow_labels.py practice <name>`.
   For every flow marked DIFFERENT, re-read the rules below until you see why. Do not change your
   practice answers after checking.
3. **Label the 61 flows** in your own `labels_<name>.csv`. Fill `label`, and for every label except
   `omitted` the paragraph number (`paragraph`, e.g. `P12`) and the deciding `sentence` copied from
   the pack. Use `notes` when you were unsure. Do not open the other person's sheet and do not
   discuss flows until both of you have finished.
4. **Merge and settle together** (one person runs these after both have pushed their sheets):
   ```bash
   PYTHONPATH=src python3 scripts/real_flow_labels.py merge anurag ishaan          # agreement, kappa
   PYTHONPATH=src python3 scripts/real_flow_labels.py disagreements anurag ishaan  # disagreements.csv
   ```
   Sit together, re-read each disagreement, and fill `agreed` and a short `reason` in
   `data/real_flows/disagreements.csv`. Then run `settle` and `keys`.

## What one flow means

Each row is one flow: **the app sends a data type to a recipient.**

- **Recipient = "the app's own company"**: the company collects the data itself (first party).
  Look for a sentence where *we / the company / the app* collects this data.
- **Recipient = an SDK**, e.g. *Google AdMob (Google)*: the app shares the data with that company.
  Look for a sentence about this data going to that SDK **or its company** (for AdMob, "Google"
  counts; for Meta Audience Network, "Facebook" or "Meta" counts).

## The four labels

Give exactly one label per flow. Go down this list and stop at the first that fits.

| Order | Label | When |
|---|---|---|
| 1 | **clear** | A sentence says the company collects this data (first party), or that this data goes to this SDK or its company (SDK flow). Both the data and the recipient are named. |
| 2 | **incorrect** | The policy says it does **not** do this: "we do not collect location", "we do not share device identifiers with third parties". If the policy both discloses and denies the same flow, also choose **incorrect** and write "contradiction" in `notes`. |
| 3 | **vague** | Only generic wording covers the flow: the data is generic ("information", "personal information", "device information", "technical data") or the recipient is generic ("third parties", "partners", "advertisers", "service providers"). A sentence naming the SDK but no data ("we use AdMob to show ads") is also **vague**. |
| 4 | **omitted** | Nothing in the policy covers the flow. |

**What names the data type** (any of these counts; anything vaguer is generic):

| Data type | Counts as named |
|---|---|
| IP address and device IDs | device ID or device identifier, advertising ID (AAID, IDFA), Android ID, IMEI, MAC address, IP address, unique (device) identifier |
| Location | location, geolocation, GPS, latitude/longitude, precise or approximate location, where you are |
| Contact | email address, phone number, contact information or contact details, postal address |

Notes:
- "may", "sometimes" or "automatically" do not change the label: "we may collect your location" is
  **clear** for a first-party location flow.
- A sentence about **another** practice does not count: "we collect your email to send newsletters"
  covers collection of email by the company, not sharing email with an SDK.
- Cookie or website-only sentences ("when you visit our website") still count if they name the data
  and the recipient; policies often cover the app and the site together.
- When unsure between two labels, choose the one higher in the table above only if you can quote a
  sentence for it, and write why in `notes`.

## Examples

| Flow | Sentence in the policy | Label |
|---|---|---|
| Location to the app's own company | "We collect your precise location to show nearby offers." | clear |
| Device IDs to Google AdMob | "We work with Google AdMob, which may collect your advertising ID." | clear |
| Device IDs to AppsFlyer | "We share device identifiers with our analytics partners." | vague (recipient generic) |
| Device IDs to Unity Ads | "We use Unity Ads to show ads in the game." | vague (no data named) |
| Location to Meta Audience Network | "We may share information with third parties." | vague (both generic) |
| Email to the app's own company | "We do not collect any personal information such as your email address." | incorrect |
| Device IDs to Google AdMob | (no sentence about identifiers, advertising or Google) | omitted |
