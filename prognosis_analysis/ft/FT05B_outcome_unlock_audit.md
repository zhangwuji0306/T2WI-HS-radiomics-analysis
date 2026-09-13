# FT05B Outcome Unlock Audit

## Authorization conditions

| Condition | Evidence | Status |
|---|---|---|
| FT04 model lock | `FT_model_freeze_lock.json`; identity SHA-256 `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e` | PASS / VALID |
| FT05A feature table and manifest | Local ignored `.finalize` assets; table SHA-256 `10b35d9d661da665bfe98e95dbefa34a6b0e9c0d911bae37a34f3d635ab5d804`; manifest SHA-256 `055bdf0e98d05ed4c4e0b8ae2c175d5e82d66ba484ebec30b4b8c04c9e0eb251`; run identity `718f357176f704f42027669b47041d24b33e9116b010bceac07b574be84c00bd` | PASS |
| Completion and schema | 163 completed unique technical cases; completion evidence SHA-256 `1f70e474ef2dcf42c875630a309fd9f27d88bb9342d5ea60a44d7e1b85ecd585`; row-schema SHA-256 `3aa6dbec948a52da64aaab74367ab797e340ee0348e10acdf433b79595ba9e19` | PASS |
| FT05A accepted technical audit | `FT05A_B_technical_generation_audit.md`: `accepted`, `PASS`; outcome-blind, no B K-means fit, no repeat extraction, no whole-tumour re-extraction | PASS |

Before unlock, `B_data_read=false` and `B_outcome_read=false` were confirmed
from the FT04 lock, FT05A run state, FT05A manifest, and accepted FT05A audit.
Feature columns/order were checked against the frozen M0–M5 technical input
contract; clinical predictors remain a later authorized-stage join.

## First controlled outcome access

The FT B unlock record was written and validated before the first B outcome
read. The FT-specific authorization check then delegated to the project
B-validation reader entry `read_B_validation`. First access was recorded on
`2026-09-13T11:00:59+08:00`, using the authorized B technical allow-list and
requesting only the frozen DFS schema (`影像号`, `DFS_time`, `DFS_event`). The
patient-level frame was held in memory only and was not written to disk.

Aggregate read evidence: `163` authorized rows returned, `163` unique
identifiers, `42` DFS events, and `121` censored rows. Schema and cohort
coverage matched; no patient-level values were persisted.

No prediction, performance calculation, model fitting, lambda/cutoff tuning,
feature selection, K-means fitting, radiomics extraction, or FT06 execution
was performed.
