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
### Path B Contraction Sweep (2025-09-18)
- Implemented per-run return-map instrumentation (`_compute_pathb_return_map`) capturing per-stage slopes, dead-zone and rail occupancy, plus absolute diff-in/out magnitudes. All Path B JSON artefacts now expose `median_stage_slope`, `stage_diff_in`, and `stage_diff_out` for post-analysis.
- Swept VOA post-limiter attenuation, SA strength, SOA gain/tau, limiter stacks, EDFA swaps, digital guard, and comparator thresholds. The dominant failure mode is stage-0 amplitude collapse: diff_out/diff_in �4e-4 with the original SOA pack.
- Increasing SOA small-signal gain to +3 dB, extending carrier lifetime to 20 ns, and raising P_sat to 20 mW (pack `tmp_codex_optics_medium_voa2_soa_tuned.yaml`) restores stage-0 contraction to �0.2 with absolute DV ~2 V. With balanced PD and comparator `vth=20 mV`, the analog cascade reaches **p50 BER � 0.3125** (depth 3�5), a 2� improvement over the prior 0.625 plateau (`out/pathb_voa2_soa_tuned_balanced_cmp20.json`).
- Later stages still fall toward the comparator dead-zone; DV shrinks from ~2 V at stage 0 to ~80 mV by stage 4, so zero-protect thresholds eventually suppress rails. Lowering `vth` reintroduces metastable flips; raising it removes zero flips but pushes BER back >0.5. Digital guard/averaging could not arrest this decay.
- Retimer gating, EDFA + OBPF, and aggressive limiter stacks all destabilised the loop (|g'|>1) without calibrated stage gain. The queue-free probes show contraction alone is insufficient; we need stage-aware gain/threshold tuning to keep rails alive through the depth we care about.
- Hardware inference: the tuned SOA recipe implies moderate gain blocks (~+3 dB) and longer recovery in the loop (slower carriers or higher bias). Balanced detection and low-noise comparators become non-negotiable; comparator trims around �20 mV with per-channel DACs are required to prevent a zero-bias collapse.
### Path B Stage-Gain + Vth Schedule Sweep (2025-09-18, Session B)
- Added `configs/packs/tmp_codex_optics_medium_voa2_soa_strongsa.yaml` (sat_I_sat 0.6, sat_alpha 1.2) to tighten the saturable absorber without changing the 3 dB SOA gain recipe.
- Stage-gain exploration:
  - `out/pathb_stagegain_vth_sched_b.json` (pack: `tmp_codex_optics_medium_voa2_soa_tuned.yaml`, stage gains `0,0,-0.25,-0.5,-0.75`, vth schedule fixed at 25 mV) kept analog BER at 0.3125 but the return map still showed |g|>2 for the zero-state (noise expansion), so the loop is formally unstable even though the rails look good early on.
  - Increasing early attenuation (`--path-b-stage-gains-db "6.0,3.0,0,0,0"`) finally forced all stage slopes <1, but the � rails collapsed to ~7e-3 mW by stage 5 and analog BER regressed to 0.625 (`out/pathb_stagegain_vth_sched_h.json`).
- With the "strongSA" pack and a milder schedule (`--path-b-stage-gains-db "4.0,1.5,0,-0.25,-0.25"`, `--path-b-vth-schedule "25,25,18,14,10"`, balanced PD, amp=SOA) we hit:
  - `out/pathb_strongsa_sched5.json`: median stage slope 0.64, max 0.999; final rail diff �7.6e-2 mW; analog p50 BER 0.4375. Dead-zone occupancy stays ~0.8 of channels, so zeros still dominate late stages even in the contractive regime.
- Takeaways: we can now dial the first two stages into contraction without destabilising later stages, but analog BER plateaus around 0.44 because the comparator threshold schedule still swallows the rails once DV <80 mV. Next passes should combine a lighter first-stage loss (3.5�4 dB) with adaptive vth trims or per-stage guard injection so the zeros stop pinning the loop.
### Path B Chain Instrumentation Fix (2025-09-18, Session B cont.)
- Patched `examples/test.py` to funnel the analog cascade through `_run_pathb_stage_pass` and accumulate per-stage outputs. `path_b_chain` is now populated with median BER vs previous/initial stage for all runs with `--path-b-depth > 0` (e.g. `out/pathb_voa2_depth5_basic_new.json`, `out/pathb_strongsa_sched5_new.json`).
- The servo knobs (`--path-b-servo-eta`) and guard options still hook in; stage-gain/vth schedules now share the same simulation path as the return-map helper, so the JSON contains consistent `path_b`, `path_b_chain`, and `path_b_return_map` blocks.
- Null `path_b` records from older runs (`out/pathb_voa2_depth5_basic.json`, etc.) predate this fix; rerunning the probe overwrites them with the populated structure.
### Path B First-Stage Attenuation + Servo Sweep (2025-09-18, evening)
- Stage gain variants on the strong-SA pack (`configs/packs/tmp_codex_optics_medium_voa2_soa_strongsa.yaml`, balanced PD, vth schedule 25/25/18/14/10):
  - `out/pathb_strongsa_sched7.json` (`3.5,1.0,0,-0.25,-0.25`): analog p50 BER stayed at 0.4375. Median stage slope 0.645; zero-state slope creeps >1.12 so contraction still marginal. Dead-zone occupancy ~0.75 by stage 5 despite milder loss.
  - `out/pathb_strongsa_sched8.json` (`3.25,0.75,0,-0.25,-0.25`) and `..._sched9.json` (`3.0,0.5,0,-0.25,-0.25`) further relaxed the early attenuation, but analog p50 BER held at 0.4375 while zero-stage slopes spiked (max 1.19�1.26). Rails persist, yet zeros flood back in the later stages.
- Comparator servo tests:
  - `out/pathb_strongsa_sched5_servo001.json` (? = 0.01) nudged thresholds each replay but worsened analog BER to 0.50 with no reduction in dead-zone fraction (~0.81).
  - `out/pathb_strongsa_sched5_servo0005.json` (? = 0.005 + digital guard 5 mV dead-zone) regressed to analog BER 0.6875; the servo drifted thresholds toward zero and amplified zero-state dominance.
- Conclusion: first-stage attenuation alone cannot fix the late-stage amplitude decay, and static servo nudges destabilize the ternary rails. Next iteration should introduce per-stage gain *while simultaneously biasing comparator thresholds downward* (e.g., staged vth schedule <10 mV) and possibly relocate guard injection into `_run_pathb_stage_pass` so it influences each hop instead of the tail only.
### Session Summary & Next Steps (2025-09-18, late)
- Implemented `_run_pathb_stage_pass` helper in `examples/test.py` so Path B always yields `path_b`, `path_b_chain`, and `path_b_return_map`. Baseline reruns now show analog BER, per-stage BER vs previous/initial, and contraction metrics without manual inspection (`out/pathb_voa2_depth5_basic_new.json`).
- Swept first-stage attenuation with the strong-SA pack (`out/pathb_strongsa_sched7/8/9.json`). Results: analog p50 BER stuck at 0.4375 while zero-state slopes >1.2 and stage-5 dead-zone fraction =0.62. Pure attenuation isn�t enough; the loop needs comparator bias relief or gain re-injection at later stages.
- Comparator servo experiments (`out/pathb_strongsa_sched5_servo001.json`, `...servo0005.json`) showed threshold drift toward zero, increasing BER (0.50�0.69). Static eta without stage-aware limits is counterproductive.
- Overall alignment with `design_1550nm.md` bundle: we completed P1/P2-style contraction sweeps, introduced VOA tuning, and validated balanced PD. Retimer (P3), EDFA swap (P6), and drift/cost-down tasks remain outstanding.
- Action plan: (1) add per-stage comparator targets (<10 mV final) and consider in-loop guard injection; (2) spin a single-channel Path B probe to prove contraction/rails without multi-channel crosstalk, then scale back up; (3) resume P3 retimer tests and compare SOA vs EDFA once contraction is stabilized.
### Single-Channel Path B Probe (2025-09-18, late night)
- Config: channels=1, strong-SA pack (`tmp_codex_optics_medium_voa2_soa_strongsa_single.yaml`), balanced PD, stage gains `2.0,1.0,0,-0.25,-0.25`, vth schedule `12,12,8,6,5`.
- Results (`out/pathb_singlech_vthlow.json` @ 10 ns): analog cascade zeroed BER (analog_p50_ber = 0.0) and return-map slopes `median�0.76`, `max�1.57`; dead-zone occupancy = 0.0. Digital Path B BER is 1.0 because the final comparator still thresholds near zero�stage0 outputs settle at 0 vs �1.
- Lower attenuation (`out/pathb_singlech_baseline.json`, `..._voa1.json`) shows the same signature: analog state holds rails, but comparator gating collapses them due to tight hysteresis and high vth. Shorter window (6 ns, `out/pathb_singlech_vthlow_6ns.json`) preserves the rails but pushes |g'| up to ~1.81.
- Takeaway: Single-channel loop confirms the optical limiter stack can maintain rails; the failure is entirely the digital guard/comparator threshold. Next change should bias the comparator down (<=5 mV) or use per-stage guard injection before the comparator so the final decision doesn�t obliterate � rails.
### Multi-Channel Scaling Attempt (2025-09-19 early)
- 4-channel sweep with moderate crosstalk (`configs/packs/tmp_codex_optics_medium_voa2_soa_strongsa_ch4.yaml`): stage gains `2.0,1.0,0,-0.25,-0.25`, comparator vth down to 3 mV, and balanced PD. Results across `out/pathb_ch4_baseline.json`, `..._vthlow.json`, `..._vthlow_stagegain.json`, `..._vthlow_bias.json` all landed at Path B p50 BER = 0.75 (analog BER 0.25) with stage-5 dead-zone fraction ~0.25. The return map shows stage-0 BER 0.5 against the inputs, meaning the comparator flips half the rails immediately even though the optical rails remain �.
- Lowering comparator Vth or adding extra post-stage attenuation did not reduce the zero-occupancy; instead, the median slopes grew (>0.8) and a zero bias persisted. Servo eta (0.02) again failed to recover rails, matching the single-channel behaviour.
- Observation: With multiple channels the comparator needs per-channel trim (or a differential offset) right after stage 0. Without that, half the rails walk into the dead-zone even when the optical limiter holds �. Next step should run the single-channel best recipe with per-channel trim (e.g. map comparator Vth from the sweep) before scaling to 4/8/16.
### Comparator Trim Insight (2025-09-19)
- Return-map diff_out for 4 ch (`out/pathb_ch4_baseline.json`) shows stage-0 rail magnitude ~1.42 mW (after limiter). Mapping through PD/TIA (~15 kO, 55 MHz) implies �~20 mV at comparator input, so the static 5 mV threshold is too close to zero and lets thermal noise flip rails. Use per-channel trim from calibration (or set vth schedule to 15?8?5?3?2 mV) before scaling channels. TODO: add per-channel `set_vth_per_channel` calibration pass after `_run_pathb_stage_pass` using diff_out median.
### 4-Channel Vth Inline Attempt (2025-09-19)
- Derived per-channel comparator trims from `_run_pathb_stage_pass` median |dv| (�47�48 mV) ? ~9.5 mV thresholds (`--vth-inline 9.399,9.619,9.521,9.570`).
- Run (`out/pathb_ch4_vthinline.json`) still reports Path B p50 BER = 0.75; stage 0 BER vs input remains 0.5. Return map shows level-0 diff_out �2.5 �W, i.e., optics bias drives the comparator positive even when ternary input = 0. The problem is offset, not threshold magnitude. We need zero-centering (per-channel offset or guard subtraction) before thresholds help.
### Comparator Offset Measurement (2025-09-19)
- Measured stage-0 comparator dv using `_run_pathb_stage_pass`: for 4-channel run, zero-input dv spans [-19.5, -10.7, -6.1, +36.1] mV while � rails sit near �1.48 V. That bias explains the 0.75 BER�two channels start negative, one positive, one heavily positive.
- Simple threshold trims (`--vth-inline` or scaled medians) cannot overcome the offset because the zero bias differs per channel; we need per-channel offset cancellation (hardware DAC or digital subtraction) before thresholding.
- Next task: prototype an offset calibration in sim (capture zero-level diff and subtract before comparator) to emulate per-channel DAC, then re-evaluate Path B across 4/8/16 channels.
### Comparator Auto-Zero Prototype (2025-09-19)
- Added per-channel auto-zero option (`--path-b-calibrate-vth`) and `Comparator.set_offset_per_channel()`. The calibration pass samples zero-input dv (guard disabled), stores offsets, and optionally records recommended vth trims (scale factor).
- 4-channel run with auto-zero (`out/pathb_ch4_auto_zero.json`): offsets converge to [-7, +28, -11, +5] mV, trimming thresholds to ~7�9 mV. Path B p50 BER stays at 0.75 (analog 0.25); stage-0 BER vs initial remains 0.5.
- Interpretation: comparator offset/DAC fixes bias, but the optical stage itself still flips half the rails on the first pass. Next experiments need stage-aware gain/threshold tuning (or alternative optical topology) before pursuing retimer/EDFA work.
### Comparator Auto-Zero + Stage Bias Findings (2025-09-19)
- Added per-channel auto-zero (`--path-b-calibrate-vth`) and comparator offset storage. Offsets shrink to �10 mV, but Path B BER still stalls at ~0.75.
- Extracted stage-0 optical bias (`calibrated_optical_bias_mW`), tried subtracting it before the comparator: negligible improvement (rails still flip). Larger stage gains or removing guard just saturate or reintroduce bias; the analog cascade still can�t hold ternary rails after stage 0.
- Implication: to move past the 0.75 plateau we need per-channel optical bias control (e.g., small VOA/MZM trims). That�s the non-obvious decision point for hardware: the comparator DAC is necessary but insufficient.
### Path B Comparator Auto-Zero & Bias Characterization (2025-09-19)
- Implemented per-channel comparator auto-zero (offset DAC) in `looking_glass/sim/comparator.py` and exposed it via `--path-b-calibrate-vth*`. Offsets now converge to �10 mV (`calibrated_offset_mV`), matching cheap offset-trim parts (~$1�$2/channel).
- Captured stage-0 optical bias during the same calibration (`calibrated_optical_bias_mW`). Even after offset trimming, 4- and 8-channel runs (`out/pathb_ch4_auto_zero*.json`, `out/pathb_ch8_auto_zero.json`) show stage-0 BER � 0.5: the comparator sees non-zero optical bias immediately after the first hop.
- Tried subtracting the measured bias in software, varying stage gains/guard, and flattening the cascade � Path B p50 BER remains � 0.75 (analog � 0.25). Conclusion: comparator tuning alone is insufficient; the optics need per-channel bias control.

### Next Steps
1. **Stage-0 optical bias trim**: add a small per-channel VOA/MZM bias (same DAC hardware) to center stage-0 outputs. Update the simulator to capture/apply that trim before comparator auto-zero.
2. **Re-run Path B sweeps**: once stage-0 bias is addressed, re-run 4?8?16 channel loops, then resume the design_1550nm roadmap (retimer P3, amplifier P6, drift/cost P8/P9).
3. **Hardware planning**: note in the hardware bill of materials that each comparator channel needs both offset trim (already modeled) and a small optical bias trim (VOA/MZM per channel).
### 1ch Path B Basic vs Scheduled (2025-09-19)
- Packs: emitter tmp_lowcost_emitter_boost, optics tmp_codex_optics_medium_voa2_soa_strongsa_single, sensor InGaAs typ, TIA stage_b2_low_noise, comparator tuned, clock jitter_20ps. Base window 10 ns. Classifier chop, avg2. normalize-dv ON. Trials 160-200.
- Probe A (basic, no balance/cal/schedule): out/pathb_1ch_strongsa_depth5.json -> analog_depth=5, analog_p50_ber=1.00; return map median slope ~0.69, max ~2.49 (unstable), no deadzone occupancy.
- Probe B (balanced PD + auto-zero + stage gains 2,1,0,-0.25,-0.25; vth schedule 12,12,8,6,5): out/pathb_1ch_strongsa_sched.json -> analog_p50_ber=0.00; return map median slope ~0.76, max ~1.64; deadzone shows a saturated middle stage in one of the three level sweeps.
- Takeaway: With per-stage gain and threshold scheduling plus balanced PD and auto-zero, a single-channel Path B loop can achieve 0.00 median BER at depth 5 under strong-SA optics. Unscheduled baseline is unstable and fails (BER 1.0).
- Next: check seed robustness (3-5 seeds) and scale to 4 channels with same schedule; then adjust SA/amp for margin vs cost.
### 1?4ch Path B Scale (2025-09-19)
- 1ch schedule held at 0.00 median BER across seeds 6004/7001/7002.
- 4ch with ch4 pack and same schedule: out/pathb_4ch_strongsa_sched.json -> analog_p50_ber=0.25. Return-map median slope ~0.75 (stable), max ~1.93; significant deadzone at stage 1 across levels (0.5 occupancy) suggests comparator biasing causing zeros during ramp.
- Next: try comparator vth schedule +3 mV and increase stage-1 gain slightly to push rails out of deadzone; then test with neighbor crosstalk softened (optics pack ch8) and evaluate masking 1 worst channel (mask 0.25) to target <0.125.
### 4ch Robustness and Tweaks (2025-09-19)
- Seeds 8001/8002/8003 with scheduled strong-SA pack: median Path B BER remains 0.25.
- Gain/vth tweak (stage gains 2.25,1,0,-0.25,-0.25; vth 15,15,10,7,6) did not change median BER (still 0.25); return map shows stage-1 deadzone persists.
- Masking 25% worst channels increased reported analog_p50_ber to 0.5, likely because the mask is applied to path_a metrics but Path B analog metric is computed post-analog chain without mask influence. We will avoid masking for Path B analog reporting and focus on improving stage-1 biasing.
- Next: try enabling optical guard injection (guard_gain ~0.1 mW, deadzone 0.2 mV) to push rails out of the deadzone, and/or add small per-channel optical bias subtraction at stage 0 during calibration.
### 4ch Guarded Scheduling (2025-09-19)
- Added optical guard (gain 0.1 mW, deadzone 0.2 mV) with scheduled gains/vths.
- Across seeds 8301/8302/8303, median Path B BER remains 0.25; return maps keep median slope ~0.754, max slope ~1.69�1.70.
- Guard does not resolve stage-1 deadzone flips; suggests per-channel optical bias trim or a stronger SA nonlinearity is needed at early stage.
- Next: run 8 ch with strong-SA ch8 pack to quantify scaling, and prototype a small per-channel optical bias subtraction at stage 0 using the measured calibrated_optical_bias in the analog pass (already partially wired) and re-test 4 ch.
### 8ch Scheduled Strong-SA (2025-09-19)
- 8ch with strong-SA ch8 pack and 1ch schedule: median Path B BER = 0.375 at depth 5. Return-map median slope ~0.754 (stable), max ~1.84; stage-1 deadzone occupancy ~0.375 across levels.
- Scaling degrades BER from 0.25 (4ch) to 0.375 (8ch), consistent with accumulated bias/crosstalk. Guard did not help at 4ch; expect similar at 8ch without per-channel optical trims.
- Next: implement stronger stage-0 optical bias subtraction during the analog pass using the calibration vector (already computed as calibrated_optical_bias_mW), then re-run 4ch and 8ch to evaluate impact.
### 4ch Stage-0 Bias Scaling (2025-09-19)
- Added --path-b-optical-bias-scale to apply calibration bias with a scale factor.
- 4ch with scales 1.5 and 2.0 leaves median BER at 0.25; return map slopes unchanged; max slope nudged (~1.96), still stable.
- Conclusion: per-channel bias subtraction alone is insufficient to break the 0.25 plateau at 4 ch. The deadzone pattern suggests early-stage nonlinearity/imbalance beyond static bias.
- Next: explore modest SA strengthening (use _soa_strongsa pack vs tuned) for 4/8 ch and revisit comparator vth schedule closer to 10/10/8/6/5 mV.
### SA/vth variants (2025-09-19)
- 4ch ch4 strong-SA with vth 10/10/8/6/5: analog p50 BER remains 0.25.
- 4ch generic strong-SA (no ch4 specialization) with vth low: analog p50 BER 0.25.
- 8ch ch8 strong-SA with vth low: analog p50 BER 0.375.
- Return-map omitted in these runs (no flag); BER behavior unchanged from prior maps that showed stage-1 deadzone.
- Conclusion: small vth tightening does not move the plateau. The next impactful knob is likely per-channel optical trim (small VOA/MZM) or more aggressive first-stage nonlinearity, which implies BOM changes. For sim purposes, we can emulate per-channel trim by injecting a tiny per-channel bias from the calibration vector at stage 0.
### TDM-style Sparse Activation (2025-09-19)
- Added sparse-activation mode: --path-b-sparse-active-k enforces K active channels per trial (others zero); --path-b-eval-active-only evaluates BER over active subset.
- 16ch strong-SA with K={1,2,4} active achieved analog p50 BER = 0.00 at depth 5 across seeds (9601..9603). This emulates time-division scanning (per-frame activates only a small subset), which greatly reduces crosstalk and stabilizes early stages.
- Interpretation: A practical MVP could run 8�16 channels by TDM scanning K active rails per cycle through the analog cascade, while keeping total window at 10 ns per micro-pass; net throughput scales with K. This provides a clear path to low BER with realistic parts by trading instantaneous parallelism for time-multiplexing.
- Next: quantify throughput vs K (effective cycles per symbol), energy, and re-evaluate pack costs; also test K=8 on 16ch and find the break point where BER rises.
### TDM vs Optics Nonlinearity (2025-09-19)
- 16ch with light-SA optics: K=4 active ? analog p50 BER 0.00; K=8 active ? 0.125. This maps a cost/performance frontier: weaker nonlinearity is viable with TDM up to moderate K.
- Throughput estimate at 10 ns window and depth=5 (no extra repeats):
  - Total micro-passes per symbol � ceil(16/K) * depth; symbol time � micro_passes * 10 ns.
  - K=4 ? ceil(16/4)*5=20 passes ? 200 ns/symbol ? 5.0 Msym/s (per bank).
  - K=8 ? ceil(16/8)*5=10 passes ? 100 ns/symbol ? 10.0 Msym/s with 0.125 BER (light-SA).
- With strong-SA, K up to 8 achieved 0.00 BER; suggests better optics increase K without BER penalty.
- Recommendation: MVP path uses TDM with K=4�8 on 16ch; choose optics tier based on allowed BER and cost. Next: compile a brief MVP plan (hardware + sim settings) in TUNING.md and queue a few long-seed sweeps for stability.
### TDM Metrics (2025-09-19)
- 16ch light-SA, K=8 ? metrics embedded in output: tdm_micro_passes=10, window_ns=10 ? 100 ns/symbol ? 10 Msym/s; BER 0.125.
- Code now emits: sparse_active_k, window_ns, tdm_micro_passes, tdm_symbol_time_ns, tdm_symbols_per_s under path_b when sparse mode is used.
- Next: run multi-seed stability sweep for (K=4,8) under light-SA and strong-SA to check variance, and outline MVP hardware config + ops recipe in TUNING.md.
### TDM Stability Sweep (2025-09-19)
- 16ch strong-SA: K=4 and K=8 ? median BER 0.00 across 3 seeds each.
- 16ch light-SA: K=4 ? 0.00; K=8 ? [0.125, 0.125, 0.00] median 0.125.
- Conclusion: TDM scanning is robust; strong-SA supports K up to 8 at 0.00 BER; light-SA supports K=4 at 0.00 and K=8 around 0.125 BER. Use K, optics tier to trade throughput vs BER/cost.
- MVP summary: Balanced PD + tuned comparator (offset trim + small vth), 10 ns window, depth 5, auto-zero at start, stage gain/vth schedule, TDM K=4�8 depending on optics. Achieves 0�0.125 BER with realistic parts and ~5�10 Msym/s per 16ch bank.
### 32ch TDM Scaling (2025-09-19)
- 32ch strong-SA:
  - K=8 active ? BER 0.00; micro_passes=20 (? 200 ns/symbol ? 5 Msym/s).
  - K=16 active ? BER 0.0625; micro_passes=10 (? 100 ns/symbol ? 10 Msym/s).
- Scaling remains favorable; we can choose K for throughput vs BER. This suggests multi-bank scaling to 32 ch is viable with TDM.
## MVP Playbook (TDM Path B) � 2025-09-19
- Hardware
  - Balanced PD/TIA path (e.g., 	ia_stage_b2_low_noise), 10 ns clock window, per-channel comparator offset trim and small vth trims.
  - Optics: choose SA tier by BER target and budget. Strong-SA supports higher K (parallelism per frame) at 0 BER; Light-SA supports moderate K (e.g., K=4 at 0 BER; K=8 at ~0.125 BER).
- Operations
  - Auto-zero comparator offsets at start; use per-stage vth/gain schedule (e.g., gains 2,1,0,-0.25,-0.25, vth 12,12,8,6,5 mV).
  - TDM scan: set --path-b-sparse-active-k K and --path-b-eval-active-only to evaluate K active channels per frame through analog depth 5; rotate subsets to cover all channels.
  - Use --normalize-dv and balanced PD. Optional: optical guard if needed (not required with TDM in our tests).
- Performance (16 ch @ 10 ns window; depth 5)
  - K=4 ? ~5 Msym/s at 0 BER (strong- or light-SA).
  - K=8 ? ~10 Msym/s at 0 BER (strong-SA) or ~0.125 BER (light-SA).
- Scaling
  - 32 ch: K=8 ? 5 Msym/s at 0 BER; K=16 ? 10 Msym/s at ~0.0625 BER (strong-SA).
- Next steps
  - Validate multi-seed stability per K, monitor drift and re-center thresholds periodically if necessary.
  - Cost down optics by lowering SA strength and compensating with smaller K.
### TDM Rotate Drill (2025-09-19)
- Added --path-b-sparse-rotate to cycle deterministic K-sized subsets across frames.
- 16ch strong-SA, K=8, rotate: BER 0.00; micro_passes=10; tdm_symbols_per_s�5.88M (longer run used 400 trials).
- Rotation confirms stable low-BER operation when cycling through all channels, matching random-subset results.
### TDM Drift Sanity (2025-09-19)
- 16ch strong-SA, K=8, rotate, longer run (400 trials) with light-output to bypass sensitivity plots: BER remains 0.00 (drift block disabled in light mode). For a heavier drift test, drop light-output and enable drift schedule.
### TDM Drift (enabled) Quick Pass (2025-09-19)
- 16ch strong-SA, K=8, rotate, 400 trials with drift enabled (no light-output): BER 0.00. This suggests robustness to modeled drift at this scale; periodic re-centering remains available but may not be needed at this SA tier and K.
- Strong-SA vs Light-SA at K=8 summary (3 seeds + drift): Strong-SA ? 0.00; Light-SA ? median 0.125 (with one 0.00 outlier), both at ~10 Msym/s.
### TDM Drift Multi-seed (2025-09-19)
- Strong-SA K=8 (rotate, 400 trials): seeds 12102/12103 ? 0.00 BER.
- Light-SA K=8: seeds 12201/12202/12203 ? [0.00, 0.125, 0.125].
- Confirms prior: strong-SA at K=8 is robust at ~10 Msym/s; light-SA at K=8 sits near ~0.125 with occasional perfect seeds. K=4 remains 0.00 for light-SA.
### Cost/Perf Sweep (2025-09-19)
- 16ch strong-SA, K=4: BER 0.00; ~5 Msym/s.
- 32ch light-SA, K=8: BER 0.0625; ~5 Msym/s.
- 32ch light-SA, K=16: BER 0.0625; ~10 Msym/s.
- Recommendation: for lower-cost optics, target light-SA with K=8�16 at 32 ch for BER ~0.0625 and 5�10 Msym/s; for zero-BER targets use strong-SA or smaller K.
### Iteration Summary and Next Directions (2025-09-19)
- Pivoted from full-parallel Path B (plateaued at 0.25�0.375 BER) to TDM sparse activation. Implemented --path-b-sparse-active-k, --path-b-eval-active-only, --path-b-sparse-rotate, and throughput metrics.
- Validated at scale:
  - 16 ch strong-SA: K=4/8 ? 0.00 BER; ~5/10 Msym/s.
  - 16 ch light-SA: K=4 ? 0.00; K=8 ? ~0.125 median; ~10 Msym/s.
  - 32 ch strong-SA: K=8 ? 0.00 (5 Msym/s); K=16 ? ~0.0625 (10 Msym/s).
  - Drift (enabled): strong-SA K=8 holds 0.00 BER.
- Tooling and docs added:
  - Scripts: scripts/run_tdm_mvp.py (suite/stability), scripts/run_scenario_tdm.py, scripts/summarize_tdm.py.
  - Scenario presets: configs/scenarios/tdm_mvp_16ch_strongsa_k8.yaml, 	dm_16_lightsa_k4.yaml, 	dm_32_strongsa_k8.yaml, 	dm_32_lightsa_k8.yaml.
  - Scenario passthrough: looking_glass/scenario.py --tdm-k/--tdm-rotate/--tdm-eval-active-only.
  - README TDM section and docs/MVP_TDM_BOM.md (hardware outline).
- Cost/perf snapshot (sim):
  - 16ch strong-SA K=4 ? 0.00 @ ~5 Msym/s; 32ch light-SA K=8/16 ? ~0.0625 @ ~5/10 Msym/s.
- Suggested next experiments:
  1) Expand cost curve: sweep optics tiers vs K at 16/32 ch; record BER/throughput and energy proxies.
  2) Add optional periodic re-center in TDM loop (every N micro-passes) and quantify drift benefit.
  3) Integrate Path A head with TDM Path B front-end for end-to-end tokens/s and accuracy tracking.
  4) Queue representative TDM runs via the probe queue (append-only) for background validation.
  5) Map minimal optics strength needed for K=8 zero-BER to refine BOM.
### Cost Curve Micro-sweep (2025-09-19)
- 16 ch strong-SA: K=4 ? BER 0.00 @ 5 Msym/s; K=8 ? 0.00 @ 10 Msym/s (seeds 15001, 15002).
- 32 ch light-SA: K=8 ? 0.125 @ 5 Msym/s; K=16 ? 0.1875 @ 10 Msym/s (seeds 15003, 15004).
- Takeaway: light-SA can hit 5 Msym/s @ ~0.125 BER (32ch K=8) and 10 Msym/s @ ~0.1875 BER (32ch K=16). Strong-SA holds 0 BER up to K=8 on 16ch.
- Next: pair TDM Path B (K=8 light/strong SA) with a Path A head to estimate end-to-end tokens/s and accuracy vs BER; extend summarize_tdm to CSV for quick spreadsheet import.
### TDM Cost Curve Summary (2025-09-19)
- Aggregate CSV written: out/tdm_costcurve_summary.csv
- 16 ch strong-SA: K=4/8 ? BER 0.00 at ~5/10 Msym/s.
- 32 ch light-SA: K=8 ? BER ~0.125 @ 5 Msym/s; K=16 ? ~0.1875 @ 10 Msym/s.
- 32 ch strong-SA: K=16 ? BER ~0.0625 @ 10 Msym/s.
- Use strong-SA for zero-BER targets at higher K; use light-SA for cost-down with K matched to BER goals.




    ### Agent Session Report (2025-09-19)
    - Added plain-English summary with costs/throughput in `REPORT.md`.
    - Instrumented confidence and energy metrics:
      - Per-step `n_bits`/`n_err` and Wilson 95% BER CIs in summaries.
      - TDM energy-per-symbol proxy (`tdm_pj_per_symbol_est`).
    - Added TDM re-centering cadence metrics (`tdm_recenter_interval/events/duty`).
    - Added TDM realism flags for switching penalties:
      - `--tdm-switch-mode {emitter|eo_switch}`, `--tdm-switch-t-ns` (+ optional off-iso/IL).
      - Reflected in `tdm_symbol_time_ns` and `tdm_symbols_per_s`.
    - Automation and CSV reporting:
      - New scripts: `scripts/summarize_tdm.py`, `scripts/run_tdm_sweep.py`.
      - Generated `out/tdm_sweep_summary2.csv` and aggregated `out/tdm_summary_all.csv` (CI, Msym/s, pJ/sym, amp/VOA/SA
        fields, e2e tokens/s).
    - Representative results (sim, CI-backed):
      - 16ch strong-SA: K=4/8 → BER 0.00 @ ~5/10 Msym/s.
      - 16ch light-SA: K=4 → 0.00 @ ~5 Msym/s; K=8 → ~0.125 @ ~10 Msym/s.
      - 32ch strong-SA: K=8 → 0.00 @ ~5 Msym/s.
      - 32ch light-SA: K=8 → ~0.125 @ ~5 Msym/s.
      - EO/WSS `t_sw=0.5 ns` reduces symbols/s by ~1% with unchanged BER.
    - End-to-end KPIs: added `end_to_end` block with combined BER (independence proxy) and tokens/s = min(Path‑A tokens/
        s, Path‑B symbols/s); summarizer extended to extract these.
    - EDFA vs SOA (initial):
      - SOA: stable (0.00 BER) for strong-SA at K=8.
      - EDFA: initial runs high BER (1.0 → ~0.875) with nudges (post-VOA, SA/post-clip); created `configs/packs/
        tmp_codex_optics_medium_voa2_edfa.yaml`, but further shaping/gain balancing needed.

    Next actions
    - EDFA convergence micro-sweep at 16ch K=8: sweep `voa_post_db` (4/6/8 dB), `sat_I_sat` (0.5/0.7/0.9), `sat_alpha`
        (1.2/1.6), and noise figure; adjust stage gains/vth schedule if needed.
    - Auto-bump trials for near-zero BER to tighten CI, then refresh CSVs.
    - Extend sweep to include end-to-end tokens/s columns broadly; update `REPORT.md` with new CI-backed results and
        switching/EDFA insights.
    "@;
    Add-Content -Path "TUNING.md" -Value $section -Encoding Unicode'

> Appended a concise session report to TUNING.md, covering:

  - What I implemented: REPORT.md, BER CIs, energy-per-symbol, re-center metrics, TDM switching realism, CSV tooling,
  and end-to-end KPIs.
  - Representative CI-backed results for 16/32ch across strong/light SA and K values, including EO/WSS penalties.
  - EDFA vs SOA status: SOA stable at 0 BER; EDFA currently high BER even with nudges and a tuned pack, needs shaping/
  gain balancing.
  - Next actions: EDFA micro-sweep for contraction, CI tightening, expanded end-to-end reporting, and report updates.
## Agent Tuning Session (2025-09-19)
- Baseline Path B probe (packs per AGENTS.md): depth=5 analog stages, return-map enabled.
- Command: examples/test.py trials=160, channels=16, window=10 ns, chop+avg2, weak-cal, VOAs+medium optics, typ InGaAs/TIA, tuned comparator, jitter=20 ps.
- Result (out/pathb_voa2_depth5.json): analog_p50_ber=0.5625; median_stage_slope=0.415; max_stage_slope=0.427; deadzone occupancy at most stages (full rows of 1.0).
- Interpretation: insufficient contraction (slope≈0.41<1) and high deadzone occupancy indicate limiter/threshold too aggressive or stage gain too low.
- Next: try enabling amp and apply tuned SOA pack to restore contraction; sweep digital guard passes and deadzone to measure recoverability; record minimal JSON summaries.
- Path B tuned runs:
  - SOA tuned (enable amp): analog_p50_ber=0.6875; median_stage_slope≈0.634; max_stage_slope≈2.48; deadzone grows across stages.
  - Strong-SA pack: analog_p50_ber=0.6875; similar slopes and deadzone profile.
- Conclusion: guard did not change analog p50 BER (expected: affects digital post-correction); contraction still weak at median, with occasional overamplification (max slope >2) not improving BER.
- Next planned probes: (a) reduce window to 8 ns to raise SNR; (b) try --path-b-vth-schedule to lighten early thresholds; (c) sweep --path-b-stage-gains-db to ensure initial contraction <1 with recovery; (d) try EDFA pack variant with tighter OBPF and tuned gains for comparison.
- Additional probes:
  - Window 8 ns (tuned SOA): analog_p50_ber=0.6875; median slope≈0.613; max≈2.74; minimal improvement.
  - EDFA pack: analog_p50_ber=0.6875; median slope≈0.871; max≈4.91; deadzone ~0.0, yet BER unchanged (likely comparator thresholds and stage gain schedule misaligned).
- Action plan:
  1) Apply explicit --path-b-stage-gains-db schedule to ensure early contraction (<1) then mild gain; 
  2) Use --path-b-vth-schedule to relax early thresholds; 
  3) Turn on --path-b-calibrate-vth --path-b-calibrate-optical --path-b-calibrate-vth-apply-guard to re-trim; 
  4) Re-check return-map slopes and analog BER.
- Scheduled + calibration run: analog_p50_ber=0.6875; median slope≈0.533 (lower, more contraction); deadzone rises late (up to 0.6875). No BER improvement yet.
- Hypothesis: analog cascade dominated by comparator decision pattern (saturated to 0/1 early), producing irreversible errors; need balanced-PD or softer vth schedule and smaller guard bias.
- Next immediate step: enable --path-b-balanced, reduce vth schedule (0.4..0.7), and soften guard gain; then, if still stuck, lower stage depth to 3 and verify per-stage err trend.
- Balanced + softer thresholds + lower guard improved Path B: analog_p50_ber→0.3125 (from 0.6875). Median slope≈0.572; deadzone still rises late.
- Next quick probe: reduce analog depth to 3 with same schedules to check if early contraction + fewer saturating stages yields lower BER.
- Depth=3 with balanced + soft vth holds at 0.3125 BER; contraction ~0.59 median. Suggests remaining errors are upstream and not accumulating further with extra stages.
- Next: small tweaks:
  - Lower guard gain to 0.01 mW; 
  - Slightly reduce vth schedule to 0.35,0.4,0.5; 
  - Try window 12 ns to help SNR.
- Window 12 ns + gentler guard yielded analog_p50_ber=0.375 (slight regression). Median slope ~0.594.
- Best to date: 0.3125 at 10 ns with balanced PD, vth 0.4-0.7, stage gains -1..+1 dB, guard 0.02 mW.
- Park current best and propose next: try light-SA pack variant that historically reduced plateau BER, or test --decoder-linear to assist decisions as an upper bound for achievable analog tuning.
- Light-SA probes (balanced PD, vth 0.4-0.7, stage gains -1..+1 dB):
  - Guard gain 0.01/0.02/0.03 mW all yielded analog_p50_ber=0.4375; median slope≈0.363; max≈0.462; deadzone saturates late.
- Takeaway: light-SA lowers contraction below baseline but induces heavy deadzone saturation; best setting remains the tuned SOA with balanced PD at 0.3125 BER.
- Next queued: decoder-assisted upper bound with --decoder-linear on the best analog setting to bound achievable BER; if meaningful gap exists, further tweak vth schedule and stage gains to close it.
- Decoder-assisted bound (balanced, depth=3): analog_p50_ber remains 0.3125; end_to_end tokens/s field not populated in this mode (null). Decoder fusion enabled (--decoder-linear --fuse-decoder) did not worsen analog BER, suggesting room to try --use-decoder-for-path-a when focusing on end-to-end.
- Next: small vth guard grid at depth=3 with balanced PD to try closing below 0.3125: vth schedules (0.35,0.4,0.45) vs guard gains (0.015, 0.02, 0.03).
- Depth=3 vth/guard grid (balanced): all three probes hold at analog_p50_ber=0.3125 with median slope ~0.563, insensitive to guard 0.015–0.03 mW. This appears to be a plateau for the current tuned SOA config.
- Proposed next directions:
  1) Revisit comparator hysteresis/sigma in the tuned comparator overlay to slightly soften early decisions; 
  2) Explore small positive stage gains in later stages (e.g., -1,-0.25,0.25) to counter late deadzone growth; 
  3) If end‑to‑end KPIs matter now, enable --use-decoder-for-path-a and --endtoend-report to capture tokens/s.
- Comparator softening + stage gains (-1,-0.25,0.25) at depth=3 held at analog_p50_ber=0.3125; median slope ~0.535. No further improvement.
- Conclusion: current tuned SOA + balanced PD + soft vth schedule plateaus around 0.3125 analog p50 BER for these seeds/params.
- Next: populate end-to-end KPIs with --use-decoder-for-path-a and --endtoend-report on the best analog setting to track tokens/s and combined BER; then decide whether to invest in deeper optics/amp tuning or accept decoder assist.
- End-to-end at current best: Path A (decoder-assisted) p50 BER = 0.0; Path B analog p50 BER = 0.3125; end_to_end tokens/s/combined not emitted in this mode.
- Next: optional EDFA micro-sweep and minor comparator overlay variants to check if analog plateau can be pushed <0.25; otherwise, freeze this recipe and proceed to aggregate CSV/report.
- EDFA micro-sweep (balanced d3):
  - Base EDFA: 0.6875 BER (median slope ~0.552; max ~5.80), poor.
  - Variants: best 0.5625 BER with voa_post ~ -4 dB (others 0.625/0.6875). EDFA remains inferior to tuned SOA for this setup.
- Conclusion: keep tuned SOA balanced recipe (0.3125) as current best; EDFA not competitive under these micro-tweaks.
- Next: freeze best recipe and produce brief CSV/report updates with settings and expected BER; optionally revisit Stage-A (Path A) head integration for end-to-end tokens/s once required.
- 1-channel Path B (strong-SA, 6 ns): analog_p50_ber=0.0 with balanced PD, soft vth schedule, modest stage gains, guard 0.02 mW. Median slope ~0.623.
- This satisfies the FEEDBACK.md request to achieve a reliable 0-BER 1-channel MVP in sim at 6–8 ns.
- Next: scale same recipe to 4 and 8 channels and confirm 0-BER holds; then gradually reduce costs (lighter TIA/comparator/optics) while maintaining acceptance targets.
- Scaling strong-SA 6 ns:
  - 1 ch: 0.0 BER (previous run).
  - 4 ch: 0.25 BER.
  - 8 ch: 0.375 BER.
- Recipe: balanced PD, vth 0.3-0.5, stage gains -0.5..+0.25 dB, guard 0.02 mW.
- Next: try 8 ch at 8–10 ns (to lift SNR) and combine with light masking and optional digital guard to approach 0 BER, then back off costs.
- 8-ch strong-SA @10 ns refinements (avg3, stronger early vth, refined stage gains, heavier calibration/mask) resulted in analog_p50_ber=0.5. No improvement over 0.375.
- Current best at 8-ch remains 0.375 (10 ns tuned comparator). Next options: try slightly higher window (12 ns) with balanced PD and conservative gains, or pivot to 6-ch as an intermediate stable point, or use TDM K<8 for 16-ch targets.
- Proceeding to write a simple-English summary in REPORT.md capturing the MVP wins, scaling posture, and recommended next validation steps.
- 8-ch strong-SA @12 ns reached analog_p50_ber=0.3125 with balanced PD and tuned thresholds/gains. This matches our best 3-stage 16-ch plateau and meets a practical intermediate target.
- Path forward: lock this recipe for 8 ch at 12 ns; attempt gentle cost-down (lighter TIA/comparator) to check robustness; optionally try avg3 and small digital guard for guardrail.

### Session Wrap‑Up (2025-09-18)
- Consolidated scaling CSV written: out/pathb_scaling_summary.csv.
- Best analogs: 1‑ch 0‑BER @6 ns; 8‑ch ~0.3125 @12 ns (premium) and ~0.375 (budget).
- Added Road‑to‑Bench checklist and Buy List to REPORT.md.
