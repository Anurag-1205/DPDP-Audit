# PoliCheck known-answer check (AC-03.4)

The authors' repository ships real flows (`ext/data/flows.csv`) but neither the policies nor the
labels PoliCheck gave them, so their results cannot be reproduced directly. This set checks the
installation instead: seven short policies covering all five PoliCheck labels (first and third party),
with the label PoliCheck's definitions give (`expected.csv`). Run with `SPLIT = "sanity"` in
`kaggle/policheck/run.py`; the result is compared in `scripts/check_policheck_sanity.py`.
