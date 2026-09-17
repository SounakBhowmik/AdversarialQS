# Initial implementation verification

This is a measured implementation snapshot, not a claim of hardware performance
or a precomputed result used by the simulator. Authoritative local artifacts are
in `outputs/final-reproduction`; earlier output directories are retained development
runs. Generated outputs are intentionally not version-controlled.

## Commands and checks

Installed into a fresh Python 3.11 virtual environment with
`pip install -e ".[dev,pulse]"`. `pip check` found no broken requirements.
`pytest -q` passed **30 tests**, including QuTiP rectangular-pulse convergence.
`ruff check .` and `ruff format --check .` passed.

Executed:

```bash
aqs reproduce --output outputs/final-reproduction
aqs attack-sweep --config configs/baseline.yaml --suite all --output outputs/final-physical-attacks
aqs sensitivity-sweep --config configs/randomized_defense.yaml --output outputs/final-sensitivity
```

In this restricted execution environment, the commands were prefixed with
`MPLCONFIGDIR=/private/tmp/aqs-matplotlib` to avoid a read-only home font cache.
Normal installations can use the commands as written.

The full reproduction contains 21 scenarios and ten figure types. Verified all
275 artifact hashes and 27 package-source hashes in its manifest. All saved
clean/attacked density matrices were Hermitian, trace-one and PSD within 1e−14.
Plots were inspected for units, labels, state-boundary interpretation and
scientific consistency. Tests reproduce the numeric results exactly and check
that changing an attack cannot alter later clean measurement randomness.

## Observations from the final default seed

Clean MLE RMSE: **4.541 nT**. At +0.1 rad analysis phase, mean MLE bias was
**−18.174 nT** across the multi-time sequence. The high-shot unit test separately
verifies the time-specific `−δφ/(γt)` law.

With target +100 nT and ±25 nT success tolerance:

| Scenario | Mean MLE bias (nT) | Target success | Detection TPR | Held-out FPR |
|---|---:|---:|---:|---:|
| Fixed schedule, A1 | 99.627 | 100% | 3.125% | 0% |
| Random phase only, A1 | 99.009 | 100% | 3.125% | 6.25% |
| Random time, A1 | 72.409 | 40.625% | 100% | 6.25% |
| Random time and phase, A1 | 87.222 | 43.75% | 100% | 9.375% |
| Random time, immediate A3 | 98.827 | 100% | 9.375% | 6.25% |
| Random time, autonomous reference A0 | 98.827 | 100% | 9.375% | 6.25% |

Detection uses the standardized residual and a threshold calibrated on separate
clean data at nominal 5% FPR. These are 32 test pairs; observed rates are coarse
and do not establish a precisely calibrated 1% or 5% operating point. A2 at or
below the configured 2-µs deadline follows the challenge; at 3 µs it falls back
to the nominal-time strategy, with the same conditional behavior as A1.

The exact distribution comparison against clean B+ΔB had maximum absolute
probability discrepancy **5.5511×10⁻¹⁶**, on both preparation and analysis surfaces.
This is the identifiability control; output-only detection cannot distinguish
those equal hypotheses. No randomization claim overrides it.

All six estimators ran. The basic learning representations incur substantial
clean-accuracy cost under randomized schedules, whereas MLE remains at a few nT
RMSE. Several randomized-time MLP fits reached their 1000-iteration limit; their
warning text and iteration counts are saved. These initial models should not be
described as tuned or converged in those cases.

The preanalysis oracle and trusted tomography are deliberately insensitive to
analysis-only corruption. That follows from their observation boundary and extra
access, not from a generic security advantage of QML. See the threat model and
limitations before using these results in a paper.

