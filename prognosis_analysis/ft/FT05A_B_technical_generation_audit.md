# FT05A B Technical Generation Audit

Status: accepted
Independent review: true
Verdict: PASS

FT05A run identity SHA-256: `718f357176f704f42027669b47041d24b33e9116b010bceac07b574be84c00bd`
FT05A cohort SHA-256: `642830a817c6c3e71845c32f9be64ab98514adc372d070570bba86f34ae5ba53`
FT05A case-completion evidence SHA-256: `1f70e474ef2dcf42c875630a309fd9f27d88bb9342d5ea60a44d7e1b85ecd585`
Technical case count: 163
FT04 lock identity SHA-256: `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e`
FT05A code-audit SHA-256: `2260e13be4dafe0d5873bb750b48ec23a9fd0467517b7ab434f82f16ef267630`
FT05A runner SHA-256: `a3c6e6b9f3b2598b36b99d944efce97b838191a922e15c3560904709425f9aa3`
W_Original asset SHA-256: `462201e66d8e8989063f02f1d7f63865a23335883c582707dc7713f40d3e9649`
W_Original order SHA-256: `1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f`
FT05A row-schema SHA-256: `3aa6dbec948a52da64aaab74367ab797e340ee0348e10acdf433b79595ba9e19`

Outcome-blind: true
Outcome accessed: false
B K-means fit: false
W_Original reused: true
Repeat extraction: false

## Independent review evidence

- The accepted FT04 lock, frozen A-full boundary, W03/PyRadiomics provenance, candidate hashes, and current independent FT05A code audit were validated successfully.
- The technical cohort contains 163 B cases and only the allowlisted technical source columns. Its canonical frame hash matches the run and audit bindings.
- The run state is `TECHNICAL_COMPLETE_PENDING_REVIEW` with 163 completed cases. All 163 case artifacts and their bound image/ROI source records were reconciled successfully; case hashes and completion evidence match the persisted state.
- The accepted W_Original asset contains 107 frozen features, covers all 163 technical cases, and matches the bound asset and feature-order hashes. Every case row matches its bound W_Original row and the canonical row schema.
- Static safety validation passed with no B K-means, outcome reader, whole-tumour re-extraction, repeat extraction, or formal-directory mixing findings. The B outcome state remains locked, and no canonical manifest, technical feature table, formal model lock, FT05B, or FT06 artifact is present.
- The generation-time runner and code-audit hashes above remain unchanged in the factual binding. The current reviewed runner is bound to implementation commit `db92fb4278572a8baa9133564031fbcccc36b941`; the only post-review path is the canonical FT05A audit namespace, with the exact allowlist marker retained.

## Downstream authorization

The next Worker may resume only the same FT05A run identity and atomically generate the canonical `FT05_B_feature_manifest.json` and `FT05A_B_technical_features.csv` after validating this accepted audit. This authorization does not unlock B outcomes, FT05B, or FT06.
