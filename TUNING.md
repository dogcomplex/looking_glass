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