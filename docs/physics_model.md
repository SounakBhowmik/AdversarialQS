# Physics model and conventions

The computational basis |0⟩, |1⟩ approximates a selected NV spin transition.
Positive B is a static field along the sensing axis, expressed relative to the
chosen rotating-frame reference. Hyperfine levels and the unused spin-1 level
are omitted. We set H/ℏ in radians/second; ℏ therefore cancels from the propagator.

$\gamma=2\pi(28.025\times10^9)\;\mathrm{rad\,s^{-1}\,T^{-1}}, \quad U_B(t)=\exp[-i(\gamma B+\delta\omega)t\sigma_z/2].$

The numerical constant is declared once. Converting a frequency specified in Hz
requires multiplying by 2π before passing `microwave_detuning_rad_per_second`.
The reference attack adds **effective rotating-frame detuning**; whether an
increase in a laboratory oscillator frequency corresponds to +δω or −δω depends
on the laboratory frame convention. This simulator defines that sign explicitly.

## Clean Ramsey derivation

Preparation `R_y(π/2)` transforms |0⟩ to |+x⟩. Let preparation phase be β and
analysis phase α. The preparation rotation axis is (−sin β, cos β, 0), so after
free precession and pure dephasing the Bloch vector is

$
r=(C(t)\cos(\gamma Bt+\beta),\;C(t)\sin(\gamma Bt+\beta),\;0),
\qquad C(t)=e^{-(t/T_2^*)^p}.
$

The analysis axis `(sin α, −cos α, 0)` maps measurement of
`X cos α + Y sin α` to Z. Thus the ideal-zero probability is
`[1+C(t) cos(γBt+β−α)]/2`. Symmetric readout flips with probability η give
`P_recorded(0)=η+(1−2η)P_ideal(0)`. For β=0 this is the configured analytical
probability. The preparation and analysis are both positive π/2 rotations around
their stated axes, avoiding an implicit sign choice in a library gate.

Density dephasing multiplies ρ01 by C and uses its conjugate for ρ10; populations
are unchanged. C∈[0,1] yields a completely positive phase-damping map for each
elapsed t. Nonexponential p models an empirical free-induction envelope, not a
time-independent Lindblad generator for arbitrary sequences.

Saved boundaries: initialized, prepared, preanalysis, premeasurement. The final
Z readout may be represented by POVM effects `E0=(I+(1−2η)Z)/2`, `E1=I−E0`.
XYZ tomography uses the same construction for each Pauli axis on additional
copies. It corrects the known readout attenuation and projects the estimated
Bloch vector radially onto the unit ball if sampling makes it unphysical.

## Control distortions

A direct analysis phase offset δφ gives a local equivalent field offset
`−δφ/(γt)`. A preparation phase offset has the positive sign. Different times
cannot generally fit a single equivalent field under one constant offset.
To request +ΔB, analysis spoof uses `δα=−γΔBt` and preparation spoof uses
`δβ=+γΔBt`. In both cases recorded distributions match a clean B+ΔB sequence.
Only the preparation version changes the preanalysis state.

Changing separation to `t_A=t(1+ε)+δt` changes phase and dephasing time.
Ignoring the envelope change, the effective phase bias is `Bε+Bδt/t`.
At B=0 no magnetic phase is created, although envelope mismatch may affect an
inference routine. A global start-time delay is irrelevant for static B and
phase-referenced pulses and therefore does not enter the propagator.

I/Q phase errors and gain balance modify the equatorial rotation vector; angle
scale and pulse amplitude multiply its norm. Cartesian I and Q gains are applied
after the additive phase, in the actual drive axes. A zero drive gives an identity
pulse. Frequency-reference offsets accumulate `(γB+δω)t`, so `δω=γΔB` is an
autonomous spoof without knowing the final t. Ideal deterministic pulses are
unitaries and preserve purity; any mixedness here comes from dephasing.

I/Q `detuning_rad_per_second` is local to the selected pulse and adds a Z
component `δω_pulse * pulse_duration_seconds` to that pulse's rotation vector.
The command's default 20-ns duration calibrates this coherent error; ordinary
field evolution during pulses is included only by the optional pulse backend.
In contrast, the `frequency` attack changes the continuously accumulating
reference term. Analysis-local detuning cannot change the preanalysis state.

## State similarity and kernel convention

`metrics.uhlmann_fidelity` returns **squared** fidelity
`F=(Tr sqrt(sqrt(ρ)σsqrt(ρ)))²`. For 2×2 normalized states it uses the equivalent
`Tr(ρσ)+2 sqrt(detρ detσ)` expression for numerical stability at pure states.
It returns 0.5 for |0⟩ and |+⟩. This differs from APIs returning root fidelity;
[QuTiP's fidelity convention](https://qutip.readthedocs.io/en/qutip-5.0.x/apidoc/functions.html)
must not be substituted without accounting for that distinction.

The Hilbert–Schmidt kernel is `Kij=mean_s Tr(ρis ρjs)`. It is a Gram matrix in
operator space and PSD. The optional squared-fidelity kernel averages the above
F across matched settings. Its actual computed Gram matrix is checked rather
than assuming PSD for arbitrary future kernels. Ridge regularization and any
negative-eigenvalue compensating diagonal shift are recorded. The original
cross-kernel is kept; this is regularization, not an unrecorded feature correction.
Trace distance is one half the trace norm of the state difference.

## Pulse backend and validation

The optional QuTiP backend exponentiates rectangular pulse Hamiltonians
`H/ℏ=(Ωx X+Ωy Y+δω_total Z)/2`. It includes the field/reference phase during pulse
duration, then applies the same free-evolution dephasing channel. It omits pulse
dephasing, leakage and shaped envelopes. Its instantaneous-duration limit is
tested; it is not used silently in CLI likelihood experiments.

Analytical/density agreement is tested to 2e−15 absolute probability across 100
random cases. Hermiticity, trace and PSD use 1e−14 tolerances appropriate for the
small matrix products. Exact spoof equivalence is checked to 1e−12, conservatively
above floating-point differences. These are numerical checks, not error bars on
physical fidelity to a real NV sensor.
