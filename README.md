# LookingGlassSim

## Start the probe queue (Windows CMD)

Use these commands in a fresh Administrator CMD session (not PowerShell):

```bat
cd G:\LOKI\LOCUS\SENSUS\looking_glass

:: (first-time only) create and activate venv, then install deps
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

:: ensure queue directories exist
mkdir queue 2> NUL
mkdir out 2> NUL

:: optional: reduce skip spam in logs
set QUIET_SKIPS=1

:: start the queue runner (blocking)
.venv\Scripts\python scripts\probe_queue_runner.py
```

Notes:
- Append jobs to `queue\probes.jsonl` (append-only). The runner picks up new lines automatically.
- Results are written to `out\*.json` and minimal summaries to `queue\completed.jsonl`.
- To rerun everything from scratch, stop the runner, delete `queue\completed.jsonl`, then start the runner again.
- If using PowerShell instead of CMD, activate with `.venv\Scripts\Activate.ps1`.

Hybrid analog–digital optical AI co‑processor simulator for ternary Transformer feature extraction. This repo is a pragmatic, staged scaffold you can run today on a laptop, then swap in measured hardware packs as you build up a real bench.

## What this project does (verbose overview)

Looking Glass explores a realistic path to optical acceleration by offloading the linear parts of attention (feature extraction, roughly sign(Wx)) into optics while keeping non‑linear control digital. We target robust ternary weights {-1, 0, +1} and build two loops that share one software stack:

- Path A — Camera/DMD loop: commodity DLP/SLM encodes vectors; a glass “reservoir” mixes the field; a camera reads intensity; a TIA+comparator makes ternary decisions. This maximizes practicality and iteration speed.
- Path B — Analog ternary loop: all‑optical threshold (saturable absorber) + gain (SOA/EDFA) between diffractive stages to propagate a ternary state without O‑E‑O until a final camera readout. This maximizes speed/energy.

The simulator models key blocks: emitter array (laser/DLP), optics PSF and crosstalk, camera/PD, TIA dynamics and noise, comparator thresholds/hysteresis, clocking/jitter, and slow thermal drift. It reports KPIs that matter for feasibility:

- BER (bit error rate) of ternary decisions
- Energy per token (pJ/token proxy)
- Throughput proxy via exposure window
- SNR margins per stage (emitter/PD/TIA)
- Stability vs drift and crosstalk

It also includes mitigation levers you can toggle in software to estimate improvements you can achieve in hardware: lock‑in subtraction, chopper stabilization (+x/−x frames), frame averaging, per‑channel calibration (vth trims), and temporal/spatial voting.

High‑level dataflow (both paths):

```
Input → Emitter → Optics → (Camera → TIA → Comparator) → ternary output
                          └─(SA + Optical Amp)─► (Path B only)─► … → Final Camera
```

See `DESIGN.md` for system goals, staged builds, KPIs, risks, and roadmap.

---

## Requirements

- Python 3.10+ (uses PEP 604 types like `X | None`)
- Windows 10/11 CMD (preferred), macOS or Linux also work

Environment:

```
python -m venv .venv
.venv\Scripts\activate
```

Base deps are minimal:

```
pip install -r requirements.txt
```

Optional extras:

```
# Dashboard server
pip install flask

# Plotting utilities in scenario runner
pip install matplotlib
```


---

## Run the simulator from the console

1) Smoke test
```
python examples/run_smoke.py
```
Prints a compact summary for one configuration.

2) Scenario runner (YAML packs)
```
python -m looking_glass.scenario configs/scenarios/basic_typ.yaml \
  --csv out/basic_typ_trials.csv --json out/basic_typ_summary.json
```
Loads packs from `configs/packs/*.yaml`, runs trials, and saves a per‑trial CSV and a summary JSON. With `matplotlib` installed you can also make plots:

```
python -m looking_glass.scenario configs/scenarios/basic_typ.yaml \
  --trials 200 --sweep-window-ns 5:25:6 \
  --plot out/ber_vs_window.png --csv out/sweep_trials.csv --json out/sweep_summary.json
```

Additional sweeps (one at a time):
```
# RIN vs BER
python -m looking_glass.scenario configs/scenarios/basic_typ.yaml --trials 200 --sweep-rin-db-hz -165:-130:8 --csv out/sweep_rin.csv --json out/sweep_rin.json

# Crosstalk vs BER
python -m looking_glass.scenario configs/scenarios/basic_typ.yaml --trials 200 --sweep-crosstalk-db -35:-18:10 --csv out/sweep_ct.csv --json out/sweep_ct.json

# Saturable absorber I_sat vs BER (enables SA automatically)
python -m looking_glass.scenario configs/scenarios/basic_typ.yaml --trials 200 --sweep-sat-I-sat 0.5:3.0:6 --csv out/sweep_sa.csv --json out/sweep_sa.json
```

3) Feature test runner with mitigations and autotune
```
python examples/test.py --trials 200 --seed 123 \
  --autotune --avg-frames 3 --chop --soft-thresh --mitigated \
  --json out/test_summary.json
```
Emits a JSON summary with:

- baseline KPIs (BER, energy, SNRs)
- per‑tile BER heatmaps (square tilings)
- sweeps and sanity checks (monotonicity)
- mitigation estimates: `lockin_p50_ber`, `chop_p50_ber`, `avg_frames_p50_ber`, `soft_thresh_p50_ber`, `mitigated_p50_ber`
- an `autotune` block with best parameters found within realistic bounds

4) Sanity checks
```
python examples/run_sanity.py
```
Asserts expected trends (e.g., BER improves with longer exposure window), returns non‑zero on failure.

---

## Launch the web dashboard (with presets & matrix)

The dashboard lets you kick off runs, watch logs in real time, and view the final JSON summary in a single page. You can also load JSON presets that define multi-select matrices across trials, seed, window, input source, path (Path A or Path B analog), autotune, calibration, averaging, and vendor packs.

1) Install the one dependency if you haven’t:
```
pip install flask
```

2) Start the server (Windows CMD shown):
```
python -m looking_glass.dashboard_server
```
The server listens on `127.0.0.1:8000` by default. You can change the port:
```
set PORT=8080 && python -m looking_glass.dashboard_server
```

3) Open your browser to:
```
http://127.0.0.1:8000/
```

4) Either click “Run” for defaults, or use the “Run Config (multi‑select everything)” section to:
   - Choose Trials/Seed/Base Window/Input Source/Path/Path B Depth
   - Toggle Vote3, Autotune, Sensitivity (stress mode), Neighbor CT model, Adaptive Input, Avg Frames, Lock‑in, Chop, Soft Threshold
   - Select vendor packs for emitter/optics/sensor/TIA/comparator/clock/camera/thermal
   - Or, click the file picker to upload a preset JSON from `configs/presets/*.json` (e.g., `sub_0p05_probe_path_a.json`)

The server executes `examples/test.py` accordingly and streams logs via Server‑Sent Events. When the run completes, the page renders all metrics, and the full JSON is also written to `out/test_summary_*.json`.

Preset format example (abbreviated):
```
{
  "runs": [{
    "trials": [300],
    "seed": [123],
    "windows": [26, 28, 30],
    "inputs": ["digital"],
    "outputs": ["path_a"],
    "vote3": ["1"],
    "autotune": ["1"],
    "apply_calibration": ["1"],
    "avg_frames": ["1", "2"],
    "packs": { "emitter_packs": ["configs/packs/vendors/emitters/coherent_OBIS-850-nm_typ.yaml"], ... }
  }]
}
```
Upload this JSON on the dashboard to reproduce a run matrix.

Dashboard tips:

- The “Retest” controls let you tweak inputs like trials, seed, and window; the server maps them to CLI flags.
- Images like `out/ber_per_tile.png` and `out/per_tile_plus.png` are produced when tiling is square.
- If the page shows “busy”, it means a run is in progress; wait for the “done” event or refresh after it finishes.

---

## Configuration packs and scenarios

- Packs live under `configs/packs/*.yaml`, including vendor‑annotated bundles in `configs/packs/vendors/` for emitters, cameras, TIAs, comparators, amplifiers, modulators, fiber, and thermal hardware.
- Scenarios (e.g., `configs/scenarios/basic_typ.yaml`) choose packs and set the end‑to‑end run parameters.
- You can create `*_vendorX.yaml` packs from datasheets/bench measurements and point scenarios to them to close sim↔bench.

### Vendor packs and matrix testing (and calibration tips)

- The dashboard exposes multi‑selects to pick vendor packs per component. Leave empty to use defaults, or select multiple to build a Cartesian matrix.
- The server prunes incompatible combinations using a preflight validator (wavelength bands, PD/TIA BW vs window, comparator toggle rate). Pruned counts are returned by `/api/run_matrix`.
- Each streamed result is labeled with the selected pack paths under `__label.packs`, and includes a `__preflight` block with `status` and reasons.
- If you intend to apply per‑channel calibration (comparator `vth` trims), ensure calibration is not disabled. In presets, set `"apply_calibration": ["1"]` and `"no_cal": ["0"]`.
- Comparator threshold calibration now persists across frames (we preserve per‑channel thresholds during `reset()`), so apply once, then evaluate multi‑trial BER without losing trims.
- Single runs accept pack overrides via query args (e.g., `emitter_pack=configs/packs/vendors/emitters/thorlabs_L850P200.yaml`).

---

## Interpreting the KPIs

- BER: p50 of per‑trial bit error rates across channels; lower is better. Ternary decisions include 0 state if comparator hysteresis lands in the deadband.
- Energy (pJ): derived from emitted optical power over the exposure window; useful as a relative proxy across configs.
- SNRs: approximate mid‑stage SNR per block (emitter/PD/TIA) to diagnose where losses accrue.
- Drift: BER vs time with and without periodic re‑centering (per‑channel threshold trims), parameterized by `thermal_typ.yaml`.
- Normalization: you can enable per‑frame differential‑voltage normalization to suppress multiplicative noise (`normalize_dv`) via preset or CLI.

---

## Troubleshooting

- “ModuleNotFoundError” from examples: ensure repo root is on `sys.path` (examples already do this) and you are launching from the repo directory.
- Dashboard won’t start: install `flask`; ensure nothing else is bound to your chosen port; corporate proxies can interfere with SSE.
- Type errors on unions (`np.ndarray | None`): ensure Python 3.10+.
- Plots aren’t created: install `matplotlib`.

---

## Roadmap snapshot

- Stage A (<$1k PoC): close the Path A loop, BER ≤ 5–10% on 16–64 ch; show MoE tiling and KV delay.
- Stage B ($3–7k prosumer): 256–1024 ch, BER ≤ 1–2%, 100–500 tokens/s‑class.
- Stage C (add Path B): demonstrate per‑stage propagation with SA+SOA and final camera readout; WDM demo.

See `DESIGN.md` for details.


---

## TDM Path B (MVP recipe)

We found a pragmatic way to scale Path B with realistic parts by time-division multiplexing (TDM): activate only K channels per frame through the analog cascade and rotate subsets.

- 16 ch strong-SA optics: K=8 yields ~10 Msym/s at ~0 BER; K=4 ~5 Msym/s at 0 BER.
- 16 ch light-SA optics: K=4 ~5 Msym/s at 0 BER; K=8 ~10 Msym/s at ~0.125 BER (median over seeds).
- 32 ch strong-SA: K=8 → 5 Msym/s at 0 BER; K=16 → 10 Msym/s at ~0.0625 BER.

Try it quickly:

```
python examples/test.py --trials 240 --channels 16 --base-window-ns 10 \
  --classifier chop --avg-frames 2 --apply-calibration --no-adaptive-input --no-cold-input --no-sweeps \
  --emitter-pack configs/packs/tmp_lowcost_emitter_boost.yaml \
  --optics-pack  configs/packs/tmp_codex_optics_medium_voa2_soa_strongsa.yaml \
  --sensor-pack  configs/packs/overlays/receiver_ingaas_typ.yaml \
  --tia-pack     configs/packs/overlays/tia_stage_b2_low_noise.yaml \
  --comparator-pack configs/packs/overlays/tuned_comparator.yaml \
  --clock-pack   configs/packs/overlays/clock_jitter_20ps.yaml \
  --normalize-dv --path-b-depth 5 --path-b-analog-depth 5 --path-b-balanced \
  --path-b-calibrate-vth --path-b-calibrate-vth-scale 0.5 --path-b-calibrate-vth-passes 64 \
  --path-b-stage-gains-db "2.0,1.0,0,-0.25,-0.25" --path-b-vth-schedule "12,12,8,6,5" \
  --path-b-sparse-active-k 8 --path-b-eval-active-only --json out/tdm16_k8.json --quiet
```

Or run the suite:

```
python scripts/run_tdm_mvp.py suite
```

See TUNING.md for context, metrics (including TDM throughput), and stability sweeps.
