Simulator Briefing: What to Emulate (and Why) for the 1550 nm Analog-Optical Rig

This document tells you exactly what to build into the software emulator / digital twin so it remains useful before hardware purchase and later for tuning. It folds in lessons from our own 1550 nm design, Microsoft’s AOC, and recent free-space/photonic-chip results.

1) Scope & Targets
A. Architectures to cover

MVP (one-pass, single-λ)

Source → mixing/weighting optics → nonlinearity → readout (photodiode bank or camera)

No feedback loop; validates mapping, SNR, and readout.

8-λ scalable tile (loop-capable)

WDM (8 wavelengths) ± MDM (e.g., 4 modes) → mixing → nonlinearity → per-λ (and per-mode) readout → optional electro-optic gain & reinjection.

This is the “unit tile” we replicate for scale.

MDM camera readout option (research branch)

Photonic lantern (mode to pixel fan-out) + InGaAs camera instead of PD banks.

B. What “success” looks like

Functional: Stable inference with ternary internal states (−1/0/+1) and saturating nonlinearity; loop convergence (when enabled).

Signal quality: Meets per-channel OSNR/BW needed to maintain task accuracy (image/text toy tasks, reservoir tasks).

Scaling: Predicts accuracy/speed/energy as λ and mode counts grow.

Tunability: Digital twin exposes knobs that correspond to real hardware controls (gains, VOAs, filter detunes, thresholds, bias points).

2) System Block Model (what to implement)

Represent the optical graph as a linear operator (complex transfer matrix) plus nonlinear + noise at well-defined points. Keep units consistent (W, A/W, dBm):

Sources (per λ)

Power 
𝑃
0
P
0
	​

, linewidth, relative intensity noise (RIN), phase noise.

Optional coherence constraints (for interference-based mixing).

WDM / MDM front-end

WDM MUX/DEMUX: channel spacing (e.g., 50/100 GHz), insertion loss, isolation, passband ripple, group-delay ripple.

MDM couplers/lanterns: mode-mix matrix with adjustable inter-mode crosstalk, coupling efficiency, differential group delay (DGD).

Mixing / Weighting

Model as a constrained matrix 
𝑊
W with amplitude-only or phase-capable taps (depending on the physical path we choose).

Negative weights via differential pairs and balanced detection (simulate that explicitly).

Include quantization or limited resolution of setpoints (e.g., 8–10-bit VOAs).

Amplifiers

SOA: small-signal gain, gain saturation (P_sat), carrier lifetime (dynamic saturation), pattern-dependent distortion, AM-to-PM if relevant, noise figure; cross-gain modulation between channels.

EDFA: gain, gain tilt vs λ, saturation, ASE PSD, noise figure.

Passive optics

Fiber attenuation (short but non-zero), polarization-mode dispersion (PMD), splice/coupling losses; coupler split ratios and excess loss.

Nonlinearity (the “activation”)

Our ternary trick: implement a saturating quantizer with hysteresis option:

𝑦
=
t
e
r
n
a
r
y
(
𝑥
;
𝜃
,
 
Δ
)
∈
{
−
1
,
0
,
+
1
}
y=ternary(x;θ, Δ)∈{−1,0,+1}, thresholds ±θ, dead-band Δ, clip limits.

Provide a soft-ternary mode (piecewise-linear or tanh+hardening) for gradient-based studies.

Optional dynamic SA (saturable absorber) model: intensity-dependent transmission with recovery time.

Readout paths

PD+TIA channels: responsivity, bandwidth (−3 dB), shot noise, thermal noise, dark current, TIA gain/GBW, DC offsets, inter-channel skew.

Camera (InGaAs) option: pixel QE @1550 nm, read noise, full-well, ADC bits, frame/line rate, rolling-vs-global shutter, fixed pattern noise, column gain mismatch. Disable “auto” behaviors in sim.

Loop plumbing (when enabled)

Latency budget (ns–µs): optics + electronics + ADC/DAC + control.

Loop filter (simple IIR/PLL-like) to stabilize; include gain margin and phase margin.

Optional clock recovery / symbol timing error / jitter injection.

3) Non-Obvious Effects to Emulate (these will break naïve sims)

ASE noise & noise figure: EDFA adds broadband ASE; SOA adds excess noise + XGM. Track OSNR per channel.

Gain saturation dynamics: SOA gain depends on recent power (carrier lifetime). Create pattern dependence and inter-channel coupling in the loop.

WDM filter shape: finite skirt steepness → adjacent-channel leakage, passband ripple → amplitude ripple across symbols.

MDM crosstalk & DGD: slight mode coupling and delay skew reduce effective orthogonality; simulate as a tunable Hermitian perturbation and per-mode group delay.

Polarization effects: slow drift & PMD cause weight drift; require periodic re-calibration.

Component variability: per-port insertion loss scatter (±0.2–0.5 dB), temperature drift of gains/filters, VOAs with hysteresis and non-monotonic regions.

Readout electronics: finite bandwidth (ISI), AC-coupling baselines, clipping, ADC quantization.

Calibration error: finite resolution, noisy measurements, stale calibration between updates.

Clock/data mis-alignment: sampling phase error, jitter accumulation, per-λ skew.

If you include these, the emulator will stop returning “0.0 error rate” and become predictive.

4) Ternary Design (our “secret sauce”)—what to model

Threshold adaptation: auto-tune ±θ and dead-band Δ per channel to hit target sparsity or BER. Include slow drift & re-lock.

Hysteresis & recovery: give the nonlinearity a time constant (ms–µs) to emulate optical SA recovery or electronic latch-like effects.

Differential encoding: for signed outputs, simulate balanced PDs and common-mode rejection; model CMC/DMR limits.

Precision-vs-noise study: sweep OSNR & threshold to map the robustness of ternary vs analog vs binary.

5) Microsoft AOC vs Our Rig—what to borrow for the twin

Common themes to emulate

Co-design of hardware + algorithm: add “solver-side” degrees of freedom (e.g., proximal/ISTA-like iterations, fixed-point search, reservoir readout training).

Digital twin fidelity: AOC emphasizes a realistic twin; for us, add device-calibrated parameters (gain curves, tilt, noise) once hardware arrives.

Test-time compute: model iterative refinement (multiple optical passes) and measure energy/latency vs accuracy.

Key differences to reflect

AOC uses free-space projector/SLM + camera (Si sensors, visible/NIR). We use C-band telecom WDM/MDM, SOA/EDFA, InGaAs readouts.

AOC weights live in spatial light patterns; our weights live in tap ratios, phases, VOAs. Constrain 
𝑊
W accordingly (non-negative amplitude + phase if available; limited resolution).

We rely on ternary activations deliberately; AOC is more analog-continuous. Keep this distinction.

6) Performance Accounting (speed/throughput/energy)

Build these counters into the twin:

Symbol rate per channel (e.g., 10–25 Gbaud realistic with telecom front-ends; sim should allow 1–50 Gbaud sweep).

Parallelism = (#λ) × (#modes) × (#spatial outputs), and fan-in/out per mixing stage.

Ops proxy: count MAC-equivalents as energy accumulated through mixing graph (even if purely physical).

Energy model: per component energy/bit (laser wall power per useful photon, SOA/EDFA electrical draw vs output, TIA/ADC power).

Latency: one-pass latency & loop round-trip.

Accuracy: task-level metrics (classification, regression, reservoir prediction) under injected non-idealities.

Provide dashboards that plot accuracy vs (OSNR, symbol rate, #λ, #modes, loop gain), and energy/bit vs accuracy.

7) Calibration & Control Routines (simulate the workflow)

Power leveling: per-λ VOA closed loop to flatten powers at readout (inject meter noise & lag).

Filter centering: WDM alignment by dithering and maximizing passband metrics.

Mode alignment: estimate/correct MDM crosstalk using a measured mixing matrix; apply pre-whitening.

Threshold auto-set: sweep θ, choose by target sparsity/BER; periodically re-trim.

Loop stabilization: gain/phase margins; if oscillation detected, auto-reduce gain or insert extra delay.

Health monitor: drift detectors, OSNR alarms, saturation flags, “suggest recalibration” events.

These are algorithms in the twin, not just parameters—please implement them, complete with imperfections.

8) Readout Paths: PD array vs Camera
PD/TIA bank (baseline)

Many channels, GHz-class BW, lowest latency.

Model per-channel BW limit, noise spectrum, offsets, and cross-talk via ground/shared rails.

InGaAs camera (MDM)

High fan-out; lower line/frame rate; larger pixels → shot-noise-limited regimes differ.

Model ROI binning, rolling-shutter skew, and pixel response non-uniformity; expose a “calibrate flat-field” routine.

9) Input Encoding & “Weights”

Prompt/context encoding: provide two modes

Digital front-end computes an input vector and programs optical amplitudes/phases (DAC + modulator model in sim).

Pre-burned weights: constrain 
𝑊
W to physically feasible settings; quantify programming time & granularity.

Signed weights: differential paths + balanced PDs; simulate mismatch & finite CMRR.

10) Test Plan & Fear Factors (what should break)

Run these scripted sweeps:

Noise wall: increase ASE, RIN → track when ternary collapses; map OSNR vs accuracy.

SOA dynamics: push pattern-dependent distortion; observe loop bias drift and instability.

WDM guard bands: shrink channel spacing; increase leakage; measure accuracy fall-off.

MDM crosstalk: sweep mode Xtalk −30 dB → −12 dB; assess mitigation via pre-whitening.

Calibration staleness: freeze trims and drift components; measure hour-scale performance decay.

Timing/jitter: add sampling skew and PLL jitter in the loop; find required margins.

Throughput scaling: plot accuracy/energy vs (#λ, #modes, symbol rate); identify diminishing returns.

If the emulator still reports “perfect” after these, it’s not realistic enough.

11) Software Architecture Hints

Composable device models with JSON/YAML configs; deterministic RNG seeds for repeatability.

Time-domain engine with variable step (to handle SOA dynamics) and a symbol-synchronous fast path for steady-state sweeps.

Auto-differentiable option (PyTorch/JAX wrapper) around the physics for co-design experiments (e.g., training readouts under non-idealities).

Knob-to-hardware mapping table so UI sliders match real dials later.

12) What to record for hardware correlation (later)

Per-λ gain curve, tilt, and noise figure; SOA P_sat and lifetime; filter S-parameters; PD/TIA NEP & BW; camera flat-field and noise.

Store these as calibration profiles the twin can load.

TL;DR for the developer

Build a constrained linear-nonlinear-noisy loop simulator with WDM/MDM, SOA/EDFA, ternary activation, and realistic readouts (PD bank, optional InGaAs camera).

Make non-idealities first-class citizens (ASE, saturation dynamics, crosstalk, PMD, filter ripple, thermal drift, ADC/TIA limits).

Include calibration algorithms (not just ideal setters), complete with sensor noise and lag.

Add performance counters (throughput, OSNR, energy, latency, accuracy) and scaling sweeps across λ/modes/symbol rate.

Provide both one-pass MVP and looping modes.

Do this, and the twin will (a) stop giving fairy-tale results, (b) guide parts purchases, and (c) keep paying off as our lab rig grows from 1-λ MVP to an 8-λ tile and beyond.