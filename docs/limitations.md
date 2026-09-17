# Limitations and next implementation steps

## Physical scope

This two-level approximation omits the full spin-1 manifold, 14N/15N and 13C
hyperfine structure, strain/electric-field terms, leakage, cross-resonances,
longitudinal relaxation, thermal dynamics and field gradients. B is static along
one sensing axis in a known rotating frame. There is no hardware validation.
The dephasing envelope is empirical and supplied as known calibration. There is
no drift in T2*, contrast, readout or reference frequency unless it is explicitly
injected as a deterministic attack.

Main experiments use instantaneous pulses. The optional QuTiP diagnostic includes
finite rectangular coherent pulses, but no dissipation during pulses, shaped
envelopes or hardware transfer function. It is not selectable in the CLI and
does not change the MLE model. Next add backend configuration and pulse-calibrated
likelihoods, then compare pulse-duration convergence and measured control traces.

Readout is independent Bernoulli sampling with symmetric bit flips, not realistic
Poisson photon counts, optical pumping dynamics, asymmetric confusion or
correlated acquisition noise. I/Q errors are deterministic; stochastic coherent
ensembles and dissipative attacks are not represented by pretending deterministic
rotations reduce purity. Next implement physical stochastic/dissipative channels
only with explicit RNGs and a stated correlation time.

## Representation access and learning

Exact density matrices are an **oracle upper bound on information access** and
are unavailable directly from real hardware. Their chosen HS regressor is not
a performance upper bound and may underfit. Tomography assumes extra identical
preparations, known readout correction and trusted XYZ axes before analysis.
Both state learners therefore bypass final analysis-only corruption. That is a
state-boundary/access distinction, not evidence that QML is inherently secure.

There is no variational quantum circuit or quantum hardware acceleration. The
mixed-state kernel is simulated classically. Hyperparameters are fixed; no
nested cross-validation, repeated-seed uncertainty estimates or robustness-tuned
training are performed. Linear ridge and the simple HS representation can
underfit Ramsey phase wrapping. Randomized challenges use flattened slot features
and may make learning materially harder. Next compare physics-informed variable-
time representations and tune only on independent validation data.

Per-shot mode is implemented but expands to one control/state per shot and uses
a high-dimensional flattened learning input. Runtime and memory scale with shot
count. It is suitable for small proof-of-concept runs; a production implementation
should stream physical acquisitions and use sufficient-statistic or set-based
representations. Tomography for each nominal shot is an extra-copy idealization.

## Threat model and statistics

Randomized sensing is conditional protection against the nominal-time commitment
strategy, not a universal downstream-control defense. Phase-only randomness does
not stop additive offsets. An immediately informed attacker or autonomous
reference-frequency shift tracks the challenge. Latency uses a deterministic
deadline, not measured pulse/control timing; next add actuation-specific deadlines
and latency distributions with causal event simulation.

An ideal spoof and clean shifted field have identical output distributions.
The verifier cannot defeat this identifiability limit. Restricted field priors,
including out-of-range shifted targets, can generate detection independently of
the proposed defense. Target success excludes out-of-range targets, while ROC
includes the full test distribution; inspect this distinction.

Only 128 calibration sequences and 32 test pairs are used by default. These are
inadequate to claim a precisely measured 1% false-positive rate. Calibration
quantiles and test AUC fluctuate. MLE profile-likelihood intervals use an
asymptotic cutoff and finite grid, with boundary/alias limitations. No confidence
intervals for learner predictions or detector rates are fabricated. Next add
large independent repetitions and binomial/bootstrap uncertainty reporting.

The attack interface restricts information by construction, but it is not a
security sandbox against arbitrary Python introspection. No hostile plugins are
executed. Configuration validation rejects unknown unit names, not semantically
wrong numbers written under a correct SI key.

## Extension order

1. Increase clean/test calibration runs and add independent-seed rate intervals.
2. Add physical pulse envelopes, noise/drift and optical-count calibration data.
3. Validate simple phase, timing and reference experiments on one actual NV node.
4. Add independent register or waveform evidence through a verifier input type.
5. Add a second trusted sensor's observations keyed by `node_id`; implement fusion
   outside the single-node simulator, then evaluate correlated/independent attacks.

No distributed network or hardware-security conclusion is claimed by this release.

The initial MLP can hit its 1000-iteration optimization limit on randomized
schedules. Warnings and actual iteration counts are retained in
`training_diagnostics.json`; such fits must not be reported as converged.
