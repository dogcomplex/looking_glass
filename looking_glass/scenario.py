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
from .sim.camera import CameraParams
from .sim.thermal import ThermalParams


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

    def _pack_data(key: str, *, required: bool) -> dict | None:
        if required and key not in scn:
            raise KeyError(f"Scenario missing required entry '{key}'")
        if key not in scn:
            return None
        raw = scn.get(key)
        if raw is None:
            return None
        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                return None
            return _load_yaml(raw)
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, Path):
            return _load_yaml(raw)
        return _load_yaml(str(raw))

    emit_p = _instantiate(EmitterParams, _pack_data("emitter_pack", required=True))
    optx_p = _instantiate(OpticsParams, _pack_data("optics_pack", required=True))
    pd_p = _instantiate(PDParams, _pack_data("sensor_pack", required=True))
    tia_p = _instantiate(TIAParams, _pack_data("tia_pack", required=True))
    comp_p = _instantiate(ComparatorParams, _pack_data("comparator_pack", required=True))
    clk_p = _instantiate(ClockParams, _pack_data("clock_pack", required=True))

    therm_data = _pack_data("thermal_pack", required=False)
    therm_p = _instantiate(ThermalParams, therm_data) if therm_data is not None else None
    cam_data = _pack_data("camera_pack", required=False)
    cam_p = _instantiate(CameraParams, cam_data) if cam_data is not None else None

    # Enforce channel count from scenario on relevant packs
    emit_p.channels = channels

    sys_p = SystemParams(channels=channels, window_ns=clk_p.window_ns, temp_C=temp_C, seed=seed)
    orch = Orchestrator(sys_p, emit_p, optx_p, pd_p, tia_p, comp_p, clk_p, cam_p, therm_p)
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
    parser.add_argument("--sweep-window-ns", type=str, default=None,
                        help="Optional sweep over window_ns, format start:stop:steps (inclusive start/stop)")
    parser.add_argument("--sweep-rin-db-hz", type=str, default=None,
                        help="Optional sweep over emitter rin_dbhz, format start:stop:steps")
    parser.add_argument("--sweep-crosstalk-db", type=str, default=None,
                        help="Optional sweep over optics crosstalk_db, format start:stop:steps")
    parser.add_argument("--sweep-sat-I-sat", type=str, default=None,
                        help="Optional sweep over optics sat_I_sat, format start:stop:steps (enable sat_abs_on)")
    parser.add_argument("--sweep-ct-neighbor-db", type=str, default=None,
                        help="Optional sweep over neighbor crosstalk (ct_model=neighbor), format start:stop:steps")
    parser.add_argument("--sweep-ct-diag-db", type=str, default=None,
                        help="Optional sweep over diagonal crosstalk (ct_model=neighbor), format start:stop:steps")
    parser.add_argument("--meta", type=str, default=None, help="Optional path to save run metadata JSON")
    parser.add_argument("--plot", type=str, default=None, help="Optional path to save BER vs window_ns PNG plot")
    args = parser.parse_args(argv)

    orch, trials_default, _ = build_orchestrator_from_scenario(args.scenario)
    trials = args.trials if args.trials is not None else trials_default

    # Optionally save run metadata
    if args.meta:
        meta = {
            "scenario": str(args.scenario),
            "trials": int(trials),
            "system": {
                "channels": int(orch.sys.channels),
                "temp_C": float(orch.sys.temp_C),
                "seed": int(orch.sys.seed),
                "window_ns": float(orch.clk.p.window_ns),
            },
            "packs": {
                "emitter": orch.emit.p.__dict__,
                "optics": orch.optx.p.__dict__,
                "sensor": orch.pd.p.__dict__,
                "tia": orch.tia.p.__dict__,
                "comparator": orch.comp.p.__dict__,
                "clock": orch.clk.p.__dict__,
            },
        }
        Path(args.meta).parent.mkdir(parents=True, exist_ok=True)
        with open(args.meta, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    # Sweep branch (only one at a time)
    sweep_kv = None
    xlabel = None
    if args.sweep_window_ns:
        start_s, stop_s, steps_s = args.sweep_window_ns.split(":")
        setter = lambda v: setattr(orch.clk.p, "window_ns", float(v))
        xlabel = "window_ns"
        sweep_kv = (float(start_s), float(stop_s), int(steps_s), setter)
    elif args.sweep_rin_db_hz:
        start_s, stop_s, steps_s = args.sweep_rin_db_hz.split(":")
        setter = lambda v: setattr(orch.emit.p, "rin_dbhz", float(v))
        xlabel = "rin_dbhz"
        sweep_kv = (float(start_s), float(stop_s), int(steps_s), setter)
    elif args.sweep_crosstalk_db:
        start_s, stop_s, steps_s = args.sweep_crosstalk_db.split(":")
        setter = lambda v: setattr(orch.optx.p, "crosstalk_db", float(v))
        xlabel = "crosstalk_db"
        sweep_kv = (float(start_s), float(stop_s), int(steps_s), setter)
    elif args.sweep_sat_I_sat:
        start_s, stop_s, steps_s = args.sweep_sat_I_sat.split(":")
        orch.optx.p.sat_abs_on = True
        setter = lambda v: setattr(orch.optx.p, "sat_I_sat", float(v))
        xlabel = "sat_I_sat"
        sweep_kv = (float(start_s), float(stop_s), int(steps_s), setter)
    elif args.sweep_ct_neighbor_db:
        start_s, stop_s, steps_s = args.sweep_ct_neighbor_db.split(":")
        orch.optx.p.ct_model = "neighbor"
        setter = lambda v: setattr(orch.optx.p, "ct_neighbor_db", float(v))
        xlabel = "ct_neighbor_db"
        sweep_kv = (float(start_s), float(stop_s), int(steps_s), setter)
    elif args.sweep_ct_diag_db:
        start_s, stop_s, steps_s = args.sweep_ct_diag_db.split(":")
        orch.optx.p.ct_model = "neighbor"
        setter = lambda v: setattr(orch.optx.p, "ct_diag_db", float(v))
        xlabel = "ct_diag_db"
        sweep_kv = (float(start_s), float(stop_s), int(steps_s), setter)

    if sweep_kv is not None:
        start, stop, steps, setter = sweep_kv
        if steps < 2:
            steps = 2
        xs = [start + i*(stop-start)/(steps-1) for i in range(steps)]
        ys = []
        from .plotting import save_xy_plot
        all_rows = []
        for x in xs:
            setter(x)
            rows = run_trials(orch, trials)
            all_rows.extend([{**r, xlabel: x} for r in rows])
            summ = summarize(rows)
            ys.append(summ["p50_ber"]) 
        # Save CSV if requested
        if args.csv:
            path = Path(args.csv)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=[xlabel, "ber", "energy_pj", "window_ns"])
                w.writeheader()
                for r in all_rows:
                    w.writerow({
                        xlabel: r.get(xlabel),
                        "ber": r.get("ber"),
                        "energy_pj": r.get("energy_pj"),
                        "window_ns": r.get("window_ns"),
                    })
        # Save plot
        if args.plot:
            save_xy_plot(xs, ys, xlabel=xlabel, ylabel="p50_ber", out_path=args.plot,
                         title=f"BER vs {xlabel}")
        # Save summary list if requested
        if args.json:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump({f"x_{xlabel}": xs, "p50_ber": ys}, f, indent=2)
        print(json.dumps({f"x_{xlabel}": xs, "p50_ber": ys}, indent=2))
        return 0
    else:
        rows = run_trials(orch, trials)
        summary = summarize(rows)
        if args.csv:
            save_csv(rows, args.csv)
        if args.json:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
        if args.plot:
            # No sweep, plot is not meaningful; ignore silently
            pass
        print(json.dumps(summary, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(run_scenario_cli())

