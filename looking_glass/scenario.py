from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import json
import csv
import typing as t

from .orchestrator import Orchestrator, SystemParams
from .sim.emitter import EmitterParams
from .sim.optics import OpticsParams
from .sim.sensor import PDParams
from .sim.tia import TIAParams
from .sim.comparator import ComparatorParams
from .sim.clock import ClockParams


def _load_yaml(path: t.Union[str, Path]) -> dict:
    """Load a minimal YAML/JSON mapping from a file.

    Tries to use PyYAML if available; otherwise falls back to a very simple
    line-based parser that supports flat key: value pairs (sufficient for our packs).
    """
    text = Path(path).read_text(encoding="utf-8")
    try:
        import importlib
        yaml_mod = importlib.import_module("yaml")
        data = yaml_mod.safe_load(text)
        return data or {}
    except ModuleNotFoundError:
        result: dict[str, t.Any] = {}
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip("\"'")
            if val.lower() in {"true", "false"}:
                parsed: t.Any = val.lower() == "true"
            else:
                try:
                    if "." in val or "e" in val.lower():
                        parsed = float(val)
                    else:
                        parsed = int(val)
                except ValueError:
                    parsed = val
            result[key] = parsed
        return result


def _instantiate(cls: t.Type[t.Any], data: dict):
    """Instantiate a dataclass from a dict, filtering unknown keys."""
    allowed = {f.name for f in fields(cls)}
    filtered = {k: v for k, v in (data or {}).items() if k in allowed}
    return cls(**filtered)


def build_orchestrator_from_scenario(scenario_yaml_path: t.Union[str, Path]) -> tuple[Orchestrator, int, dict]:
    scn = _load_yaml(scenario_yaml_path)

    trials = int(scn.get("trials", 100))
    channels = int(scn.get("channels", 16))
    seed = int(scn.get("seed", 42))
    temp_C = float(scn.get("temp_C", 25.0))

    emit_p = _instantiate(EmitterParams, _load_yaml(scn["emitter_pack"]))
    optx_p = _instantiate(OpticsParams, _load_yaml(scn["optics_pack"]))
    pd_p = _instantiate(PDParams, _load_yaml(scn["sensor_pack"]))
    tia_p = _instantiate(TIAParams, _load_yaml(scn["tia_pack"]))
    comp_p = _instantiate(ComparatorParams, _load_yaml(scn["comparator_pack"]))
    clk_p = _instantiate(ClockParams, _load_yaml(scn["clock_pack"]))

    # Enforce channel count from scenario on relevant packs
    emit_p.channels = channels

    sys_p = SystemParams(channels=channels, window_ns=clk_p.window_ns, temp_C=temp_C, seed=seed)
    orch = Orchestrator(sys_p, emit_p, optx_p, pd_p, tia_p, comp_p, clk_p)
    return orch, trials, scn


def run_trials(orch: Orchestrator, trials: int) -> list[dict]:
    return [orch.step() for _ in range(int(trials))]


def summarize(trial_rows: list[dict]) -> dict:
    if not trial_rows:
        return {"p50_ber": None, "p50_energy_pj": None, "window_ns": None}
    from numpy import median
    ber = median([r["ber"] for r in trial_rows])
    en = median([r["energy_pj"] for r in trial_rows])
    dt = median([r["window_ns"] for r in trial_rows])
    return {"p50_ber": float(ber), "p50_energy_pj": float(en), "window_ns": float(dt)}


def save_csv(trial_rows: list[dict], path: t.Union[str, Path]) -> None:
    if not trial_rows:
        return
    keys = ["ber", "energy_pj", "window_ns"]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["trial"] + keys)
        w.writeheader()
        for i, row in enumerate(trial_rows):
            w.writerow({"trial": i, **{k: row.get(k) for k in keys}})


def run_scenario_cli(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Run LookingGlass scenario YAML")
    parser.add_argument("scenario", type=str, help="Path to scenario YAML")
    parser.add_argument("--trials", type=int, default=None, help="Override trials count")
    parser.add_argument("--csv", type=str, default=None, help="Optional CSV output path for per-trial rows")
    parser.add_argument("--json", type=str, default=None, help="Optional JSON output path for summary")
    args = parser.parse_args(argv)

    orch, trials_default, _ = build_orchestrator_from_scenario(args.scenario)
    trials = args.trials if args.trials is not None else trials_default
    rows = run_trials(orch, trials)
    summary = summarize(rows)

    if args.csv:
        save_csv(rows, args.csv)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_scenario_cli())

