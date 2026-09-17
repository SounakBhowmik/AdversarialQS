# Results schema (version 1)

An output root is created exclusively. Reusing an existing directory raises an
error. A failed run retains its partial artifacts and records failure in the
manifest; it is never marked complete. Default roots use UTC timestamp names.

## Files

| Path | Contents |
|---|---|
| `manifest.json` | Status, timestamps, invocation, environment, scenario list, runtime, SHA-256 inventory |
| `results.csv` | Concatenated per-sample/per-estimator scenario results |
| `identifiability.json` | ΔB, max probability discrepancy by pulse, tolerance, equivalence flag, interpretation |
| `clean_accuracy_overhead_tesla.json` | Per-scenario clean RMSE minus fixed-schedule clean RMSE; empty if fixed control absent |
| `figures/*.png` | Figures at 160 dpi |
| `figures/*.json` | Caption, configuration-file references, source CSV |
| `<scenario>/resolved_config.yaml` | All defaults and overrides, including ordered attack components |
| `<scenario>/seeds.json` | Nine SeedSequence entropy/spawn-key identities, in documented stream order |
| `<scenario>/results.csv` | Scenario-specific rows |
| `<scenario>/summary.json` | Regression, target-success and MLE coverage metrics by condition/estimator |
| `<scenario>/detector.json` | NLL/residual threshold and evaluation metrics |
| `<scenario>/roc.json` | Test FPR/TPR arrays for both statistics |
| `<scenario>/calibration.json` | Independent clean validation field estimates, interval sets and scores |
| `<scenario>/kernel_diagnostics.json` | Training/test Gram checks, regularization, matrix distortion |
| `<scenario>/training_diagnostics.json` | Per-learner warning text and optimizer iterations where available |
| `<scenario>/audit.jsonl` | One test-pair audit record per line, detailed below |
| `<scenario>/states.npz` | Complex exact clean/attacked state arrays, detailed below |
| `<scenario>/runtime.json` | Scenario simulation/training/evaluation elapsed seconds |

## CSV columns

Each test pair generates 12 rows: two conditions times six estimators. The test
field and attack metadata are evaluator outputs, not estimator inputs.

| Column | Meaning / unit |
|---|---|
| `scenario` | Grid case name |
| `sample_id` | Integer test pair index within scenario |
| `condition` | `clean` or `attacked` |
| `estimator` | `maximum_likelihood`, `linear`, `rbf_krr`, `mlp`, `tomography_krr`, `oracle_upper_bound` |
| `true_field_tesla` | Simulator evaluation label B, T |
| `estimated_field_tesla` | Prediction B_hat, T |
| `error_tesla` | B_hat−B, T |
| `phase_radians` | Configured direct phase parameter, rad; not necessarily actual spoof phase |
| `target_displacement_tesla` | Configured requested displacement ΔB, T |
| `target_in_bounds` | Whether B+ΔB is inside public estimator bounds |
| `target_success` | Whether prediction is within configured tolerance of B+ΔB |
| `ci_covered` | MLE 95% confidence set contains B; blank for other estimators |
| `nll` | Held-out binomial NLL including combinatorial terms, nats |
| `standardized_residual` | Mean held-out squared standardized binomial residual, dimensionless |
| `latency_seconds` | Configured A2 disclosure latency, s |
| `profile` | Attacker class for scenario |
| `random_times`, `random_phases` | Schedule flags |
| `preanalysis_fidelity` | Mean squared Uhlmann fidelity of clean/attacked preanalysis states |
| `preanalysis_trace_distance` | Mean trace distance at preanalysis boundary |
| `premeasurement_trace_distance` | Mean trace distance after analysis pulse |
| `measurement_kl_nats_per_shot` | Mean KL(Bernoulli(p_attack) || Bernoulli(p_clean)), nats/shot |
| `oracle_kernel_vector_l2` | L2 difference of preanalysis HS overlaps against clean training states |
| `log_likelihood_ratio_attack_vs_clean` | Exact log L_attack/L_clean on attacked counts using known simulator hypotheses |

State, KL and kernel diagnostics describe the pair, and are repeated across its
condition/estimator rows to support joins. Detector scores are computed from MLE
on each condition, repeated for all estimator rows; they do not claim to be
learner-specific detector outputs. The likelihood ratio is an evaluator-only
known-hypotheses metric, not a deployable detector using unknown B/attack truth.

## Metric JSONs

Seed entries 7 and 8 (zero-based test readout and test tomography) each spawn child
0 for clean and child 1 for attacked acquisitions. This condition separation is
part of the reproducibility contract; see the architecture document for all streams.

`summary` keys are `condition/estimator`. `rmse_tesla`, `mae_tesla`, `bias_tesla`
have SI units. `target_success_rate_in_bounds` is a fraction or null when no
targets qualify; `target_eligible_samples` is a count.
`confidence_interval_coverage_95pct` appears only for MLE.

`detector` has `nll` and `standardized_residual` objects. Each contains `roc_auc`
and, for suffixes `1pct` and `5pct`, `threshold_<suffix>`,
`tpr_at_calibrated_<suffix>`, and `heldout_fpr_at_calibrated_<suffix>`.
These operating points mean a threshold calibrated at a nominal rate, not an
assertion that the measured false-positive rate equals it. `roc` supplies FPR and
TPR lists from the test samples.

Kernel training diagnostics contain `minimum_eigenvalue`, `psd_within_1e-10`,
`eigenvalue_shift`, `ridge_alpha`, and kernel name. Test clean/attacked Gram checks
contain the first two fields. `matrix_frobenius_distortion` is the Frobenius norm
of the difference between clean and attacked test-set mean-setting HS Gram
matrices, over both subsets. Kernel-vector distortion uses estimation settings
against training references; the two quantities have different index sets.

## Audit and state records

Each audit line has sample ID, true B for evaluation, and `clean` / `attacked`
lists in challenge order. Each challenge entry has ID, node ID, subset, shots,
zero count, noiseless *recorded* zero probability, intended command, ordered
attack invocation records, and resolved physical operation. Invocation records
contain restricted `attacker_view`, all attacker parameters, original command
and attacked command. The view includes profile, permitted duration/phase or
null, commitment time, disclosure time or null, and textual information level.
All command field units are embedded in their names. Physical rotations are
three-component radian vectors; free duration is seconds; detuning is rad/s.

`states.npz` contains `clean` and `attacked` arrays of shape
`(test_samples, challenges_per_sequence, 4, 2, 2)`. Boundary order is initialized,
prepared, preanalysis, premeasurement. Indices match the audit order exactly.
These are privileged simulator data, not hardware measurements. Training states
and counts can be regenerated using recorded seeds/configuration; they are not
duplicated in output to limit file size. Tomography inputs likewise regenerate
from their independent stream. Test count records permit independent MLE and
verifier reanalysis.

## Manifest and provenance

`schema_version=1`; `status` is running, failed or complete. UTC start/finish
timestamps use ISO 8601. `command` is the Python argument vector. `environment`
records Python version, platform and all installed package versions. `runtime_seconds`
sums scientific scenario runtimes and excludes artifact/plot writing.
`files` maps paths relative to the root to SHA-256 hashes for every artifact
except the manifest itself. `error` exists for failures. Numeric results are
seed-reproducible in the same environment; timestamps and binary-container bytes
need not be identical. No scientific values are hard-coded into manifests.

`source_sha256` maps package-relative Python paths to hashes of the implementation
at run start. This distinguishes editable development versions even when their
package version string is unchanged or no project-local Git repository exists.
