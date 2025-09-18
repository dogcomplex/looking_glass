Please analyze this repo and determine a series of probing tests to try and push for results which maximize the following properties:

- accuracy: minimal total BER (i.e. 0.065 achieved or 0.00)
- consistency against realistic environmental noise
- realistic components pulled from actual purchasable products
- lower priced products where possible (figuring out which ones are critical and which are less important for scaling)
- total average speed / cycle time (though schemes which use an initial/periodic slow calibration or slow input read over many cycles may be acceptable - especially if the subsequent cycles for multiple layers are short)
- uses analog cycling ("path B") to emulate multiple hidden transformer layers before a final camera readout (though prefer accuracy first with single-path runs before attempting looping)
- shows both analog input (read from static "cold" etched glass/crystal with its own seek/read movement delays) and digital input (read from digital-to-analog "hot" emitters, delayed by the device + the digital data lookup speed).
- uses inherent delays from either input method intelligently as slack for the rest of the system
- aims for highest achievable throughputs, given all other constraints.  Aims to characterize tiers of quality/quantity vs cost/complexity/stability.
- above all aims for realism.  NEVER sacrifices realistic conditions and realistic products for easy simulation cheats (except as well-marked temporary measures while calibrating)
 
With those heuristics in mind, please proceed to develop testing plans using and improving our simulation code to try and narrow down best simulation parameters and characterize what we're capable of.  Where you see missing, incorrect, or needing-refinement features please suggest the code changes and keep moving on

Try to proceed with one probe at a time, analyzing the data, then adjusting accordingly for the next probe.   Try to do this all by running your own test queries, and don't rely on the human user and dashboard at all if you can.  Try to run as many probes and tests per session one after the other as you can manage before hitting session limits.

Be careful to make non-destructive changes where possible, at least when modifying params/probes, so you can still access the history of progress.  (Functional code changes can still be destructive if necessary)  

Try to give brief layman summaries of progress on what was achieved where relevant, to mark progress.  Try to track and update the history of what was tried to avoid repeating past mistakes.

Please proceed with designing your next test probes.

UPDATE: we now use a queue design to set probes to run, which is run by an external process.

APPEND ONLY to queue/probes.jsonl
NEVER modify queue/completed.jsonl

## Current progress and added capabilities (update)

- Best reproducible Path A combo in sim: E2+C2+B2 overlays at 19.0 ns (optics power/contrast, low‑noise TIA, tuned comparator). Achieved 0.0625 on one seed with avg2 + lite gating (0.6 mV, +1); most seeds plateau at 0.125 → margin limited.
- Implemented and queued:
  - Lite confidence gating and small averaging (avg2/avg3); per‑channel vth/linear optimizers; mask mode (error/dvspan); decoders (linear/MLP) and ECC; decoder fusion; deblur; MAP.
  - Queue runner improvements (overlay pack merge for cmd jobs; skip policy for error signatures); multiple appender scripts for targeted suites.
  - Stress tests: comparator overrides; optics CT/stray; TIA gain variation; speckle/fringe multiplicative noise (new); comparator metastability near zero (new); drift stress and drift schedules with periodic re-trim.

Observed outcomes (sim):
- Primary Path A BER is stable at 0.125 across seeds/settings unless extra margin is emulated; advanced post‑processing (replicate/vote/decoder/ECC) does not improve without SNR.
- Stress/invalidations did not catastrophically break the robust preset (avg3 + lite gating); they mostly inflate baseline, not primary. Drift schedules with periodic re‑trim held at 0.125.

## Bench plan and acceptance gates (actionable)

- Build a 16–32 ch micro‑rig (laser + engineered diffuser + baffles; low‑noise TIA; fast comparator with per‑channel DAC vth trims; TEC on emitter/sensor; clean clock). Optionally AOM for modulation depth.
- Acceptance gates:
  - Robust: avg3 @ 19.0 ns, mask ~0.09375, ≤0.09375 BER across ≥3 seeds, window ±0.05 ns, stable 30 min.
  - Fast: avg2 + lite gate (0.6 mV, +1) ≤0.065 on ≥2 seeds.
- If pass, scale channels / add modulation depth (AOM/BOA/EDFA). If fail, stop or re‑scope.

## MoE compensation and utility (sim result)

- Replication/vote classifiers did not reduce BER (errors are not independent). Linear decoder + ECC showed no consistent lift at current margin.
- Practical recipe remains: masking + small averaging + lite gating. This remains useful for an optical feature extractor feeding a digital head trained to tolerate structured noise.

## Invalidation stress (sim-only)

- Optics CT/stray, TIA gain variance, comparator noise/sigma, speckle/fringes, comparator metastability, and drift schedules (with periodic re‑trim) did not collapse primary BER; robust preset remained at 0.125 across seeds/jitter. Conclusion: the simulator is margin‑limited, not brittle; real SNR lifts are required.

## Path B and cold analog input status

- Path B (optical ternary loop) hooks exist (amp/SA and `--path-b-depth`), but queued runs used `--no-path-b`; we have not executed full recursion suites yet.
- Cold analog input is supported (cold reader), but queued runs used `--no-cold-input`; we have not executed cold‑input suites yet.
- Next (sim-only):
  - Append a compact Path B suite (depth 1–3) with SA+amp enabled; measure BER vs depth and gain/saturation; compare to Path A.
  - Append a cold‑input suite to characterize baseline vs digital emission under identical optics/TIA/comparator settings.
  - Elevate any promising Path B/cold recipes into bench acceptance presets.

## Two bench‑ready presets to carry forward

- Fast: 19.0 ns; avg2; mask ~0.09375; lite gating (0.6 mV, +1); tuned comparator/TIA; power/contrast optics.
- Robust: same, avg3 with lite gating; periodic re‑trim cadence validated by drift schedules.

---

## Update — C‑band harsh realism progress & goals (2025‑09‑05)

### Scope covered (sim realism now on by default in harsh suites)
- 1550 nm C‑band: DFB linewidth/coherence, RIN propagation, wavelength drift labels (Δλ variants).
- Passive plant: per‑pass IL jitter, PDL random walk + scrambler, DWDM ripple/poor isolation, back‑reflections (APC/PC), PM vs SMF proxies.
- Nonlinear blocks: EDFA ASE with OBPF, SOA saturation + simple memory, XGM/XPM/FWM proxies.
- Electronics: PD shot/thermal, TIA poles + slew (100–300 MHz; variants to 3 GHz for sub‑ns studies), comparator noise/jitter/metastability.
- Timing: clock jitter 20–30 ps, PMD/GDR proxies, lane‑skew proxy. Calibration: normalize + lite gating + small averaging (weak‑cal) with bounded strength.

### Key results (EDFA‑8 tile unless noted)
- Must‑fail then pass demonstrated:
  - No‑cal / no‑gate: BER 0.625–0.75 at 6/8/10 ns under harsh/ultra conditions; weak‑cal rescues to 0.0.
  - Ultra marginality (metastability + 30 ps jitter): EDFA‑8 0.75 at 6 ns; SOA‑1 remains 0.0.
- λ drift: step tests at +0.2 nm passed with weak‑cal at 6 ns (need continuous ramps next).
- Connectors/fiber: APC+PM, APC+SMF, PC+PM all passed at 6 ns with weak‑cal (penalties visible without cal).
- Power sweeps (base/40/60 mW): all passed at 6 ns with weak‑cal; XGM floor shows only when calibration is disabled or isolation worsens.
- SOA burst memory (depth 12/16/24/32): no‑cal at 6 ns remained 0.0 (need explicit burst pattern driver for stronger effect).

### Bottlenecks and speed outlook
- With current packs (100–300 MHz TIA, ~1.25 ns comparator delay, 20–30 ps jitter), practical UI: 5–10 ns.
- For ≤1 ns UI: need ≥1–3 GHz TIA, fast SA (≤100 ps) + fast SOA (τc ≲100 ps), EOM gating, very short per‑hop path (≤5 cm), jitter ≲10 ps, PM fiber + APC connectors, tight OBPF. Expected achievable UI: 0.8–1.5 ns with careful tuning.

### Next goals (queued/queued‑next)
- Bulk critique sweeps (power, jitter, λ drift, connectors/fiber, SOA bursts) — appended and running; aggregate BER/tokens/s/energy and pick cheapest configs that pass at 6–10 ns.
- Continuous λ ramp (+0.4 → +1.0 nm day‑scale proxy) with bounded calibration; report BER vs Δλ and re‑trims/hour.
- Control‑loop realism: quantized VOAs (e.g., 0.25 dB steps), DAC Vth quantization/INL, limited bandwidth; measure calibration duty cycle to hold ≤0.125 at 6 ns.
- Dual‑threshold ternary (dead‑zone variability) and class‑conditional noise metrics; add confusion matrices and dead‑zone occupancy to outputs.
- Sub‑ns feasibility: GHz‑grade stack sweep (TIA ≥3 GHz, fast SOA/SA proxies) at 1.5/1.2/1.0/0.8 ns to map BER degradation.

### Acceptance gates (harsh C‑band)
- 6 ns, EDFA‑8 tile, weak‑cal: ≤0.065 BER across ≥3 seeds with scrambler/ripple on; stable for 30 min equivalent drift.
- 1.0–1.5 ns exploratory: show monotonic BER trend and identify first failing component; document power/SNR margins and required re‑trim cadence.
## Pragmatic Build Strategy Update (2025-09-17)

### Split-Array Direction
- For configurations beyond 8 logical channels we will deploy **multiple independent 4�8 channel optical arrays** instead of a single large tile. This keeps per-array analog margin high while allowing channel scaling through duplication.
- Each array should remain as cost-efficient as possible: mid-power C-band DFB (�12 mW/channel), medium-loss fiber loop optics (0.72 transmittance, -30 dB neighbor crosstalk), low-noise but off-the-shelf TIA (�15 kO / 55 MHz / 3.6 pA/vHz), and the tuned comparator overlay.
- Control software should treat arrays as parallel workers with shared digital aggregation; no additional physical coupling is assumed in the near term.

### MVP Single-Channel Validation
- Before investing in multi-channel array builds, run the same hardware pack with **only one active channel** enabled. This is the bare-minimum MVP to validate optics/TIA/comparator alignment and mitigation code paths.
- Use chop + avg2 + lite gating (0.6 mV threshold, +1 frame), light masking (=6%) and per-channel calibration. The one-channel run should hit **p50 BER = 0** at 6�8 ns (see `out/boost_medium_w6.json`).

### Current Best Recipes
- **Prosumer 8-channel @ 6�8 ns (p50 BER = 0.0):** boosted emitter, medium optics, low-noise TIA, tuned comparator, chop + avg2, lite gating, mask�6%, DV normalization.
- **16-channel @ 10 ns (p50 BER � 0.13 ? 0.08 with heavier gating/mask):** same stack; requires additional analog margin (higher power or tighter crosstalk) before it reaches zero BER.
- **Cost-reduced 8-channel @ 10 ns (p50 BER = 0.0 with mitigations):** medium optics + boosted emitter + low-cost TIA/comparator; chop + gating are mandatory. Removing either swings BER back above 0.12.
- **Harsh 6 ns stress (metastability + nonlinear overlays):** zero BER only with the full mitigation bundle (chop, avg2, gate, mask, calibration, normalization). Any knob removal produces =0.1 BER.

### Action Items
1. Map analog SNR requirements for the 16-channel 6 ns target by sweeping emitter power (12 ? 15 mW) and TIA noise while keeping mitigation constant.
2. Test optical crosstalk controls (`--lock-optics-ct`, spatial oversampling) to determine whether 16�32 channel splits can share optics without new hardware.
3. Explore chop+lock-in hybrids or adaptive gating budgets to reduce average frame count without losing the BER floor.
4. Formalize test plans for one-channel MVP and 4�8-channel split arrays so the queue runner can exercise them regularly.
### Low-Cost 8-Channel Stack Validation (2025-09-17)
- Setup: 8 channels at 6.0 ns with chop + avg2 + lite gate (0.6 mV / +1 frame), low-crosstalk optics (`configs/packs/tmp_codex_optics_lowct.yaml`), decoder linearization, and 6.25% masking.
- LED emitters: both the baseline (`tmp_led_array.yaml`) and harsher `tmp_led_array_stress.yaml` kept Path A p50 BER at 0.0 (`out/splitarray_w6_led.json`, `out/splitarray_w6_led_stress.json`).
- Sensors & front-end: swapping to the budget InGaAs array (`tmp_budget_sensor.yaml`), low-cost TIA (`tmp_budget_tia.yaml`), and noisy comparator (`tmp_budget_comparator.yaml`) each preserved the zero-BER floor (`out/splitarray_w6_led_budgetSensor.json`, `..._budgetTIA.json`, `..._budgetComparator.json`).
- Full bargain stack: stress LED + budget sensor/TIA/comparator + high-jitter clock (`tmp_budget_clock.yaml`) still achieved p50 BER = 0.0 even without masking; removing averaging/gating (avg1, gate off) held p50 BER at 0.0 (`out/splitarray_w6_led_allBudget*.json`). Baseline (no mitigations) remains at p50 BER ~0.125.
- Next stress knobs: raise neighbor CT toward -25 dB, increase stray floor, or introduce thermal drift/jitter beyond 45 ps to map the failure boundary before locking hardware choices.
### 1550 nm Tile Synthesis Notes (2025-09-17)
- Dual-wavelength 16-channel tile (configs/packs/overlays/emitter_dual_wdm.yaml + optics_mode_mix_dual.yaml) holds p50 BER �0.133 with chop+avg2 at 6 ns; baseline remains 0.6875 (out/tile16_wdm_dual.json). The mode-mix overlay (75/25 pair coupling) plus 6-bit VOA quantization and SOA pattern memory now exercise the new Optics hooks.
- Path B baseline (8-channel, SA/amp enabled) reports analog-depth p50 BER �0.625 with cold-input BER �0.375 while Path A stays at zero (out/tile8_pathb_baseline.json), providing the loop-ready datapoint called out in design_1550nm.md.
- Stress configs (	ile8_ctstress_cal.json, 	ile8_ctstress_nomitig.json, _nocal, _avg_nomitig) confirm calibration + mitigations resist heavy CT/drift/jitter; removing mitigations pushes BER to 0.625, setting the failure boundary for documentation.
## Priority B Analog Loop Experiments (2025-09-18)

- Implemented two-stage SOA+limiter stack in `looking_glass/sim/optics.py`, adding the saturable absorber (`sat_abs_on`) and a hard `tanh` clip (`hard_clip_on`) to mimic a telecom 2R/3R clamp.
- Added the digital guard pipeline (`--path-b-digital-guard`, `--path-b-digital-deadzone-mV`, `--path-b-digital-guard-passes`) so the analog cascade can replay the loop, average DV, and apply a dead-zone sign correction (see `examples/test.py:749-805`).
- Introduced balanced-PD support via `--path-b-balanced`, pushing the PD/TIA path into differential mode (`SystemParams.balanced_pd` and `Orchestrator.step`).
- New overlays: `optics_pathb_soa_sa.yaml` (SOA + saturable absorber + hard clip) plus `optics_pathb_soa_sa_ch1.yaml` and ideal TIA/comparator/sensor packs for �best case� tests.
- Results so far:
  - `out/pathb_sa_dual.json` (SOA+SA+hard clip, digital guard 5�, no balanced PD) still reports Path?B p50?BER = 0.625 (analog cascade 0.75).
  - `out/pathb_sa_dual_bal.json` (same stack + balanced PD) worsens the analog cascade to 1.0 while Path?B median stays 0.625.
  - Earlier pure-digital guard runs (`out/pathb_dguard.json`) and SOA+SA sweeps (`out/pathb_sa8.json`, `out/pathb_sa8_hi.json`) all plateaued at �0.625.
- Interpretation: even with aggressive limiting, differential bias servo, and digital averaging, the loop never develops a stable ternary rail. Next steps: tighten the limiter further (lower `hard_clip_sat_mw`, higher `sat_alpha`), add a true second limiter stage (post-MZI clip), or revisit the optics topology (balanced splitter before the SOA, cascaded SA stages).
- Added optional hard and post clips (`hard_clip_on`, `post_clip_on`) plus balanced-PD mode, but even with extreme clipping (sat_abs 0.12 mW, hard tanh at 0.06 mW, post clip 0.04 mW) Path B stayed at p50 BER 0.625 (balanced analog cascade hit 1.0) � see `out/pathb_sa_dual.json`.
