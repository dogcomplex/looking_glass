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
