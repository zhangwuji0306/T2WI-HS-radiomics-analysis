# Archive reference

## Active method and protocol

- Active method: `Primary Prognostic Analysis v2`.
- Active protocol: `T2WI-HS-radiomics-analysis Primary v2 正式分析方案书与串行执行工作流.md`.
- Machine-readable contract: `prognosis_analysis/primary/protocol.json`.
- Active long-term branch: `main`.

## Immutable history anchors

- Formal v1: `archive/formal-nested-cv-v1-20260913`.
- FT validation v1: `archive/ft-validation-v1-20260913`.

The tags are immutable recovery points. The transition commit history remains traceable through the Primary v2 commits and the merged `main` history.

## Historical refs / cleanup boundary

- `main` is the only active long-term branch, and Primary v2 is the only active scientific protocol.
- `codex/l7-current-code-technical-preflight` and `codex/w00-formal-archive` remain occupied by their respective linked worktrees. They are not removed in this cleanup to avoid deleting content from other workspaces.
- Older `origin/codex/*` refs are remote historical references only. This cleanup does not delete remote refs or push to the remote.
- These retained references are not active analysis routes. They do not alter either immutable tag or the Primary v2 scientific release conclusion; retention is a reversible repository-safety boundary.

## Archive directories

- `archive/formal_nested_cv_v1/`: Formal W08 v1 protocol, old execution SOP, W08/R5/R6 audit records and aggregate evidence.
- `archive/ft_validation_v1/`: FT protocol, FT03/FT04/FT06 aggregate reports/reviews and freeze metadata.
- `archive/project_status_history/`: pre-Primary-v2 project status.
- `archive/protocol_history/`: earlier protocol history.

## Active upstream assets intentionally not archived

The following remain active or reusable upstream assets: `feature_extract/` scripts and configs; `habitat_analysis/` configs, cohort definitions, freeze locks and scripts; `prognosis_analysis/primary/`; the clinical schema and generic provenance utilities; the current scientific master protocol; the Pre-W08 upstream SOP; `environment.yml`, `requirements-cloud.txt`, `setup.sh`, `tools/` and regression tests.

The untracked Primary v2 scheme book and `_codex_ft_run_*` transition contracts are preserved locally as required and are not included in this archive commit. Patient-level data, raw imaging, ROI, clinical/pathology/outcome source tables, mapping files and all output directories are outside this reference and remain excluded.
