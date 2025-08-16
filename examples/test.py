"""
Usage examples (PowerShell-friendly):

  # default run
  python examples/test.py

  # more trials and fixed seed
  python examples/test.py --trials 300 --seed 123

  # sensitivity mode (amplify effects):
  python examples/test.py --sensitivity

  # custom windows and ranges
  python examples/test.py --windows 5,10,15,20,25 --rin-range "-170:-130:9" --ct-range "-40:-15:9"

  # save JSON output
  python examples/test.py --json out/test_summary.json
"""

import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import json
from statistics import median
import argparse

from looking_glass.orchestrator import Orchestrator, SystemParams
from looking_glass.sim.emitter import EmitterParams
from looking_glass.sim.optics import OpticsParams
from looking_glass.sim.sensor import PDParams
from looking_glass.sim.tia import TIAParams
from looking_glass.sim.comparator import ComparatorParams
from looking_glass.sim.clock import ClockParams


def run_trials(orch: Orchestrator, trials: int):
    return [orch.step() for _ in range(trials)]


def med_ber(rows):
    return float(median([r["ber"] for r in rows])) if rows else None


def quick_window_sweep(orch: Orchestrator, trials: int, windows):
    xs, ys = [], []
    for w in windows:
        orch.clk.p.window_ns = float(w)
        rows = run_trials(orch, trials)
        xs.append(w)
        ys.append(med_ber(rows))
    # Expect BER non-increasing with window
    monotone = all(ys[i] >= ys[i+1] for i in range(len(ys)-1))
    return xs, ys, bool(monotone)


def quick_rin_sweep(
    base_sys: SystemParams,
    trials: int,
    starts,
    stops,
    steps,
    *,
    tia_bw_mhz: float,
    comp_noise_mV: float,
    emit_ext_db: float | None = None,
    emit_power_mw: float | None = None,
    tia_R_kohm: float | None = None,
    comp_vth_mV: float | None = None,
):
    xs, ys = [], []
    for i in range(steps):
        x = starts + i*(stops-starts)/(steps-1)
        # Rebuild orchestrator per point to keep RNG state comparable
        emit = EmitterParams(channels=base_sys.channels, rin_dbhz=float(x))
        if emit_ext_db is not None:
            emit.extinction_db = float(emit_ext_db)
        if emit_power_mw is not None:
            emit.power_mw_per_ch = float(emit_power_mw)
        optx = OpticsParams()
        pd = PDParams()
        tia = TIAParams(bw_mhz=tia_bw_mhz, tia_transimpedance_kohm=(tia_R_kohm if tia_R_kohm is not None else 10.0))
        comp = ComparatorParams(input_noise_mV_rms=comp_noise_mV, vth_mV=(comp_vth_mV if comp_vth_mV is not None else 5.0))
        clk = ClockParams(window_ns=base_sys.window_ns, jitter_ps_rms=10.0)
        orch = Orchestrator(base_sys, emit, optx, pd, tia, comp, clk)
        rows = run_trials(orch, trials)
        xs.append(x)
        ys.append(med_ber(rows))
    # Expect BER non-decreasing when RIN gets worse (less negative)
    monotone = all(ys[i] <= ys[i+1] for i in range(len(ys)-1))
    return xs, ys, bool(monotone)


def quick_crosstalk_sweep(base_sys: SystemParams, trials: int, starts, stops, steps, *, tia_bw_mhz: float, comp_noise_mV: float, opt_contrast: tuple[float, float] | None = None, opt_transmittance: float | None = None):
    xs, ys = [], []
    for i in range(steps):
        x = starts + i*(stops-starts)/(steps-1)
        emit = EmitterParams(channels=base_sys.channels)
        optx = OpticsParams(crosstalk_db=float(x))
        if opt_contrast is not None:
            optx.w_plus_contrast, optx.w_minus_contrast = float(opt_contrast[0]), float(opt_contrast[1])
        if opt_transmittance is not None:
            optx.transmittance = float(opt_transmittance)
        pd = PDParams()
        tia = TIAParams(bw_mhz=tia_bw_mhz)
        comp = ComparatorParams(input_noise_mV_rms=comp_noise_mV)
        clk = ClockParams(window_ns=base_sys.window_ns, jitter_ps_rms=10.0)
        orch = Orchestrator(base_sys, emit, optx, pd, tia, comp, clk)
        rows = run_trials(orch, trials)
        xs.append(x)
        ys.append(med_ber(rows))
    # Crosstalk less negative (towards 0) => worse; expect BER non-decreasing with x
    monotone = all(ys[i] <= ys[i+1] for i in range(len(ys)-1))
    return xs, ys, bool(monotone)

def quick_neighbor_ct_sweep(
    base_sys: SystemParams,
    trials: int,
    starts,
    stops,
    steps,
    *,
    tia_bw_mhz: float,
    comp_noise_mV: float,
    opt_contrast: tuple[float, float] | None = None,
    emit_power_mw: float | None = None,
    tia_R_kohm: float | None = None,
    comp_vth_mV: float | None = None,
):
    xs, ys = [], []
    for i in range(steps):
        x = starts + i*(stops-starts)/(steps-1)
        emit = EmitterParams(channels=base_sys.channels)
        if emit_power_mw is not None:
            emit.power_mw_per_ch = float(emit_power_mw)
        optx = OpticsParams(ct_model="neighbor", ct_neighbor_db=float(x))
        if opt_contrast is not None:
            optx.w_plus_contrast, optx.w_minus_contrast = float(opt_contrast[0]), float(opt_contrast[1])
        pd = PDParams()
        tia = TIAParams(bw_mhz=tia_bw_mhz, tia_transimpedance_kohm=(tia_R_kohm if tia_R_kohm is not None else 10.0))
        comp = ComparatorParams(input_noise_mV_rms=comp_noise_mV, vth_mV=(comp_vth_mV if comp_vth_mV is not None else 5.0))
        clk = ClockParams(window_ns=base_sys.window_ns, jitter_ps_rms=10.0)
        orch = Orchestrator(base_sys, emit, optx, pd, tia, comp, clk)
        rows = run_trials(orch, trials)
        xs.append(x)
        ys.append(med_ber(rows))
    monotone = all(ys[i] <= ys[i+1] for i in range(len(ys)-1))
    return xs, ys, bool(monotone)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seed", type=int, default=321)
    ap.add_argument("--sensitivity", action="store_true")
    ap.add_argument("--windows", type=str, default="3,5,7,9,13,17")
    ap.add_argument("--rin-range", type=str, default="-170:-140:4")
    ap.add_argument("--ct-range", type=str, default="-40:-18:4")
    ap.add_argument("--json", type=str, default=None)
    args = ap.parse_args()

    # Base system from typ packs inline
    sys_p = SystemParams(channels=16, window_ns=10.0, temp_C=25.0, seed=args.seed)
    emit = EmitterParams(channels=16, power_mw_per_ch=0.7, power_sigma_pct=2.0)
    optx = OpticsParams()
    pd = PDParams()
    # Sensitivity mode tunes TIA BW and comparator noise to amplify trends
    tia_bw = 30.0 if args.sensitivity else 80.0
    comp_noise = 0.3 if args.sensitivity else 0.6
    tia = TIAParams(bw_mhz=tia_bw, tia_transimpedance_kohm=5.0, in_noise_pA_rthz=3.0, gain_sigma_pct=1.0)
    comp = ComparatorParams(input_noise_mV_rms=comp_noise, vth_sigma_mV=0.2)
    clk = ClockParams(window_ns=10.0, jitter_ps_rms=10.0)
    orch = Orchestrator(sys_p, emit, optx, pd, tia, comp, clk)

    # Parse windows and ranges
    windows = [float(w) for w in args.windows.split(",") if w.strip()]
    rin_s, rin_e, rin_n = [v.strip() for v in args.rin_range.split(":")]
    ct_s, ct_e, ct_n = [v.strip() for v in args.ct_range.split(":")]

    # Short, pragmatic sweeps
    w_xs, w_ys, w_ok = quick_window_sweep(orch, trials=args.trials, windows=windows)
    r_xs, r_ys, r_ok = quick_rin_sweep(sys_p, trials=args.trials, starts=float(rin_s), stops=float(rin_e), steps=int(rin_n), tia_bw_mhz=tia_bw, comp_noise_mV=comp_noise)
    c_xs, c_ys, c_ok = quick_crosstalk_sweep(sys_p, trials=args.trials, starts=float(ct_s), stops=float(ct_e), steps=int(ct_n), tia_bw_mhz=tia_bw, comp_noise_mV=comp_noise)

    # Baseline summary at default settings
    base_emit = EmitterParams(channels=16)
    base_optx = OpticsParams()
    base_pd = PDParams()
    base_tia = TIAParams(bw_mhz=tia_bw)
    base_comp = ComparatorParams(input_noise_mV_rms=comp_noise)
    base_clk = ClockParams(window_ns=10.0, jitter_ps_rms=10.0)
    base_orch = Orchestrator(sys_p, base_emit, base_optx, base_pd, base_tia, base_comp, base_clk)
    base_summary = base_orch.run(trials=args.trials)

    # Notable effects across sweeps
    def safe_delta(arr):
        return (arr[0] - arr[-1]) if arr and len(arr) > 1 else 0.0
    effects = {
        "window_ber_improvement": safe_delta(w_ys),
        "rin_ber_degradation": (r_ys[-1] - r_ys[0]) if r_ys and len(r_ys) > 1 else 0.0,
        "crosstalk_ber_degradation": (c_ys[-1] - c_ys[0]) if c_ys and len(c_ys) > 1 else 0.0,
    }

    # Per-tile BER heatmap (default run): if tiling is square, compute BER per tile
    per_tile = None
    try:
        blocks = base_orch.sys.channels
        blocks = int(blocks**0.5)
        if blocks*blocks == base_orch.sys.channels:
            # Run one frame to get tile mapping, then accumulate per-tile BER
            # Use a small additional run to estimate per-tile BER robustly
            rows = [base_orch.step() for _ in range(min(200, args.trials))]
            # Map channel -> tile index
            # Tiles are filled row-major in optics.simulate(); two rails per tile (plus/minus)
            # Here we approximate channel→tile as index // 1 (one channel per tile in current mapping)
            import numpy as _np
            tile_err = _np.zeros((blocks, blocks), dtype=float)
            tile_cnt = _np.zeros((blocks, blocks), dtype=float)
            for r in rows:
                t_out = r.get("t_out", [])
                truth = r.get("truth", [])
                for ch, (o, z) in enumerate(zip(t_out, truth)):
                    by = ch // blocks
                    bx = ch % blocks
                    tile_err[by, bx] += 1.0 if int(o) != int(z) else 0.0
                    tile_cnt[by, bx] += 1.0
            with _np.errstate(divide='ignore', invalid='ignore'):
                per_tile = (tile_err / _np.clip(tile_cnt, 1.0, None)).tolist()
            try:
                from looking_glass.plotting import save_heatmap as _save_hm
                _save_hm(per_tile, xlabel="tile-x", ylabel="tile-y", out_path="out/ber_per_tile.png", title="Per-tile BER")
            except Exception:
                pass
    except Exception:
        per_tile = None

    summary = {
        "config": {
            "trials": args.trials,
            "seed": args.seed,
            "sensitivity": args.sensitivity,
        },
        "baseline": base_summary,
        "ber_per_tile": per_tile,
        "sanity": {
            "window_non_increasing": w_ok,
            "rin_non_decreasing": r_ok,
            "crosstalk_non_decreasing": c_ok,
        },
        "effects": effects,
        "window_sweep": {"x_window_ns": w_xs, "p50_ber": w_ys},
        "rin_sweep": {"x_rin_dbhz": r_xs, "p50_ber": r_ys},
        "crosstalk_sweep": {"x_crosstalk_db": c_xs, "p50_ber": c_ys},
    }

    # Always include a sensitivity block with more pronounced ranges for "notable results"
    sens_tia_bw = 30.0
    sens_comp_noise = 0.3
    sens_windows = [3, 6, 10, 15, 20, 30]
    sens_rin = (-170.0, -130.0, 9)
    sens_ct = (-40.0, -15.0, 9)
    sens_emit = EmitterParams(channels=16, power_mw_per_ch=0.05)
    sens_optx = OpticsParams()
    sens_pd = PDParams()
    sens_tia = TIAParams(bw_mhz=sens_tia_bw, tia_transimpedance_kohm=1.0)
    sens_comp = ComparatorParams(input_noise_mV_rms=sens_comp_noise, vth_mV=5.0)
    sens_clk = ClockParams(window_ns=10.0, jitter_ps_rms=10.0)
    sens_orch = Orchestrator(sys_p, sens_emit, sens_optx, sens_pd, sens_tia, sens_comp, sens_clk)
    sw_xs, sw_ys, sw_ok = quick_window_sweep(sens_orch, trials=args.trials, windows=sens_windows)
    sr_xs, sr_ys, sr_ok = quick_rin_sweep(
        sys_p,
        trials=args.trials,
        starts=sens_rin[0],
        stops=sens_rin[1],
        steps=sens_rin[2],
        tia_bw_mhz=sens_tia_bw,
        comp_noise_mV=sens_comp_noise,
        emit_ext_db=6.0,
        emit_power_mw=0.05,
        tia_R_kohm=1.0,
        comp_vth_mV=5.0,
    )
    sc_xs, sc_ys, sc_ok = quick_crosstalk_sweep(
        sys_p,
        trials=args.trials,
        starts=sens_ct[0],
        stops=sens_ct[1],
        steps=sens_ct[2],
        tia_bw_mhz=sens_tia_bw,
        comp_noise_mV=sens_comp_noise,
        opt_contrast=(0.8, 0.78),
        opt_transmittance=0.6,
    )
    nct_range = (-40.0, -20.0, 5)
    sn_xs, sn_ys, sn_ok = quick_neighbor_ct_sweep(
        sys_p,
        trials=args.trials,
        starts=nct_range[0],
        stops=nct_range[1],
        steps=nct_range[2],
        tia_bw_mhz=sens_tia_bw,
        comp_noise_mV=sens_comp_noise,
        opt_contrast=(0.8, 0.78),
        emit_power_mw=0.05,
        tia_R_kohm=1.0,
        comp_vth_mV=5.0,
    )
    sens_effects = {
        "window_ber_improvement": safe_delta(sw_ys),
        "rin_ber_degradation": (sr_ys[-1] - sr_ys[0]) if sr_ys and len(sr_ys) > 1 else 0.0,
        "crosstalk_ber_degradation": (sc_ys[-1] - sc_ys[0]) if sc_ys and len(sc_ys) > 1 else 0.0,
        "neighbor_crosstalk_ber_degradation": (sn_ys[-1] - sn_ys[0]) if sn_ys and len(sn_ys) > 1 else 0.0,
    }
    summary["sensitivity"] = {
        "config": {
            "tia_bw_mhz": sens_tia_bw,
            "comp_input_noise_mV_rms": sens_comp_noise,
            "windows": sens_windows,
            "rin_range": sens_rin,
            "ct_range": sens_ct,
            "neighbor_ct_range": nct_range,
        },
        "sanity": {
            "window_non_increasing": sw_ok,
            "rin_non_decreasing": sr_ok,
            "crosstalk_non_decreasing": sc_ok,
            "neighbor_crosstalk_non_decreasing": sn_ok,
        },
        "effects": sens_effects,
        "window_sweep": {"x_window_ns": sw_xs, "p50_ber": sw_ys},
        "rin_sweep": {"x_rin_dbhz": sr_xs, "p50_ber": sr_ys},
        "crosstalk_sweep": {"x_crosstalk_db": sc_xs, "p50_ber": sc_ys},
        "neighbor_crosstalk_sweep": {"x_ct_neighbor_db": sn_xs, "p50_ber": sn_ys},
    }

    # Optional: Per-tile heatmap in sensitivity mode if tiling is square (blocks^2 == channels)
    try:
        from looking_glass.plotting import save_heatmap
        # Run one sensitivity frame to capture per-tile average maps
        _one = sens_orch.step()
        if _one.get("per_tile", {}).get("plus") is not None:
            save_heatmap(_one["per_tile"]["plus"], xlabel="tile-x", ylabel="tile-y", out_path="out/per_tile_plus.png", title="Per-tile Plus Intensity")
            save_heatmap(_one["per_tile"]["minus"], xlabel="tile-x", ylabel="tile-y", out_path="out/per_tile_minus.png", title="Per-tile Minus Intensity")
    except (ImportError, RuntimeError, ValueError):
        pass
    print(json.dumps(summary, indent=2))
    if args.json:
        os.makedirs(os.path.dirname(args.json), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
    # Exit non-zero if any sanity monotonic checks fail
    if not (w_ok and r_ok and c_ok):
        sys.exit(1)


if __name__ == "__main__":
    main()

