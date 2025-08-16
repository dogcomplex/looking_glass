# LookingGlassSim (scaffold)

A small, runnable scaffold for the "Looking Glass" ternary analog optical loop simulator.

## Quick start
1) Smoke test
```
python examples/run_smoke.py
```
Prints a small summary dict for a single configuration.

2) Scenario runner (YAML packs)
```
python -m looking_glass.scenario configs/scenarios/basic_typ.yaml --csv out/basic_typ_trials.csv --json out/basic_typ_summary.json
```
Loads parameter packs from `configs/packs/*.yaml`, runs trials, and saves per-trial CSV and a summary JSON. PyYAML is optional; if not installed, the runner falls back to a minimal parser that supports the provided packs.

Install optional deps:
```
pip install pyyaml
```

3) Sweep and plot (requires matplotlib):
```
pip install matplotlib
python -m looking_glass.scenario configs/scenarios/basic_typ.yaml --trials 200 --sweep-window-ns 5:25:6 --plot out/ber_vs_window.png --csv out/sweep_trials.csv --json out/sweep_summary.json
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

4) Sanity checks (quick physics sanity):
```
python examples/run_sanity.py
```
Runs a few checks (emitter noise scaling, sensor mean, end-to-end BER vs window); returns non-zero on failure.

Notes on model realism:
- TIA now includes a first-order bandwidth limit and a slew-rate limit (`slew_v_per_us`).
- Comparator includes hysteresis and propagation delay (delay reduces effective integration window in orchestrator).
- Scenario sweep shows expected monotonic improvement in BER as `window_ns` increases.

Optimistic/Pessimistic scenarios:
```
python -m looking_glass.scenario configs/scenarios/basic_optimistic.yaml --trials 200 --json out/optimistic.json
python -m looking_glass.scenario configs/scenarios/basic_pessimistic.yaml --trials 200 --json out/pessimistic.json
```
