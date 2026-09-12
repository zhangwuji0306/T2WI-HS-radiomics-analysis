# FT05A Independent Pre-run Code Audit — Round 12

Independent review: true

Reviewed FT05A implementation commit: `0745e8a119944f366950ee3e68e3e4225c96584f`

FT05A runner SHA-256: `47245aea440b4dbf4e7fb647f52fbf25352c9bb96b66fe803ea0bf0fb7d7fb95`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

## Verdict

Verdict: PASS

## Scope and evidence

- Directly reviewed the current FT05A runner, FT05A synthetic regression tests, implementation diff at the reviewed commit, FT04 lock/review bindings, preparation contract, and current Git path state.
- The code-audit validator binds the reviewed runner blob to the reviewed implementation commit, requires exact current runner and preparation-contract hashes, and accepts only the canonical FT05A code-audit and factual technical-audit paths after that commit. Post-review code audits must use the canonical tracked report.
- FT05A preflight validates the accepted FT04 freeze, canonical lock identity, accepted FT04 review, B-locked state, frozen A-full boundary, exact A/W03 PyRadiomics settings, frozen R_low/R_high candidate orders and hashes, accepted reused W_Original binding, technical-source allowlist, and absence of the formal model lock.
- The runner remains outcome-blind: technical input headers, source paths, case results, persisted rows, and final tables reject clinical/endpoint content and formal namespaces. Static validation reports no B K-means fit, outcome reader, model-fitting call, or whole-tumour re-extraction route.
- Run-state ownership, one-time identity, per-case completion hashes, atomic writes, resume gating, technical-audit pending state, and manifest finalization gates remain fail-closed. A complete run emits a factual technical audit with `generated_pending_review` and no manifest; manifest creation requires an accepted independent technical audit bound to the run and current runner.
- FT04 downstream validation continues to require the canonical frozen FT05A manifest, complete technical table, accepted independent code and technical audits, frozen provenance, and all outcome-blind generation flags. No FT05B or FT06 access path was used.

## Findings

None blocking or nonblocking.

## Synthetic and regression validation

All Python execution used `tools/run_t2_radiomics.ps1` with the locked `t2_radiomics` environment defined by `environment.yml`.

```text
tools/run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','tests.test_ft05a_runner','tests.test_ft04_runner','tests.test_ft03_runner','tests.test_ft02_runner','tests.test_w07_outer_splits')
110 tests run; 109 passed; 0 failed; 1 skipped; exit code 0

tools/run_t2_radiomics.ps1 -PythonArguments @('.\prognosis_analysis\ft\ft05a_runner.py','static-validate')
pass: true; B_kmeans_fit: false; outcome_accessed: false; whole_tumor_reextraction: false; formal_directory_mixing: false

tools/run_t2_radiomics.ps1 -PythonArguments @('.\prognosis_analysis\ft\ft04_runner.py','validate')
status: VALID; FT04 lock identity: 10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e

tools/run_t2_radiomics.ps1
matches_locked_spec: true
```

The skipped check is the Windows symbolic-link privilege-dependent synthetic case; the non-privileged alias and junction coverage passed. The regression suite covers canonical audit-path binding, non-audit path rejection, outcome/path denial, frozen-boundary and candidate contracts, W_Original reuse, run-state and manifest gating, safe resume, atomic finalization, namespace isolation, tamper rejection, and synthetic technical failure closure.

No real B image, ROI, W_Original value, technical feature, clinical/outcome source, patient-level FT05A output, FT05B artifact, or FT06 artifact was read, generated, or changed during this review.

## Downstream authorization

The next Worker is authorized to run or resume only the same one-time FT05A technical run under the accepted FT04 lock and this accepted pre-run code audit. After technical completion it must leave the factual technical audit in `generated_pending_review` and stop for an independent technical review. This authorization does not unlock B outcome access, FT05B, or FT06.
