# Threat model

## Assets, goals and trusted components

The protected assets are the intended sensing sequence, the reported field, and
the integrity of a sequence-level consistency decision. The attacker seeks a
specified displacement ΔB or a control-induced estimation error, optionally while
passing the verifier. Simulator truth is an evaluation label, not a trusted
measurement available to the legitimate algorithm.

Trusted: the challenge RNG and scheduler, protected intended-command record,
measurement-count transport, estimator/verifier code, public calibration and
training data. The attacker can transform downstream pulse controls and/or free
evolution timing. Readout bit flips are calibrated noise, not an implemented
adversarial count-rewriting capability. Tomography axes are assumed independently
trusted for that diagnostic estimator; this is stronger access than ordinary
Ramsey readout. Exact preanalysis states are restricted to the labeled oracle.

## Information access

The attack implementation receives only `AttackSpec` (attacker-owned choices) and
`AttackerView`. It does not receive B, state traces, sampled outcomes or the full
configuration. The analog executor separately receives the hidden intended
command and applies the relative transformation. This allows a blind attacker
to add phase without reading nominal phase or timing.

| Capability | Current secret challenge | Nominal schedule | Commitment/disclosure |
|---|---|---|---|
| A0 | Never | None | Fixed commitment at −1 µs, no disclosure |
| A1 | Fixed schedule only | Yes | Fixed known schedule at −1 µs; randomized values withheld |
| A2 | If disclosure delay ≤ actuation window | Yes as fallback | Disclosure at configured delay after t=0 |
| A3 | Immediately | Unnecessary | Disclosure and commitment at t=0 |

Each challenge has an abstract release time t=0 and a configured actuation window
(default 2 µs). If A2 disclosure is too late, commitment is recorded at −1 µs and
uses the nominal schedule. Equality with the deadline counts as actionable.
These timestamps are relative event-model markers, not lab measurements or a
physical pulse clock. The actuation window is assumed to precede the affected
control; it is not derived from t, cable delays or preparation pulse duration.
There is no partial exposure or probabilistic latency jitter yet.

Per-setting attacks commit before each hidden setting; per-shot attacks commit
before each hidden shot. A1's nominal schedule is fixed in advance; the repeated
calls do not confer feedback or access to earlier measurements. A0 spoof may use
an explicit constant `reference_time_seconds` guess. The profiles define allowed
inputs in this simulator, not an operating-system isolation boundary for hostile
plugins.

## Attack surfaces

Phase on preparation changes the sensing state. Phase on analysis changes the
effective measurement basis and the post-analysis state, leaving stored
preanalysis density matrices exactly intact. Timing changes relative pulse
separation; whole-sequence delay has no static-field effect. Coherent I/Q
distortions change phase, angle, drive gain balance or effective detuning.
Frequency reference offsets accumulate phase continuously; they can follow a
secret t without observing its value. Composite attacks execute in listed order
and share one profile/latency, with intermediate commands logged.

The exact-state and trusted-preanalysis-tomography learners can ignore an
analysis-only attack precisely because that attack occurs after their chosen
state boundary. That result reflects privileged placement, not intrinsic QML
security. Conversely, preparation and reference attacks alter those inputs.

## Identifiability and conditional defense

Using the clean convention cos(γBt−α), apply an analysis offset
`δα=−γΔBt`. Then

\[
P_A(0|B,t,\alpha)=P_0(0|B+\Delta B,t,\alpha).
\]

Preparation offset `δβ=+γΔBt` gives the same distribution. A literal positive
analysis offset gives B−ΔB. Since the binomial distributions are identical at
every setting, their joint likelihoods match for every possible record. No
output-only classifier can separate these hypotheses beyond its false-positive
rate. A larger KL relative to clean **B** does not change indistinguishability
relative to clean **B+ΔB**.

Secret t obstructs the specific precommitted nominal-time spoof, because its
phase no longer scales with the actual t. Random α alone cannot stop adding a
relative phase. A3, sufficiently fast A2, or an autonomous reference offset
defeats the proposed time secrecy. Under these conditions, apparent detection
above FPR may indicate boundary priors, noise, finite-sample variation or model
mismatch, not a violation of identifiability.

Targets outside the estimator's allowed field range are excluded from targeted
success rates; range restrictions are genuine independent prior evidence.
Detection statistics still include all test fields, so boundary effects must be
examined before making a stealth claim. A trusted reference, waveform/register
evidence or another physically justified constraint would supply additional
information. None is silently included in this verifier.

Excluded: malicious training data, optical detector tampering, RNG compromise,
classical inference-code compromise, denial of service, side channels, arbitrary
malicious Python execution, attacks on a network, and leakage beyond the two-level
space. These require separate models, not broader implicit attacker access.

