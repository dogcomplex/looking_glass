# LookingGlassSim

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

Tip (Windows CMD) create/activate a venv:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
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

## Launch the web dashboard

The dashboard lets you kick off runs, watch logs in real time, and view the final JSON summary in a single page.

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

4) Click “Run”. The server executes `examples/test.py` with sensible defaults and streams logs via Server‑Sent Events. When the run completes, the page renders all metrics, and the full JSON is also written to `out/test_summary.json`.

Dashboard tips:

- The “Retest” controls let you tweak inputs like trials, seed, and window; the server maps them to CLI flags.
- Images like `out/ber_per_tile.png` and `out/per_tile_plus.png` are produced when tiling is square.
- If the page shows “busy”, it means a run is in progress; wait for the “done” event or refresh after it finishes.

---

## Configuration packs and scenarios

- Packs live under `configs/packs/*.yaml`, including vendor‑annotated bundles in `configs/packs/vendors/` for emitters, cameras, TIAs, comparators, amplifiers, modulators, fiber, and thermal hardware.
- Scenarios (e.g., `configs/scenarios/basic_typ.yaml`) choose packs and set the end‑to‑end run parameters.
- You can create `*_vendorX.yaml` packs from datasheets/bench measurements and point scenarios to them to close sim↔bench.

---

## Interpreting the KPIs

- BER: p50 of per‑trial bit error rates across channels; lower is better. Ternary decisions include 0 state if comparator hysteresis lands in the deadband.
- Energy (pJ): derived from emitted optical power over the exposure window; useful as a relative proxy across configs.
- SNRs: approximate mid‑stage SNR per block (emitter/PD/TIA) to diagnose where losses accrue.
- Drift: BER vs time with and without periodic re‑centering (per‑channel threshold trims), parameterized by `thermal_typ.yaml`.

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
