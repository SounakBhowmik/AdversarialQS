# ISCAS 2027 outline (4 pages + 1 reference page)

Track: Sensory Circuits and Systems. Deadline: October 13, 2026.

## Central contribution (one sentence)
In an NV Ramsey magnetometer the microwave control chain (clock, synthesizer, drive) is an
attack surface the sensor cannot police from its own data, and reference-sensor fallback can
restore integrity only up to the reference's own error floor, so security becomes a
hardware-architecture problem: reference sizing, dependency isolation, and dual-transition
drive design.

## Keyword set
Primary: NV magnetometer spoofing. Secondary: quantum sensor security; microwave control
chain; reference sensor fusion; Ramsey magnetometry; clock and synthesizer integrity.

## Title candidates
1. Microwave Control-Chain Spoofing of NV Magnetometers: Detection Limits and Reference-Sensor Design Rules
2. Spoofing NV Ramsey Magnetometers Through the Microwave Drive: Why Reference Fallback Needs Sizing and Isolation
3. Clock and Synthesizer Attacks on NV Diamond Magnetometers and the Design of Reference-Assisted Verification
4. Securing Quantum Magnetometers Against Microwave Drive Spoofing: A Hardware Design Perspective

## Contributions (mapped to CLAIMS.md)
1. Control-chain attack surface: a sub-ppm drive-frequency offset, reachable through the clock or synthesizer, reproduces a field shift in the photon counts for any interrogation schedule (C1-C3, C5); secret interrogation timing stops only precomputed phase attacks (C4, C6).
2. Architectural defense analysis: dual-transition driving cancels common clock errors (about 112 nT to 10 nT at 1 ppm, C3); reference fallback is floored by the reference itself (C7-C9); a closed-form design equation predicts residual harm and a blind window of small spoofs, and gives the reference noise needed to close it (C10-C12).
3. Engineering evaluation: a 30-pipeline frozen simulation study quantifies clock/synthesizer sharing (C13), precision and cost trade-offs of fallback, abstention and fusion (C14-C17), and distills four design rules.

## Paragraph outline
**Abstract** (about 180 words): quantum magnetometers for navigation → estimate rides on microwave phase → attacker on drive chain → cannot self-verify → reference fallback floored by reference, blind window, closed-form sizing rule → shared clock 99.98% harm → design rules.

**I. Introduction** (about 0.8 column)
- P1 hook: NV magnetometers move to the field (navigation), where estimate errors become position errors [barry2020, canciani2016].
- P2 stakes: the quantum spin is hard to reach remotely, but the classical control electronics (clock, synthesizer, AWG, cables) are not; signal injection into sensor electronics is documented [kune2013, shoukry2013]; a 100 nT spoof needs a sub-ppm frequency offset, within crystal tolerance.
- P3 gap: NV literature treats control errors as benign imperfections (robust/DQ sequences [oshnik, fang, bauch, hart]); spoofing work on classical sensors relies on challenge-response timing [pycra, shin]; nobody sizes the reference hardware for recovery rather than detection.
- P4 question + approach: *what can the defender detect and recover when the drive is manipulated?* Analyze at the level of the control chain and reference architecture, derive a closed-form design equation, evaluate by frozen simulation.
- P5 contributions (3 bullets) + one-sentence roadmap.

**II. Sensor Architecture and Threat Model** (about 0.6 column + Fig. 1)
- Fig. 1: hardware chain block diagram (clock → synthesizer/AWG → NV → photodetector → estimator/verifier; reference path; attacker injection point; trust boundary).
- Attacker controls drive frequency or analysis phase only; offline (precomputed) vs real-time knowledge; out of scope: data path, software, reference tampering.
- Engineering scale: 100 nT = 2.8 kHz ≈ 0.9 ppm of the 3.15 GHz transition; shared 10 MHz reference makes clock drift equivalent.
- Metrics: harm (|Y-B| > 25 nT), coverage, RMSE; one sentence.

**III. What the Primary Sensor Can Reveal** (about 0.7 column)
- Ramsey model Eq. (1), one line of parameters.
- Detuning-field equivalence, stated with the rotating-frame condition; lab-frame spin-1 residual bound, per-sequence scope.
- Secret timing: residual phase Eq. (2) defeats precomputed phase tables, not detuning.
- Dual transition: Eq. (3); 1 ppm clock error: 112 nT vs 10 nT; algebraic bound, not demonstrated.

**IV. Reference-Assisted Verification: Architecture and Design Equation** (about 0.8 column)
- Architecture: MLE + held-out NLL score + discrepancy |B̂-R|; calibrated thresholds (one sentence, conformal cite); policies: fallback, abstention, always-reference, fusion.
- Floor: fallback cannot beat the reference under harmful spoof (one-sentence argument); stronger worst-case statement for translation-equivariant fusion stated without proof.
- Design equation Eqs. (4)-(5): three regimes; blind window exists when κ > 2h, i.e., σ_R > 17.3 nT; this is the sizing rule.

**V. Evaluation** (about 1.2 columns + Fig. 2 + Table I)
- Setup (compact paragraph, parameters inline; frozen protocol in one sentence).
- A. Attack capability: fixed vs secret timing vs detuning (numbers in text).
- B. Fallback floor and design-equation check: nominal harm = reference; 50 nT spoof; σ_R = 50 nT worse than reference; closed form within 0.6 pp (Fig. 2).
- C. Hardware dependencies (Table I, audit): shared clock, partial coupling, bias.
- D. Precision, availability, cost: fallback buys clean RMSE; abstention buys harm with coverage; IVW fusion 100% harm; averaging 11 reference readings.

**VI. Design Guidelines and Limitations** (about 0.4 column)
- Four rules: match defense to actuator; size reference to tolerance (σ_R < 17.3 nT for 25 nT); isolate clock/synthesizer/data path; prefer dual-transition drive.
- Limitations: simulation only, abstract white-noise reference, behavioral (not circuit-level) actuator, finite attacker search.

**VII. Conclusion** (about 0.2 column) + future work (hardware demo, dual-transition attack simulation, circuit-level PLL model).

## Floats
- Fig. 1: control-chain block diagram (reuse `figures/pipeline.tex`, scaled to one column or full width top of page 1-2).
- Fig. 2: `figures/reference_theory.pdf` (design equation vs observations).
- Table I: dependency audit + policy trade-offs merged (single column).
Dropped: primary-endpoint table, capability table (numbers go in text), policies table*, trade-off curve figure, fusion table (numbers in text).
