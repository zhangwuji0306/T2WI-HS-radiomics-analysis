# FT05B Outcome Unlock Audit

## Authorization gate

The FT-specific authorization entry is
`prognosis_analysis/ft/ft05b_runner.py::validate_ft05b_gate`. It is separate
from the formal W08/L9 B lock and does not call the formal B reader.

| Condition | Evidence | Status |
|---|---|---|
| FT04 model lock | `FT_model_freeze_lock.json`; `FROZEN`, validated; identity SHA-256 `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e` | PASS |
| Formal model lock | `prognosis_analysis/model_freeze_lock.json` absent | PASS |
| FT05A scientific amendment | `FT05A_scientific_freeze_amendment.md`; exact ignored `.finalize` paths and hashes | PASS |
| FT05A accepted technical audit | `FT05A_B_technical_generation_audit.md`; `accepted`, independent `true`, `PASS`; 163 unique B technical cases | PASS |
| FT05A manifest/table | Local ignored `.finalize` assets; manifest SHA-256 `055bdf0e98d05ed4c4e0b8ae2c175d5e82d66ba484ebec30b4b8c04c9e0eb251`; table SHA-256 `10b35d9d661da665bfe98e95dbefa34a6b0e9c0d911bae37a34f3d635ab5d804` | PASS |
| Schema and frozen bindings | Row-schema SHA-256 `3aa6dbec948a52da64aaab74367ab797e340ee0348e10acdf433b79595ba9e19`; `R_low=49`, `R_high=10`; `W_Original=107`; exact order/candidate/provenance checks | PASS |
| FT_B_unlock | Status `authorized`; outcome access `true`; scope `FT06 prediction/evaluation only`; unlock SHA-256 `20aacae0c7cb85c8cf7c544e8788d2950820956e3ab581e41df9d66760e07415` | PASS |

The former non-reproducible outcome-access claim is not used as evidence. The
following superseding access was performed only after this FT-specific gate,
unlock hash, and field validation passed.

## Superseding controlled access

| Field | Value |
|---|---|
| Access timestamp | `2026-09-13T11:35:31+08:00` |
| Reader entry | `ft05b_runner.read_b_dfs -> data_split_guard._authorized_read` |
| Requested columns | `影像号`, `DFS_time`, `DFS_event` only |
| Unlock validated before access | `true` |
| Unlock committed before access | `true` |
| B data read before unlock | `false` |
| Access after unlock | `true` |
| Patient-level frame persisted | `false` |
| FT06 executed | `false` |
| Source commit | `5b2083f4f1b6eef558a2367763213bf90dd3a81f` |
| Receipt | `FT05B_unlock_receipt.json`; SHA-256 `e7a9f35d38416a726df086c054fdbf8b2f600e30782f0c56e3712fb24995285f` |

Aggregate read evidence: `163` authorized rows, `163` unique identifiers,
`42` DFS events, and `121` censored rows. No patient-level outcome frame or
value was persisted.

No prediction, performance calculation, model fitting, lambda/cutoff tuning,
feature selection, K-means fitting, radiomics extraction, or FT06 execution
was performed.
