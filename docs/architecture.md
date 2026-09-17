# Architecture

The package uses `src/adversarial_quantum_sensing`. Related short implementations
are deliberately consolidated instead of creating one file for every attack.
There are no external services, registries or mutable global RNGs.

| Module | Responsibility |
|---|---|
| `config.py`, `constants.py` | Validated immutable SI parameters and angular γ |
| `control/commands.py` | Intended/attacked commands, resolved physical rotations |
| `physics/ramsey.py` | Vectorized ideal-pulse analytical probabilities |
| `physics/density_matrix.py` | Initialization, unitary pulses, dephasing, four state boundaries |
| `physics/pulse_model.py` | Optional coherent rectangular-pulse QuTiP diagnostic |
| `attacks/base.py` | Capability projection, relative transformations, ordered execution and audit |
| `measurement/sampling.py` | Binomial outcomes, typed observations and physical XYZ reconstruction |
| `estimators/maximum_likelihood.py` | Global likelihood search and confidence set |
| `estimators/classical.py` | Protected measurement/challenge features and three learners |
| `estimators/quantum_kernel.py` | Tomography/exact-state kernels and checked regularized solves |
| `defense/challenge.py`, `defense/verifier.py` | Trusted schedule and held-out consistency |
| `experiments/runner.py`, `experiments/sweeps.py` | Acquisitions, isolated splits, experimental grids |
| `metrics.py`, `plotting.py`, `experiments/output.py` | Evaluation, figures, reproducibility artifacts |
| `cli.py` | Argument handling and experiment selection |

## Object contracts

`SensorConfig` contains only public noise calibration. `ExperimentConfig` describes
field bounds, distributions, counts and experiment/attacker configuration, but is
never passed to an estimator or verifier. Supervised `.fit` receives explicit
training labels, as intended. Hidden test truth is available only to simulation
and offline metric evaluation.

`ControlCommand` is immutable and has preparation phase/angle/amplitude, analysis
phase/angle/amplitude, pulse separation, reference detuning, global delay, challenge
ID and node ID. `Challenge` adds trusted subset, shot budget and disclosure policy.
`AttackerView` is a restricted projection, not the challenge itself.
`perturbation(AttackSpec, AttackerView)` returns `ControlDelta`; no hidden command
is passed to that function. `apply_delta` is a trusted analog-path executor.
`execute` logs each intermediate command for a composite.

`resolve` converts an attacked command to `PhysicalOperation`: dimensionless
rotation vectors, seconds of free evolution, and radians/second of detuning.
`simulate(B, command, sensor)` returns `StateTrace`. The parameter B is explicitly
simulator-owned. `StateTrace` is never a measurement estimator input.

`Observation` has only intended command, zero count, shots and subset. Ordinary
learners use `features(observations)` and `.fit(X, labels_microtesla)` /
`.predict(X)`. State learners use the same fit/predict pattern on state arrays;
the exact-state instance is explicitly `oracle=True`. The physics estimator
accepts an observation list and returns an `Estimate` with SI field and confidence
interval union. Different representations intentionally have different typed
inputs; there is no catch-all input object containing hidden truth.

`Acquisition` is a simulator-side result with separate observation, exact-state,
tomography and audit fields. The runner explicitly extracts permitted inputs for
each estimator. Tomography uses independent extra copies at the preanalysis
boundary; it cannot be derived from Ramsey Z outcomes alone.

## Randomness and split flow

A root SeedSequence spawns nine streams: training fields, training challenges,
training readout, training tomography, calibration seed, test fields, test
challenges, test readout and test tomography. The calibration seed spawns four
additional independent streams. No global random seed is set. Fields are uniform
over the configured range; train, calibration and test fields are independent.
Clean/attacked test pairs share B and intended challenge, with independent shot
draws. Estimation and verification acquisitions have disjoint IDs. A run's name
is included in IDs; naming does not change random draws.

The test-readout and test-tomography seed sequences each spawn separate clean and
attacked children, in that order. This prevents probability-dependent random
number consumption in an attacked binomial draw from changing later clean noise.

## Extension seams

A second node creates another `ControlCommand(node_id=...)` stream and calls the
same simulator. A future fusion/verifier module can consume separate trusted
observations keyed by node and challenge. Register monitoring compares intended
and attacked commands; waveform monitoring compares physical operations; neither
currently supplies evidence to the output-only verifier. Add those evidence
channels explicitly rather than leaking simulator state into its inputs.

The pulse API can replace the density propagator in an acquisition once backend
selection and pulse-calibrated inference are added. It is currently a standalone
diagnostic: published CLI results always use instantaneous density evolution.
