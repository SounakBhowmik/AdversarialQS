# Experiment protocol

## Default data and budgets

The root seed is 20260910. Draw clean training (128), clean threshold calibration
(128), and independent test fields (32) uniformly in [0, 2] µT. Each test field
has a matched clean and attacked intended schedule, with independent measurement
noise. Training labels are explicitly permitted; test labels are evaluation only.
The same seed across scenarios pairs fields and random-number streams for
comparisons. It does not make test fields overlap training or calibration.

Each sequence contains five nominal times (5, 10, 20, 40, 60 µs), two nominal
analysis quadratures (0, π/2), and separate estimation and verification subsets.
At 1000 shots/setting, each subset costs 10,000 Ramsey shots. Both subsets together
cost 20,000. Tomography adds 3×10,000 extra preparations for the estimation subset.
Exact-state inputs cost no simulated shots but are an explicitly unattainable
hardware oracle. Comparing tomography to measurements is not an equal-total-shot
benchmark; the extra resource is part of the benchmark definition.

Random times are uniform on [5,60] µs by default, or drawn from the configured
time list with `time_distribution: choice`. Random phases are uniform [0,2π),
or drawn from the configured phase list with `phase_distribution: choice`.
Fixed values use the lists directly. Per-shot mode expands each nominal setting
into individual one-shot challenges, preserving its Ramsey shot budget.

## Models and fitting

MLE uses the known ideal-pulse measurement model and public noise calibration.
It searches at least 2049 field grid points, or 128 points per fastest phase
cycle if more are required, then refines the winning minimum. The grid captures
separated aliases in the declared field range. It is not guaranteed for arbitrary
extreme likelihood landscapes or astronomical shot budgets.

Measurement features flatten each estimation setting's recorded expectation,
time in µs, sin α, cos α. Training-only standardization precedes linear ridge,
RBF KRR and MLP. Targets are scaled to µT numerically, then returned to tesla.
Linear ridge alpha is 0.001; RBF alpha=0.01 and gamma=0.03; MLP has 32 hidden units,
L-BFGS, alpha=0.1 and at most 1000 iterations. Hyperparameters are fixed, not tuned
using test labels. Tomography and oracle KRR use preanalysis state arrays,
matching-setting mean HS overlap, alpha=0.01 and training-label mean centering.
Random-schedule models are trained on that schedule distribution; simple flattened
features are intentionally an initial baseline, not optimized variable-time
representations. All six methods run in every scenario.

## Sweeps and controls

Direct phase magnitudes: 0.001, 0.003, 0.01, 0.03, 0.1 rad. Target displacements:
25, 50, 100, 200 nT. Timing relative errors: 0.001, 0.01, 0.05, 0.1. The I/Q
examples use phase 0.05 rad, angle scale 1.05, I gain 1.05, Q gain 0.95, separately
on preparation and analysis. Frequency spoof is A0 and +100 nT. Composite applies
0.03-rad analysis phase then 1% timing error. Custom absolute timing errors,
detunings, gains and component order can be supplied to `simulate` through YAML.

Defense ablations include fixed schedule, random α only, random t only, random t
and α, A2 delays 0/1/2/3/10 µs at a 2-µs deadline, A3 immediate access, and A0
frequency offset. The reference control is essential: time secrecy alone is not
a defense against arbitrary downstream analog control. Sensitivity sweeps vary
100/1000/5000 shots, η=0/0.1/0.2, and T2*=50/100/200 µs one factor at a time.

Every run also evaluates exact probability equivalence at 11 fields and random
challenges for preparation and analysis spoof against a genuine shifted field.
That calculation is not a sampled detection trial and can include fields outside
the regression range: the underlying physical model is still well-defined.

## Confidence and detection

MLE saves a 95% profile-likelihood confidence set: all sampled fields with
`2(NLL−NLL_min) ≤ χ²_1(0.95)`. Disconnected intervals are retained in calibration
scores; bounds expand by half a grid cell. Coverage is measured on test truth.
The Wilks cutoff is approximate, especially near boundaries, weak signals and
alias transitions. The grid resolution is not a substitute for calibration.
Learning regressors do not report fabricated confidence intervals.

The verifier estimates using only the estimation subset, then computes summed
exact binomial NLL (including combination constants) and mean squared standardized
residual on verification counts. Upper empirical clean-calibration quantiles
set 1% and 5% thresholds; decisions use strict `score > threshold`. Test clean
sequences determine actual FPR and test attacks determine TPR. ROC/AUC use these
test scores, never calibration scores. Threshold quantiles are discrete and do
not guarantee the nominal FPR.

Target success is `|B_hat−(B+ΔB)|≤25 nT`, restricted to targets inside configured
field bounds; eligible count is reported. This is a meaningful attack metric for
target/reference spoof. For a direct phase, timing or I/Q scenario the same stored
target is only a diagnostic reference, not that attack's physical objective.
RMSE, MAE, signed bias and state/measurement diagnostics remain applicable.

At 32 test sequences, FPR and TPR vary in increments of 1/32. A 1% rate cannot be
resolved accurately. Publication-level experiments should use at least thousands
of independent calibration and test sequences, multiple root seeds and binomial
or bootstrap rate intervals. These uncertainty intervals and hyperparameter
selection are not implemented in this first demonstration. Report efficacy and
observed FPR/TPR jointly; never equate small KL with stealth.

## Acceptance and review

Installation and all tests must pass. Analytical/density probabilities agree to
2e−15 on the randomized unit test; all saved density matrices are physical within
1e−14 in the component tests. Zero perturbations preserve clean controls/states;
analysis-only attacks preserve preanalysis state. Exact spoof distribution
equivalence must be below 1e−12; the artifact writer fails otherwise.

The high-shot scientific tests verify constant-phase time scaling, MLE recovery,
and the conditional difference between precommitted and immediately informed
attackers. A finite default run need not show monotonic phase-error curves at the
shot-noise floor or perfect nominal detector FPR. Inspect those results and retain
the uncertainty rather than hard-coding success criteria for random metrics.

Use `aqs reproduce --output outputs/reproduction` for the default 21 scenarios.
Use `attack-sweep --suite all` and `sensitivity-sweep` for additional physical
controls. Check the manifest, identifiability result, all figures, clean baseline
error, state-boundary diagnostics and detector false positives before interpreting
any QML comparison. Preserve the exact environment with the saved versions.
