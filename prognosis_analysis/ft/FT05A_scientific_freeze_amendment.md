# FT05A Scientific Freeze Amendment

## Status

`SCIENTIFICALLY_FROZEN_WITH_ENGINEERING_FINALIZATION_EXCEPTION`

FT05A contains a complete outcome-blind B technical feature generation for 163 unique B cases. The persisted engineering state is `FINALIZING` with transaction schema `1`; this indicates that local finalization/promotion is not closed. It is an engineering state and does not invalidate the scientific data, provenance, or outcome-blind status.

## Local output

The patient-level table, manifest, case artifacts, and source assets remain in the local ignored output namespace:

- `prognosis_analysis/output/ft_20260910_01a08bf3/FT05A/.finalize/FT05A_B_technical_features.csv`
- `prognosis_analysis/output/ft_20260910_01a08bf3/FT05A/.finalize/FT05_B_feature_manifest.json`

No patient-level table, manifest, case artifact, source image, ROI, or mapping is included in Git.

## Frozen evidence

| Item | Value |
|---|---|
| Run ID | `FT05A-20260912-01a08bf3` |
| Run identity SHA-256 | `718f357176f704f42027669b47041d24b33e9116b010bceac07b574be84c00bd` |
| FT04 lock identity SHA-256 | `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e` |
| Completed unique B cases | `163/163` |
| Case-completion evidence SHA-256 | `1f70e474ef2dcf42c875630a309fd9f27d88bb9342d5ea60a44d7e1b85ecd585` |
| Staged feature table SHA-256 | `10b35d9d661da665bfe98e95dbefa34a6b0e9c0d911bae37a34f3d635ab5d804` |
| Staged manifest SHA-256 | `055bdf0e98d05ed4c4e0b8ae2c175d5e82d66ba484ebec30b4b8c04c9e0eb251` |
| Row schema SHA-256 | `3aa6dbec948a52da64aaab74367ab797e340ee0348e10acdf433b79595ba9e19` |
| `R_low` candidate SHA-256 | `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0` |
| `R_high` candidate SHA-256 | `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce` |
| `W_Original` count | `107` |
| `W_Original` asset SHA-256 | `462201e66d8e8989063f02f1d7f63865a23335883c582707dc7713f40d3e9649` |
| `W_Original` order SHA-256 | `1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f` |
| Technical audit | `accepted / PASS` |

## Integrity state

- Feature columns and order match the FT04 frozen model-input contract; all frozen model-input hashes match.
- The staged table and the 163 case artifacts have no substantive row disagreement; the canonical table bytes match the table reconstructed from the case artifacts.
- Missing values are confined to unavailable `R_low`/`R_high` technical feature blocks; global descriptors, state indicators, and `W_Original` values are finite.
- `W_Original` is reused from the accepted asset; no B K-means fit, preprocessing estimation, whole-tumour re-extraction, repeat extraction, or formal-directory mixing is present.
- B clinical/outcome data, including B DFS/outcome, has not been read. Clinical predictors remain excluded until the authorized outcome stage.
