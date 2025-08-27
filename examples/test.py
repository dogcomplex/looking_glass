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
from dataclasses import replace
from statistics import median
import argparse

from looking_glass.orchestrator import Orchestrator, SystemParams
from looking_glass.sim.emitter import EmitterParams
from looking_glass.sim.cold_storage import ColdParams, ColdReader
from looking_glass.sim.optics import OpticsParams
from looking_glass.sim.sensor import PDParams
from looking_glass.sim.tia import TIAParams
from looking_glass.sim.comparator import ComparatorParams
from looking_glass.sim.clock import ClockParams


def run_trials(orch: Orchestrator, trials: int):
    # Minimal per-trial retention to avoid large in-memory logs
    out = []
    for _ in range(trials):
        r = orch.step()
        out.append({
            "ber": r.get("ber"),
            "energy_pj": r.get("energy_pj"),
            "window_ns": r.get("window_ns"),
        })
    return out


def med_ber(rows):
    return float(median([r["ber"] for r in rows])) if rows else None

def mean_ber(rows):
    return (float(sum(r["ber"] for r in rows)/len(rows)) if rows else None)


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

def quick_diag_ct_sweep(
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
        optx = OpticsParams(ct_model="neighbor", ct_diag_db=float(x))
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


def _build_fixed_inputs(seed: int, channels: int, count: int):
    import numpy as _np
    rng = _np.random.default_rng(int(seed))
    return [rng.integers(-1, 2, size=channels) for _ in range(count)]


def _med_ber_fixed_inputs(orch: Orchestrator, inputs: list[list[int]]):
    import numpy as _np
    errs = []
    for tern in inputs:
        r = orch.step(force_ternary=_np.asarray(tern, dtype=int))
        errs.append(float(r.get("ber", 0.0)))
    return float(median(errs)) if errs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=200)
    ap.add_argument("--seed", type=int, default=321)
    ap.add_argument("--channels", type=int, default=16, help="Number of logical channels (e.g., 16/32/64)")
    ap.add_argument("--sensitivity", action="store_true")
    ap.add_argument("--windows", type=str, default="3,5,7,9,13,17")
    ap.add_argument("--rin-range", type=str, default="-170:-140:4")
    ap.add_argument("--ct-range", type=str, default="-40:-18:4")
    ap.add_argument("--vote3", action="store_true", help="Enable 3x temporal voting estimate")
    ap.add_argument("--repeat", type=int, default=1, help="Temporal repeats for majority vote estimate (overrides --vote3)")
    ap.add_argument("--classifier",
                    type=str,
                    choices=["auto","adaptive","avg","soft","vote3","vote5","repeat","replicate","replicate2","phys2x","lockin","chop","mitigated"],
                    default=None,
                    help="Classifier used for primary Path A summary when set")
    ap.add_argument("--autotune", action="store_true", help="Run automatic tuner within realistic bounds")
    ap.add_argument("--autotune-budget", type=int, default=60)
    ap.add_argument("--autotune-trials", type=int, default=120)
    ap.add_argument("--neighbor-ct", action="store_true", help="Use neighbor crosstalk model in baseline")
    ap.add_argument("--base-window-ns", type=float, default=20.0, help="Baseline clock window (ns)")
    ap.add_argument("--apply-calibration", action="store_true", help="Apply per-channel vth trims to baseline KPIs")
    ap.add_argument("--mask-bad-channels", type=int, default=0, help="Mask N worst channels (exclude from BER)")
    ap.add_argument("--mask-bad-frac", type=float, default=0.0, help="Mask worst frac of channels (0.0..1.0)")
    ap.add_argument("--calib-mask-trials", type=int, default=200, help="Trials used to estimate bad-channel mask")
    ap.add_argument("--spatial-oversample", type=int, default=1, help="Pseudo spatial oversampling vote (runs per input)")
    ap.add_argument("--lockin", action="store_true", help="Estimate lock-in subtraction by subtracting a dark frame dv")
    ap.add_argument("--chop", action="store_true", help="Chopper stabilization: use +x and -x frames, subtract dv before threshold")
    ap.add_argument("--avg-frames", type=int, default=1, help="Average dv over N frames per input before thresholding (noise ~ 1/sqrt(N))")
    ap.add_argument("--avg-kernel", type=str, choices=["sum", "ewma"], default="sum", help="Averaging kernel for dv over frames: sum or ewma")
    ap.add_argument("--avg-ema-alpha", type=float, default=0.6, help="EWMA alpha (0..1], only used when --avg-kernel=ewma")
    ap.add_argument("--use-avg-frames-for-path-a", action="store_true", help="If set and avg_frames>1, use averaged-dv classifier as primary path_a summary")
    ap.add_argument("--permute-repeats", action="store_true", help="Permute logical↔physical channel mapping on each repeat and de-permute for voting")
    ap.add_argument("--permute-scheme", type=str, choices=["random","cyclic"], default="random", help="Permutation scheme across repeats")
    ap.add_argument("--soft-thresh", action="store_true", help="Bypass comparator: software threshold dv using per-channel vth (upper bound for Path A)")
    # Option to choose which computed classifier feeds the primary path_a summary
    ap.add_argument("--path-a-mode", type=str, default="auto",
                    choices=["auto", "adaptive", "avg", "soft", "vote3", "lockin", "chop", "mitigated"],
                    help="Select classifier used for path_a summary: auto (default policy), adaptive, averaged dv, software threshold, temporal vote3, lockin, chop, or mitigated pipeline")
    ap.add_argument("--apply-autotuned-params", action="store_true", help="After autotune, re-evaluate path_a using best params and include as path_a_autotuned")
    ap.add_argument("--use-autotuned-as-primary", action="store_true", help="If set, replace primary path_a summary with path_a_autotuned when available")
    ap.add_argument("--path-b-depth", type=int, default=5, help="If >0, run Path B cascaded for N stages and report per-stage BER (default 5)")
    ap.add_argument("--path-b-sweep", action="store_true", help="Run Path B sweeps (amp_gain_db, sat_I_sat) and report BER curves")
    ap.add_argument("--no-path-b-sweep", action="store_true", help="Disable Path B sweeps (default is ON)")
    ap.add_argument("--path-b-analog-depth", type=int, default=-1, help="If -1, use --path-b-depth; if >0, run analog cascade (optics SA+amp per hop, single final threshold)")
    ap.add_argument("--adaptive-input", action="store_true", help="Integrate multiple frames until dv margin met or max frames (default ON)")
    ap.add_argument("--no-adaptive-input", action="store_true", help="Disable adaptive input integration")
    ap.add_argument("--adaptive-max-frames", type=int, default=12, help="Max frames to integrate for adaptive input")
    ap.add_argument("--adaptive-margin-mV", type=float, default=0.8, help="Extra margin above comparator up-threshold before stopping")
    ap.add_argument("--no-path-b", action="store_true", help="Disable Path B baselines")
    ap.add_argument("--no-path-b-analog", action="store_true", help="Disable Path B analog cascade baseline")
    ap.add_argument("--no-cold-input", action="store_true", help="Disable cold-storage input baseline")
    ap.add_argument("--components-mode", type=str, default="auto", help="Components attribution mode: auto|path_a|cold|path_b_analog")
    ap.add_argument("--mitigated", action="store_true", help="Compute mitigated BER using (chop, avg-frames, linear per-channel calibration)")
    ap.add_argument("--quiet", action="store_true", help="Do not print final JSON to stdout (write file only)")
    ap.add_argument("--progress", action="store_true", help="Emit coarse progress messages to stdout")
    ap.add_argument("--json", type=str, default=None)
    ap.add_argument("--light-output", action="store_true", help="Reduce output size by skipping heavy diagnostic blocks (sensitivity, drift, path-b sweeps, large arrays)")
    # Speed/skip flags
    ap.add_argument("--no-sweeps", action="store_true", help="Skip window/RIN/crosstalk sweeps for faster runs")
    ap.add_argument("--no-cal", action="store_true", help="Skip per-tile/calibration passes")
    ap.add_argument("--no-drift", action="store_true", help="Skip drift demo block")
    ap.add_argument("--fast", action="store_true", help="Shortcut: implies --no-sweeps --no-cal --no-drift and uses smaller internal caps")
    ap.add_argument("--lock-optics-ct", action="store_true", help="Constrain autotuner to keep optics ct_neighbor_db/ct_diag_db at initial values (no worsening)")
    # Vendor pack overrides (paths)
    ap.add_argument("--emitter-pack", type=str, default=None)
    ap.add_argument("--optics-pack", type=str, default=None)
    ap.add_argument("--sensor-pack", type=str, default=None)
    ap.add_argument("--tia-pack", type=str, default=None)
    ap.add_argument("--comparator-pack", type=str, default=None)
    ap.add_argument("--camera-pack", type=str, default=None)
    ap.add_argument("--clock-pack", type=str, default=None)
    ap.add_argument("--thermal-pack", type=str, default=None)
    # Normalization/mitigation toggles
    ap.add_argument("--normalize-dv", action="store_true", help="Normalize dv to comparator threshold scale inside orchestrator")
    ap.add_argument("--normalize-eps-v", type=float, default=1e-6, help="Epsilon to avoid divide-by-zero during dv normalization (V)")
    ap.add_argument("--export-vth", type=str, default=None, help="Export per-channel comparator vth (mV) learned during calibration to this JSON file")
    ap.add_argument("--import-vth", type=str, default=None, help="Import per-channel comparator vth (mV) from JSON file and apply to comparator")
    args = ap.parse_args()
    # Defaults to run full non-destructive suite
    run_path_b_sweep = (not getattr(args, 'no_path_b_sweep', False)) or getattr(args, 'path_b_sweep', False)
    args.path_b_sweep = bool(run_path_b_sweep)
    if not getattr(args, 'no_adaptive_input', False):
        args.adaptive_input = True

    # Base system from typ packs inline
    sys_p = SystemParams(channels=int(args.channels), window_ns=float(args.base_window_ns), temp_C=25.0, seed=args.seed,
                         normalize_dv=bool(getattr(args, 'normalize_dv', False)),
                         normalize_eps_v=float(getattr(args, 'normalize_eps_v', 1e-6)))
    # Build from overrides if provided (simple loader)
    def _load_yaml(path: str | None):
        if not path:
            return {}
        import importlib, pathlib
        text = pathlib.Path(path).read_text(encoding="utf-8")
        try:
            yaml_mod = importlib.import_module("yaml")
            return yaml_mod.safe_load(text) or {}
        except ModuleNotFoundError:
            return {}

    emit = EmitterParams(channels=sys_p.channels, power_mw_per_ch=0.7, power_sigma_pct=2.0, modulation_mode="pushpull", pushpull_alpha=0.9)
    emit_override = _load_yaml(getattr(args, 'emitter_pack', None))
    for k, v in (emit_override or {}).items():
        if hasattr(emit, k): setattr(emit, k, v)

    optx = OpticsParams(ct_model=("neighbor" if args.neighbor_ct else "global"))
    optx_override = _load_yaml(getattr(args, 'optics_pack', None))
    for k, v in (optx_override or {}).items():
        if hasattr(optx, k): setattr(optx, k, v)
    # Map common vendor-pack fields → sim params
    try:
        if isinstance(optx_override, dict):
            if 'transmittance_percent' in optx_override:
                tp = float(optx_override['transmittance_percent'])
                optx.transmittance = max(0.0, min(1.0, tp/100.0))
            if 'scatter_angle_deg_FWHM' in optx_override:
                ang = float(optx_override['scatter_angle_deg_FWHM'])
                # Heuristic: wider scatter → higher neighbor leakage (less negative dB)
                neigh = -40.0 + (ang - 5.0) * (10.0 / 15.0)  # 5°→-40dB, 20°→-30dB
                neigh = max(-45.0, min(-28.0, neigh))
                diag = neigh - 3.0
                optx.ct_model = 'neighbor'
                optx.ct_neighbor_db = float(neigh)
                optx.ct_diag_db = float(diag)
                # PSF width proxy
                w = 2.0 + max(0.0, (ang - 5.0)) * 0.2
                optx.psf_kernel = f"lorentzian:w={w:.2f}"
    except Exception:
        pass
    # Ensure neighbor/diag crosstalk are effective when neighbor model is active
    try:
        if isinstance(optx_override, dict) and (("ct_neighbor_db" in optx_override) or ("ct_diag_db" in optx_override)):
            optx.ct_model = 'neighbor'
            if getattr(optx, 'ct_neighbor_db', None) is None:
                base = float(getattr(optx, 'crosstalk_db', -30.0))
                optx.ct_neighbor_db = base
            if getattr(optx, 'ct_diag_db', None) is None:
                optx.ct_diag_db = float(optx.ct_neighbor_db) + 3.0
        elif getattr(optx, 'ct_model', 'global') == 'neighbor':
            base = float(getattr(optx, 'crosstalk_db', -30.0))
            if getattr(optx, 'ct_neighbor_db', None) is None:
                optx.ct_neighbor_db = base
            if getattr(optx, 'ct_diag_db', None) is None:
                optx.ct_diag_db = base + 3.0
    except Exception:
        pass

    pd = PDParams()
    pd_override = _load_yaml(getattr(args, 'sensor_pack', None))
    for k, v in (pd_override or {}).items():
        if hasattr(pd, k): setattr(pd, k, v)

    # Sensitivity mode tunes TIA BW and comparator noise to amplify trends
    tia_bw = 30.0 if args.sensitivity else 120.0
    comp_noise = 0.25 if args.sensitivity else 0.3
    tia = TIAParams(bw_mhz=tia_bw, tia_transimpedance_kohm=5.0, in_noise_pA_rthz=3.0, gain_sigma_pct=1.0)
    tia_override = _load_yaml(getattr(args, 'tia_pack', None))
    for k, v in (tia_override or {}).items():
        if hasattr(tia, k): setattr(tia, k, v)

    comp = ComparatorParams(input_noise_mV_rms=comp_noise, vth_mV=5.0, vth_sigma_mV=0.2)
    comp_override = _load_yaml(getattr(args, 'comparator_pack', None))
    for k, v in (comp_override or {}).items():
        if hasattr(comp, k): setattr(comp, k, v)

    clk = ClockParams(window_ns=float(args.base_window_ns), jitter_ps_rms=10.0)
    clk_override = _load_yaml(getattr(args, 'clock_pack', None))
    for k, v in (clk_override or {}).items():
        if hasattr(clk, k): setattr(clk, k, v)
    # Ensure CLI --base-window-ns always wins over pack defaults
    try:
        clk.window_ns = float(args.base_window_ns)
    except Exception:
        pass
    orch = Orchestrator(sys_p, emit, optx, pd, tia, comp, clk)

    # Helper: accumulate dv across frames using selected kernel
    def _accumulate_dv_over_frames(_orch, _tern, _N: int, _kernel: str, _alpha: float):
        import numpy as _np
        acc = None
        for _j in range(max(1, int(_N))):
            r = _orch.step(force_ternary=_tern)
            dv = _np.array(r.get("dv_mV", [0]*_orch.sys.channels))
            if acc is None:
                acc = dv.astype(float)
            else:
                if _kernel == "ewma":
                    acc = float(_alpha)*dv + (1.0-float(_alpha))*acc
                else:  # sum
                    acc = acc + dv
        return acc if acc is not None else _np.zeros(_orch.sys.channels, dtype=float)

    # Parse windows and ranges
    windows = [float(w) for w in args.windows.split(",") if w.strip()]
    rin_s, rin_e, rin_n = [v.strip() for v in args.rin_range.split(":")]
    ct_s, ct_e, ct_n = [v.strip() for v in args.ct_range.split(":")]

    # Short, pragmatic sweeps
    if not (getattr(args, 'no_sweeps', False) or getattr(args, 'fast', False)):
        w_xs, w_ys, w_ok = quick_window_sweep(orch, trials=args.trials, windows=windows)
        r_xs, r_ys, r_ok = quick_rin_sweep(sys_p, trials=args.trials, starts=float(rin_s), stops=float(rin_e), steps=int(rin_n), tia_bw_mhz=tia_bw, comp_noise_mV=comp_noise)
        c_xs, c_ys, c_ok = quick_crosstalk_sweep(sys_p, trials=args.trials, starts=float(ct_s), stops=float(ct_e), steps=int(ct_n), tia_bw_mhz=tia_bw, comp_noise_mV=comp_noise)
    else:
        w_xs, w_ys, w_ok = [float(args.base_window_ns)], [None], True
        r_xs, r_ys, r_ok = [], [], True
        c_xs, c_ys, c_ok = [], [], True

    # Baseline summary at default settings (use same policy for baseline and path_a)
    base_emit = EmitterParams(channels=sys_p.channels, modulation_mode="pushpull", pushpull_alpha=0.9)
    base_optx = OpticsParams(ct_model=("neighbor" if args.neighbor_ct else "global"))
    base_pd = PDParams()
    base_tia = TIAParams(bw_mhz=tia_bw)
    base_comp = ComparatorParams(input_noise_mV_rms=comp_noise, vth_mV=5.0, hysteresis_mV=1.8, vth_sigma_mV=0.2)
    base_clk = ClockParams(window_ns=float(args.base_window_ns), jitter_ps_rms=10.0)
    base_orch = Orchestrator(sys_p, base_emit, base_optx, base_pd, base_tia, base_comp, base_clk)
    # Optional: import per-channel vth (mV) and apply to primary and baseline comparators
    try:
        imp_path = getattr(args, 'import_vth', None)
        if isinstance(imp_path, str) and imp_path:
            import json as _json, pathlib as _pathlib, numpy as _np
            arr = _json.loads(_pathlib.Path(imp_path).read_text(encoding="utf-8"))
            vec = _np.asarray(arr, dtype=float)
            orch.comp.set_vth_per_channel(vec)
            try:
                base_orch.comp.set_vth_per_channel(vec)
            except Exception:
                pass
    except Exception:
        pass
    # Optional adaptive integration for input stage only (baseline)
    if args.adaptive_input:
        import numpy as _np
        errs = []
        T = int(args.trials)
        maxN = max(1, int(args.adaptive_max_frames))
        margin = float(args.adaptive_margin_mV)
        for _ in range(min(T, 400)):
            tern = base_orch.rng.integers(-1, 2, size=base_orch.sys.channels)
            acc = _np.zeros(base_orch.sys.channels, dtype=float)
            for k in range(maxN):
                r = base_orch.step(force_ternary=tern)
                dv = _np.array(r.get("dv_mV", [0]*base_orch.sys.channels))
                if dv.shape[0] != base_orch.sys.channels:
                    dv = dv[:base_orch.sys.channels]
                acc = acc[:dv.shape[0]]
                acc += dv
                up_th = float(base_orch.comp.p.vth_mV) + 0.5*float(base_orch.comp.p.hysteresis_mV)
                if _np.all(_np.abs(acc) >= (up_th + margin)):
                    break
            pred = _np.sign(acc)
            errs.append(float(_np.mean(pred != tern)))
        base_summary = {
            "p50_ber": float(_np.median(errs)) if errs else None,
            "p50_energy_pj": None,
            "window_ns": float(base_orch.clk.p.window_ns),
        }
    else:
        base_summary = base_orch.run(trials=args.trials)
    # Add mean_ber to baseline using a lightweight re-run (bounded)
    try:
        _rows_b = run_trials(base_orch, min(args.trials, 200))
        base_summary["mean_ber"] = mean_ber(_rows_b)
    except Exception:
        pass

    # Cold-storage input path (parallel baseline)
    cold_summary = None
    if not getattr(args, 'no_cold_input', False):
        try:
            cold_emit = ColdReader(ColdParams(channels=sys_p.channels))
            cold_orch = Orchestrator(sys_p, EmitterParams(channels=sys_p.channels), base_optx, base_pd, base_tia, base_comp, base_clk, emitter_override=cold_emit)
            cold_summary = cold_orch.run(trials=args.trials)
        except Exception:
            cold_summary = {"error": "cold_input_failed"}

    # Path B estimate (enable saturable absorber + optical amplifier in optics)
    path_b_summary = None
    path_b_chain = None
    path_b_sweeps = None
    try:
        b_emit = EmitterParams(**emit.__dict__)
        b_optx = OpticsParams(**optx.__dict__)
        b_optx.sat_abs_on = True
        b_optx.amp_on = True
        b_pd = PDParams(**pd.__dict__)
        b_tia = TIAParams(**tia.__dict__)
        b_comp = ComparatorParams(**comp.__dict__)
        b_clk = ClockParams(**clk.__dict__)
        b_orch = Orchestrator(sys_p, b_emit, b_optx, b_pd, b_tia, b_comp, b_clk)
        if not getattr(args, 'no_path_b', False):
            path_b_summary = b_orch.run(trials=args.trials)

        # Optional cascaded Path B chain: feed ternary outputs of stage k as inputs to k+1
        if int(getattr(args, "path_b_depth", 0)) > 0:
            import numpy as _np
            depth = int(args.path_b_depth)
            T = min(args.trials, 200)
            stage_errs = [[0.0]*T for _ in range(depth)]
            stage_cum_errs = [[0.0]*T for _ in range(depth)]
            for t_idx in range(T):
                in_vec = b_orch.rng.integers(-1, 2, size=b_orch.sys.channels)
                ref = in_vec.copy()
                for k in range(depth):
                    r = b_orch.step(force_ternary=in_vec)
                    out = _np.array(r.get("t_out", in_vec), dtype=int)
                    stage_errs[k][t_idx] = float(_np.mean(out != in_vec))
                    stage_cum_errs[k][t_idx] = float(_np.mean(out != ref))
                    in_vec = out
            per_stage_med_ber = [float(_np.median(stage_errs[k])) for k in range(depth)]
            per_stage_med_cum = [float(_np.median(stage_cum_errs[k])) for k in range(depth)]
            path_b_chain = {
                "depth": depth,
                "per_stage_p50_ber_vs_prev": per_stage_med_ber,
                "per_stage_p50_ber_vs_initial": per_stage_med_cum,
            }
        # Optional Path B sweeps for realism: amplifier gain and SA I_sat
        if (not getattr(args, 'light_output', False)) and bool(getattr(args, "path_b_sweep", False)) and (not getattr(args, 'no_path_b', False)):
            import numpy as _np
            # Sweep amplifier gain in dB
            gain_vals = [0, 5, 10, 15, 20]
            ber_vs_gain = []
            for g in gain_vals:
                b_optx.amp_on = True
                b_optx.amp_gain_db = float(g)
                b_orch2 = Orchestrator(sys_p, b_emit, b_optx, b_pd, b_tia, b_comp, b_clk)
                ber_vs_gain.append(float(b_orch2.run(trials=min(args.trials, 200)).get("p50_ber", None)))
            # Sweep SA I_sat (lower I_sat = stronger nonlinearity at lower current)
            isat_vals = [0.5, 1.0, 1.5, 2.0, 3.0]
            ber_vs_isat = []
            for s in isat_vals:
                b_optx.sat_abs_on = True
                b_optx.sat_I_sat = float(s)
                b_orch3 = Orchestrator(sys_p, b_emit, b_optx, b_pd, b_tia, b_comp, b_clk)
                ber_vs_isat.append(float(b_orch3.run(trials=min(args.trials, 200)).get("p50_ber", None)))
            path_b_sweeps = {
                "amp_gain_db": gain_vals,
                "p50_ber_vs_gain": ber_vs_gain,
                "sat_I_sat": isat_vals,
                "p50_ber_vs_isat": ber_vs_isat,
            }
        # Analog cascade (realistic accumulation): propagate analog intensities SA+amp per hop, O/E at end
        analog_depth = int(getattr(args, "path_b_analog_depth", -1))
        if analog_depth == -1:
            analog_depth = int(getattr(args, "path_b_depth", 0))
        if analog_depth > 0 and (not getattr(args, 'no_path_b_analog', False)):
            import numpy as _np
            T = min(args.trials, 200)
            errs = []
            for _ in range(T):
                tern0 = b_orch.rng.integers(-1, 2, size=b_orch.sys.channels)
                Pp, Pm = b_orch.emit.simulate(tern0, b_orch.clk.sample_window(), b_orch.sys.temp_C)
                for _k in range(analog_depth):
                    op, om, _, _ = b_orch.optx.simulate(Pp, Pm)
                    Pp, Pm = op, om
                Ip = b_orch.pd.simulate(Pp, b_orch.clk.sample_window())
                Im = b_orch.pd.simulate(Pm, b_orch.clk.sample_window())
                Vp = b_orch.tia.simulate(Ip, b_orch.clk.sample_window())
                Vm = b_orch.tia.simulate(Im, b_orch.clk.sample_window())
                out = b_orch.comp.simulate(Vp, Vm, b_orch.sys.temp_C)
                errs.append(float(_np.mean(out != tern0)))
            path_b_summary = dict(path_b_summary or {})
            path_b_summary["analog_depth"] = analog_depth
            path_b_summary["analog_p50_ber"] = float(_np.median(errs)) if errs else None
    except Exception:
        path_b_summary = None

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
    per_tile_after = None
    vth_suggest = None
    ber_after = None
    lin_scale = None
    lin_offset = None
    cal_summary = None
    try:
        if getattr(args, 'no_cal', False) or getattr(args, 'fast', False):
            raise RuntimeError('skip per-tile/calibration')
        blocks = base_orch.sys.channels
        blocks = int(blocks**0.5)
        if blocks*blocks == base_orch.sys.channels:
            # Run one frame to get tile mapping, then accumulate per-tile BER
            # Use a small additional run to estimate per-tile BER robustly
            cap_rows = min(args.trials, 200 if not getattr(args, 'fast', False) else 60)
            rows = [base_orch.step() for _ in range(int(cap_rows))]
            # Map channel -> tile index
            # Tiles are filled row-major in optics.simulate(); two rails per tile (plus/minus)
            # Here we approximate channel→tile as index // 1 (one channel per tile in current mapping)
            import numpy as _np
            tile_err = _np.zeros((blocks, blocks), dtype=float)
            tile_cnt = _np.zeros((blocks, blocks), dtype=float)
            dv_pos = []
            dv_neg = []
            for r in rows:
                t_out = r.get("t_out", [])
                truth = r.get("truth", [])
                dv = _np.array(r.get("dv_mV", [0]*len(t_out)), dtype=float)
                for ch, (o, z) in enumerate(zip(t_out, truth)):
                    by = ch // blocks
                    bx = ch % blocks
                    tile_err[by, bx] += 1.0 if int(o) != int(z) else 0.0
                    tile_cnt[by, bx] += 1.0
                    if z > 0:
                        dv_pos.append(dv[ch])
                    elif z < 0:
                        dv_neg.append(dv[ch])
            with _np.errstate(divide='ignore', invalid='ignore'):
                per_tile = (tile_err / _np.clip(tile_cnt, 1.0, None)).tolist()
            # Suggest per-channel vth: midpoint between class means (global suggestion for now)
            if dv_pos and dv_neg:
                vth_suggest = float(0.5*(float(_np.mean(dv_pos)) + float(_np.mean(dv_neg))))
            if not getattr(args, 'light_output', False):
                try:
                    from looking_glass.plotting import save_heatmap as _save_hm
                    _save_hm(per_tile, xlabel="tile-x", ylabel="tile-y", out_path="out/ber_per_tile.png", title="Per-tile BER")
                except Exception:
                    pass
            # Calibration pass: collect per-channel dv stats, compute vth per channel, apply and re-run
            # Build a fresh orchestrator to apply trims
            cal_emit = EmitterParams(**emit.__dict__)
            cal_optx = OpticsParams(**optx.__dict__)
            cal_pd = PDParams(**pd.__dict__)
            cal_tia = TIAParams(**tia.__dict__)
            cal_comp = ComparatorParams(**comp.__dict__)
            cal_clk = ClockParams(**clk.__dict__)
            orch_cal = Orchestrator(sys_p, cal_emit, cal_optx, cal_pd, cal_tia, cal_comp, cal_clk)
            # Gather dv per channel given known ternary patterns
            pos_sum = _np.zeros(sys_p.channels, dtype=float)
            pos_cnt = _np.zeros(sys_p.channels, dtype=float)
            neg_sum = _np.zeros(sys_p.channels, dtype=float)
            neg_cnt = _np.zeros(sys_p.channels, dtype=float)
            total_cal = int(min(args.trials*2, 400 if not getattr(args, 'fast', False) else 120))
            for idx in range(total_cal):
                tern = orch_cal.rng.integers(-1, 2, size=sys_p.channels)
                r = orch_cal.step(force_ternary=tern)
                dv = _np.array(r.get("dv_mV", [0]*sys_p.channels), dtype=float)
                pos = tern > 0
                neg = tern < 0
                pos_sum[pos] += dv[pos]
                pos_cnt[pos] += 1.0
                neg_sum[neg] += dv[neg]
                neg_cnt[neg] += 1.0
                if args.progress and (idx+1) % 50 == 0:
                    print(f"PROGRESS: calibration gather {idx+1}/{total_cal}")
            pos_mean = _np.divide(pos_sum, _np.clip(pos_cnt, 1.0, None))
            neg_mean = _np.divide(neg_sum, _np.clip(neg_cnt, 1.0, None))
            vth_vec = 0.5*(pos_mean + neg_mean)
            # Linear per-channel calibration: scale/offset dv so classes map to ±1
            eps = 1e-6
            lin_scale = 2.0/_np.clip((pos_mean - neg_mean), eps, None)
            lin_offset = -0.5*(pos_mean + neg_mean)
            # Apply per-channel trims
            orch_cal.comp.set_vth_per_channel(vth_vec)
            # Evaluate post-calibration BER and per-tile BER
            rows_after = []
            total_eval = int(min(args.trials, 200 if not getattr(args, 'fast', False) else 60))
            for j in range(total_eval):
                rows_after.append(orch_cal.step())
                if args.progress and (j+1) % 50 == 0:
                    print(f"PROGRESS: calibration evaluate {j+1}/{total_eval}")
            tile_err2 = _np.zeros((blocks, blocks), dtype=float)
            tile_cnt2 = _np.zeros((blocks, blocks), dtype=float)
            for r in rows_after:
                t_out = r.get("t_out", [])
                truth = r.get("truth", [])
                for ch, (o, z) in enumerate(zip(t_out, truth)):
                    by = ch // blocks
                    bx = ch % blocks
                    tile_err2[by, bx] += 1.0 if int(o) != int(z) else 0.0
                    tile_cnt2[by, bx] += 1.0
            with _np.errstate(divide='ignore', invalid='ignore'):
                per_tile_after = (tile_err2 / _np.clip(tile_cnt2, 1.0, None)).tolist()
            # Full-run BER after applying trims
            cal_summary = orch_cal.run(trials=args.trials)
            ber_after = float(cal_summary.get("p50_ber", None))
            if not getattr(args, 'light_output', False):
                try:
                    from looking_glass.plotting import save_heatmap as _save_hm
                    _save_hm(per_tile_after, xlabel="tile-x", ylabel="tile-y", out_path="out/ber_per_tile_after.png", title="Per-tile BER (after calib)")
                except Exception:
                    pass
    except Exception:
        per_tile = None

    # Per-component BER attribution (toggle one component to an idealized variant)
    components = None
    try:
        import numpy as _np
        fixed_inputs = _build_fixed_inputs(args.seed, sys_p.channels, min(args.trials, 200))
        # Determine baseline orchestrator for attribution based on mode
        comp_mode = (getattr(args, 'components_mode', 'auto') or 'auto').lower()
        base_for_components = base_orch
        base_labeled = "path_a"
        if comp_mode == 'cold' and not getattr(args, 'no_cold_input', False):
            try:
                cold_emit = ColdReader(ColdParams(channels=sys_p.channels))
                base_for_components = Orchestrator(sys_p, EmitterParams(channels=sys_p.channels), base_optx, base_pd, base_tia, base_comp, base_clk, emitter_override=cold_emit)
                base_labeled = "cold"
            except Exception:
                base_for_components = base_orch
                base_labeled = "path_a"
        elif comp_mode in ('path_b_analog', 'path_b') and (not getattr(args, 'no_path_b', False)):
            # Build a Path B baseline orchestrator (with SA+amp on) for attribution
            b_emit = EmitterParams(**emit.__dict__)
            b_optx = OpticsParams(**optx.__dict__)
            b_optx.sat_abs_on = True
            b_optx.amp_on = True
            base_for_components = Orchestrator(sys_p, b_emit, b_optx, base_pd, base_tia, base_comp, base_clk)
            base_labeled = "path_b"
        baseline_med = _med_ber_fixed_inputs(base_for_components, fixed_inputs)

        def clone_orch(e=None, o=None, p=None, t=None, c=None, k=None):
            # Respect the attribution baseline's current packs (so mode follows path specifics)
            be = getattr(base_for_components, 'emit').p if hasattr(base_for_components, 'emit') else base_emit
            bo = getattr(base_for_components, 'optx').p if hasattr(base_for_components, 'optx') else base_optx
            bp = getattr(base_for_components, 'pd').p if hasattr(base_for_components, 'pd') else base_pd
            bt = getattr(base_for_components, 'tia').p if hasattr(base_for_components, 'tia') else base_tia
            bc = getattr(base_for_components, 'comp').p if hasattr(base_for_components, 'comp') else base_comp
            bk = getattr(base_for_components, 'clk').p if hasattr(base_for_components, 'clk') else base_clk
            return Orchestrator(
                sys_p,
                e if e is not None else be,
                o if o is not None else bo,
                p if p is not None else bp,
                t if t is not None else bt,
                c if c is not None else bc,
                k if k is not None else bk,
            )

        # Idealized params per component (keep scales, remove dominant noise terms)
        ideal_emit = replace(base_emit, rin_dbhz=-200.0, extinction_db=max(30.0, getattr(base_emit, 'extinction_db', 20.0)), power_sigma_pct=0.0)
        ideal_optx = replace(base_optx,
                             crosstalk_db=-60.0,
                             ct_model="global",
                             stray_floor_db=-80.0,
                             w_plus_contrast=0.95,
                             w_minus_contrast=0.95)
        ideal_pd = replace(base_pd, dark_current_nA=0.0)
        ideal_tia = replace(base_tia,
                            in_noise_pA_rthz=0.0,
                            bw_mhz=max(1000.0, float(getattr(base_tia, 'bw_mhz', 80.0))),
                            adc_read_noise_mV_rms=0.0,
                            slew_v_per_us=1e9,
                            gain_sigma_pct=0.0)
        ideal_comp = replace(base_comp, input_noise_mV_rms=0.0, hysteresis_mV=0.0, vth_sigma_mV=0.0)

        # Evaluate BER with each component idealized (others baseline)
        ber_emit = _med_ber_fixed_inputs(clone_orch(e=ideal_emit), fixed_inputs)
        ber_optx = _med_ber_fixed_inputs(clone_orch(o=ideal_optx), fixed_inputs)
        ber_pd = _med_ber_fixed_inputs(clone_orch(p=ideal_pd), fixed_inputs)
        ber_tia = _med_ber_fixed_inputs(clone_orch(t=ideal_tia), fixed_inputs)
        ber_comp = _med_ber_fixed_inputs(clone_orch(c=ideal_comp), fixed_inputs)
        components = {
            "baseline_p50_ber": baseline_med,
            "emitter_ideal_p50_ber": ber_emit,
            "optics_ideal_p50_ber": ber_optx,
            "pd_ideal_p50_ber": ber_pd,
            "tia_ideal_p50_ber": ber_tia,
            "comparator_ideal_p50_ber": ber_comp,
            "mode": base_labeled,
            "delta": {
                "emitter": None if (baseline_med is None or ber_emit is None) else float(max(0.0, baseline_med - ber_emit)),
                "optics": None if (baseline_med is None or ber_optx is None) else float(max(0.0, baseline_med - ber_optx)),
                "pd": None if (baseline_med is None or ber_pd is None) else float(max(0.0, baseline_med - ber_pd)),
                "tia": None if (baseline_med is None or ber_tia is None) else float(max(0.0, baseline_med - ber_tia)),
                "comparator": None if (baseline_med is None or ber_comp is None) else float(max(0.0, baseline_med - ber_comp)),
            }
        }
    except Exception:
        components = None

    # Realism heuristic scoring (0.0–1.0)
    def realism_scores():
        scores = {}
        # Emitter: extinction, RIN in plausible range
        rin = float(emit.rin_dbhz if hasattr(emit, 'rin_dbhz') else -150.0)
        ext = float(emit.extinction_db if hasattr(emit, 'extinction_db') else 20.0)
        s_rin = min(1.0, max(0.0, (rin + 180.0) / 30.0))  # -180..-150 → 0..1, flatter above
        s_ext = min(1.0, max(0.0, (ext - 10.0) / 20.0))   # 10..30 dB → 0..1
        scores["emitter"] = {"score": round(0.6*s_rin + 0.4*s_ext, 3), "rin_dbhz": rin, "extinction_db": ext}
        # Optics: crosstalk and stray floor
        ct = float(optx.crosstalk_db if hasattr(optx, 'crosstalk_db') else -28.0)
        stray = float(optx.stray_floor_db if hasattr(optx, 'stray_floor_db') else -38.0)
        s_ct = min(1.0, max(0.0, (-ct - 18.0) / 20.0))    # -38..-18 → 1..0
        s_stray = min(1.0, max(0.0, (-stray - 28.0) / 20.0))
        scores["optics"] = {"score": round(0.7*s_ct + 0.3*s_stray, 3), "crosstalk_db": ct, "stray_floor_db": stray}
        # Camera: read noise and full well
        # Not always present here; approximate typical values
        scores["camera"] = {"score": 0.7, "read_noise_e_rms": 2.0, "full_well_e": 20000.0}
        # TIA: bandwidth and input noise
        bw = float(tia_bw)
        in_n = float(getattr(tia, 'in_noise_pA_rthz', 5.0))
        s_bw = min(1.0, max(0.0, (bw - 20.0) / 100.0))
        s_in = min(1.0, max(0.0, (8.0 - in_n) / 8.0))
        scores["tia"] = {"score": round(0.5*s_bw + 0.5*s_in, 3), "bw_mhz": bw, "in_noise_pA_rthz": in_n}
        # Comparator: noise and drift
        comp_n = float(comp.input_noise_mV_rms)
        s_cn = min(1.0, max(0.0, (1.2 - comp_n) / 1.2))
        scores["comparator"] = {"score": round(s_cn, 3), "input_noise_mV_rms": comp_n}
        return scores

    # Optional temporal voting estimate (repeat > 1)
    vote3_ber = None
    rep = max(3 if args.vote3 else 1, int(args.repeat))
    if rep > 1:
        import numpy as _np
        errs = []
        for _ in range(min(args.trials, 200)):
            # Use a fixed ternary vector per trial to enable meaningful voting
            tern = base_orch.rng.integers(-1, 2, size=base_orch.sys.channels)
            outs = []
            for _j in range(rep):
                outs.append(base_orch.step(force_ternary=tern)["t_out"])
            t = _np.array(tern)
            O = _np.vstack(outs)
            vote = _np.sign(_np.sum(O, axis=0))
            errs.append(float(_np.mean(vote != t)))
        vote3_ber = float(_np.median(errs)) if errs else None

    # Pseudo spatial oversampling (S>1): majority vote across S repeats per input
    spatial_ber = None
    S = max(1, int(args.spatial_oversample))
    if S > 1:
        import numpy as _np
        errs = []
        for _ in range(min(args.trials, 200)):
            tern = base_orch.rng.integers(-1, 2, size=base_orch.sys.channels)
            outs = []
            for _j in range(S):
                outs.append(base_orch.step(force_ternary=tern)["t_out"])
            t = _np.array(tern)
            O = _np.vstack(outs)
            vote = _np.sign(_np.sum(O, axis=0))
            errs.append(float(_np.mean(vote != t)))
        spatial_ber = float(_np.median(errs)) if errs else None

    # Lock-in estimate: subtract a dark dv per trial and threshold on sign
    lockin_ber = None
    if args.lockin:
        import numpy as _np
        errs = []
        for _ in range(min(args.trials, 200)):
            tern = base_orch.rng.integers(-1, 2, size=base_orch.sys.channels)
            r_sig = base_orch.step(force_ternary=tern)
            r_dark = base_orch.step(force_ternary=_np.zeros_like(tern))
            dv_sig = _np.array(r_sig.get("dv_mV", [0]*base_orch.sys.channels))
            dv_dark = _np.array(r_dark.get("dv_mV", [0]*base_orch.sys.channels))
            dv_diff = dv_sig - dv_dark
            pred = _np.sign(dv_diff)
            errs.append(float(_np.mean(pred != tern)))
        lockin_ber = float(_np.median(errs)) if errs else None

    # Chopper stabilization: use +x and -x frames, subtract, then threshold
    chop_ber = None
    if args.chop:
        import numpy as _np
        errs = []
        for _ in range(min(args.trials, 200)):
            tern = base_orch.rng.integers(-1, 2, size=base_orch.sys.channels)
            r_pos = base_orch.step(force_ternary=tern)
            r_neg = base_orch.step(force_ternary=-tern)
            dv_pos = _np.array(r_pos.get("dv_mV", [0]*base_orch.sys.channels))
            dv_neg = _np.array(r_neg.get("dv_mV", [0]*base_orch.sys.channels))
            dv_diff = dv_pos - dv_neg
            pred = _np.sign(dv_diff)
            errs.append(float(_np.mean(pred != tern)))
        chop_ber = float(_np.median(errs)) if errs else None

    # Frame averaging on dv: average N frames per input, then threshold
    avg_frames_ber = None
    if int(args.avg_frames) > 1:
        import numpy as _np
        N = int(args.avg_frames)
        errs = []
        for _ in range(min(args.trials, 200)):
            tern = base_orch.rng.integers(-1, 2, size=base_orch.sys.channels)
            acc = _accumulate_dv_over_frames(base_orch, tern, N, str(getattr(args, 'avg_kernel', 'sum')), float(getattr(args, 'avg_ema_alpha', 0.6)))
            pred = _np.sign(acc)
            errs.append(float(_np.mean(pred != tern)))
        avg_frames_ber = float(_np.median(errs)) if errs else None

    # Software threshold (upper bound Path A): learn per-channel vth, then classify dv
    soft_thresh_ber = None
    if args.soft_thresh:
        import numpy as _np
        # Learn per-channel vth from a short calibration set
        pos_sum = _np.zeros(sys_p.channels, dtype=float)
        pos_cnt = _np.zeros(sys_p.channels, dtype=float)
        neg_sum = _np.zeros(sys_p.channels, dtype=float)
        neg_cnt = _np.zeros(sys_p.channels, dtype=float)
        for _ in range(min(300, max(100, args.trials))):
            tern = base_orch.rng.integers(-1, 2, size=sys_p.channels)
            r = base_orch.step(force_ternary=tern)
            dv = _np.array(r.get("dv_mV", [0]*sys_p.channels), dtype=float)
            pos = tern > 0
            neg = tern < 0
            pos_sum[pos] += dv[pos]; pos_cnt[pos] += 1
            neg_sum[neg] += dv[neg]; neg_cnt[neg] += 1
        pos_mean = _np.divide(pos_sum, _np.clip(pos_cnt, 1.0, None))
        neg_mean = _np.divide(neg_sum, _np.clip(neg_cnt, 1.0, None))
        vth_vec = 0.5*(pos_mean + neg_mean)
        errs = []
        for _ in range(min(args.trials, 200)):
            tern = base_orch.rng.integers(-1, 2, size=sys_p.channels)
            r = base_orch.step(force_ternary=tern)
            dv = _np.array(r.get("dv_mV", [0]*sys_p.channels), dtype=float)
            pred = _np.sign(dv - vth_vec)
            errs.append(float(_np.mean(pred != tern)))
        soft_thresh_ber = float(_np.median(errs)) if errs else None

    # Mitigated pipeline: chopper + frame averaging + linear per-channel calibration, then sign
    mitigated_ber = None
    if args.mitigated and (lin_scale is not None) and (lin_offset is not None):
        import numpy as _np
        errs = []
        N = max(1, int(args.avg_frames))
        for _ in range(min(args.trials, 200)):
            tern = base_orch.rng.integers(-1, 2, size=base_orch.sys.channels)
            acc = _np.zeros(base_orch.sys.channels, dtype=float)
            for _j in range(N):
                if args.chop:
                    r_pos = base_orch.step(force_ternary=tern)
                    r_neg = base_orch.step(force_ternary=-tern)
                    dv = _np.array(r_pos.get("dv_mV", [0]*base_orch.sys.channels)) - _np.array(r_neg.get("dv_mV", [0]*base_orch.sys.channels))
                else:
                    r = base_orch.step(force_ternary=tern)
                    dv = _np.array(r.get("dv_mV", [0]*base_orch.sys.channels))
                if dv.shape[0] != base_orch.sys.channels:
                    dv = dv[:base_orch.sys.channels]
                acc = acc[:dv.shape[0]]
                acc += dv
            dv_avg = acc/float(N)
            dv_lin = lin_scale*(dv_avg + lin_offset)
            pred = _np.sign(dv_lin)
            errs.append(float(_np.mean(pred != tern)))
        mitigated_ber = float(_np.median(errs)) if errs else None

    # Optional quick per-channel calibration to set vth for path_a/baseline even when --no-cal
    # Initialize masking and calibration vectors
    active_mask = None
    vth_vec_pa = None
    try:
        if getattr(args, 'apply_calibration', False):
            import numpy as _np
            calN = int(min(max(120, args.trials), 240))
            pos_sum = _np.zeros(sys_p.channels, dtype=float)
            pos_cnt = _np.zeros(sys_p.channels, dtype=float)
            neg_sum = _np.zeros(sys_p.channels, dtype=float)
            neg_cnt = _np.zeros(sys_p.channels, dtype=float)
            # Use a fresh clone to avoid contaminating main RNG state
            cal_orch = Orchestrator(sys_p, EmitterParams(**emit.__dict__), OpticsParams(**optx.__dict__), PDParams(**pd.__dict__), TIAParams(**tia.__dict__), ComparatorParams(**comp.__dict__), ClockParams(**clk.__dict__))
            for _ in range(calN):
                tern = cal_orch.rng.integers(-1, 2, size=sys_p.channels)
                r = cal_orch.step(force_ternary=tern)
                dv = _np.array(r.get("dv_mV", [0]*sys_p.channels), dtype=float)
                pos = tern > 0
                neg = tern < 0
                pos_sum[pos] += dv[pos]; pos_cnt[pos] += 1
                neg_sum[neg] += dv[neg]; neg_cnt[neg] += 1
            pos_mean = _np.divide(pos_sum, _np.clip(pos_cnt, 1.0, None))
            neg_mean = _np.divide(neg_sum, _np.clip(neg_cnt, 1.0, None))
            vth_vec_pa = 0.5*(pos_mean + neg_mean)
            # Apply to comparator for main orchestrator
            try:
                orch.comp.set_vth_per_channel(vth_vec_pa)
            except Exception:
                pass
            # Optionally export the learned per-channel vth (mV)
            try:
                exp_path = getattr(args, 'export_vth', None)
                if isinstance(exp_path, str) and exp_path:
                    import json as _json, os as _os
                    _os.makedirs(_os.path.dirname(exp_path), exist_ok=True)
                    with open(exp_path, "w", encoding="utf-8") as _f:
                        _json.dump([float(x) for x in vth_vec_pa.tolist()], _f)
            except Exception:
                pass
    except Exception:
        vth_vec_pa = None

    # Build bad-channel mask BEFORE classifier evaluation so it is applied
    masked_count = 0
    try:
        Nmask = int(max(int(getattr(args, 'mask_bad_channels', 0)), float(getattr(args, 'mask_bad_frac', 0.0)) * float(sys_p.channels)))
        if Nmask > 0:
            import numpy as _np
            trials_mask = int(max(50, min(getattr(args, 'calib_mask_trials', 200), 500)))
            ch = sys_p.channels
            err_counts = None
            for _ in range(trials_mask):
                tern = orch.rng.integers(-1, 2, size=ch)
                r = orch.step(force_ternary=tern)
                # Prefer comparator outputs for mask (matches classifier); fallback to dv sign
                tout = _np.array(r.get("t_out", []), dtype=int)
                if tout.size == 0:
                    dv = _np.array(r.get("dv_mV", []), dtype=float)
                    tout = _np.sign(dv).astype(int)
                if err_counts is None:
                    err_counts = _np.zeros_like(tout, dtype=float)
                if tout.shape[0] != ch:
                    tern = tern[:tout.shape[0]]
                err_counts += (tout != tern)
            rates = err_counts / float(max(1, trials_mask))
            idx = _np.argsort(rates)[::-1][:min(Nmask, rates.shape[0])]
            active_mask = _np.ones_like(rates, dtype=bool)
            active_mask[idx] = False
            try:
                import numpy as _np
                masked_count = int((_np.asarray(active_mask) == False).sum())
            except Exception:
                masked_count = int(Nmask)
    except Exception:
        active_mask = None

    # Path A summary with configured packs (reflects vendor overrides)
    # If classifier is explicitly chosen, honor it; otherwise precedence: soft > avg > adaptive > default
    cls_choice = getattr(args, 'classifier', None)
    if cls_choice in ('vote3','vote5','repeat'):
        import numpy as _np
        errs = []
        if cls_choice == 'vote3':
            repN = 3
        elif cls_choice == 'vote5':
            repN = 5
        else:
            repN = max(1, int(getattr(args, 'repeat', 1)))
        for _ in range(min(args.trials, 200)):
            tern = orch.rng.integers(-1, 2, size=orch.sys.channels)
            votes = None
            for j in range(repN):
                # Optional permutation diversity across repeats
                if getattr(args, 'permute_repeats', False):
                    if args.permute_scheme == 'cyclic':
                        perm = _np.roll(_np.arange(orch.sys.channels), j)
                    else:
                        perm = _np.array(orch.rng.permutation(orch.sys.channels))
                    inv = _np.argsort(perm)
                    # Apply permutation to input channels
                    tern_perm = tern[perm]
                    r = orch.step(force_ternary=tern_perm)
                    tout = _np.array(r.get("t_out", [0]*orch.sys.channels), dtype=int)
                    # De-permute t_out back to logical order
                    tout = tout[inv]
                else:
                    r = orch.step(force_ternary=tern)
                    tout = _np.array(r.get("t_out", [0]*orch.sys.channels), dtype=int)
                # Apply bad-channel mask if present
                if active_mask is not None:
                    M = min(len(active_mask), tout.shape[0])
                    tout = tout[:M]; tsel = tern[:M]; am = active_mask[:M]
                    tout = tout[am]; tcur = tsel[am]
                else:
                    tcur = tern
                # Initialize votes matrix on first repeat with effective length
                if votes is None:
                    votes = _np.zeros((repN, len(tcur)), dtype=int)
                votes[j, :len(tout)] = _np.sign(tout)
            # Tie-break zeros toward +1 to avoid 0 labels
            vote_sum = _np.sum(votes, axis=0)
            pred = _np.where(vote_sum >= 0, 1, -1)
            errs.append(float(_np.mean(pred != tcur)))
        path_a_summary = {
            "p50_ber": float(_np.median(errs)) if errs else None,
            "p50_energy_pj": None,
            "window_ns": float(orch.clk.p.window_ns),
        }
    elif cls_choice == 'replicate2':
        import numpy as _np
        errs = []
        ch = orch.sys.channels
        # Two complementary permutations: identity and half-rotate (for even channels)
        base_perm = _np.arange(ch)
        if ch % 2 == 0:
            alt_perm = _np.roll(base_perm, ch//2)
        else:
            alt_perm = _np.array(orch.rng.permutation(ch))
        inv_base = _np.argsort(base_perm)
        inv_alt = _np.argsort(alt_perm)
        for _ in range(min(args.trials, 200)):
            tern = orch.rng.integers(-1, 2, size=ch)
            # Pass 1: identity
            r1 = orch.step(force_ternary=tern[base_perm])
            dv1 = _np.array(r1.get("dv_mV", [0]*ch))[inv_base]
            # Pass 2: alternate permutation
            r2 = orch.step(force_ternary=tern[alt_perm])
            dv2 = _np.array(r2.get("dv_mV", [0]*ch))[inv_alt]
            dv_sum = dv1 + dv2
            tcur = tern
            if active_mask is not None:
                M = min(len(active_mask), dv_sum.shape[0])
                dv_sum = dv_sum[:M]; tcur = tcur[:M]; am = active_mask[:M]
                dv_sum = dv_sum[am]; tcur = tcur[am]
            if vth_vec_pa is not None:
                vv = vth_vec_pa
                if active_mask is not None:
                    vv = vv[:M][am]
                pred = _np.sign(dv_sum - 2.0*vv)
            else:
                pred = _np.sign(dv_sum)
            errs.append(float(_np.mean(pred != tcur)))
        path_a_summary = {
            "p50_ber": float(_np.median(errs)) if errs else None,
            "p50_energy_pj": None,
            "window_ns": float(orch.clk.p.window_ns),
        }
    elif cls_choice == 'replicate':
        import numpy as _np
        errs = []
        ch = orch.sys.channels
        repN = max(2, int(getattr(args, 'repeat', 2)))
        for _ in range(min(args.trials, 200)):
            tern = orch.rng.integers(-1, 2, size=ch)
            dv_acc = _np.zeros(ch, dtype=float)
            for j in range(repN):
                if getattr(args, 'permute_repeats', False):
                    if args.permute_scheme == 'cyclic':
                        perm = _np.roll(_np.arange(ch), j)
                    else:
                        perm = _np.array(orch.rng.permutation(ch))
                    inv = _np.argsort(perm)
                    r = orch.step(force_ternary=tern[perm])
                    dv = _np.array(r.get("dv_mV", [0]*ch))[inv]
                else:
                    r = orch.step(force_ternary=tern)
                    dv = _np.array(r.get("dv_mV", [0]*ch))
                dv_acc += dv
            tcur = tern
            if active_mask is not None:
                M = min(len(active_mask), dv_acc.shape[0])
                dv_acc = dv_acc[:M]; tcur = tcur[:M]; am = active_mask[:M]
                dv_acc = dv_acc[am]; tcur = tcur[am]
            if vth_vec_pa is not None:
                vv = vth_vec_pa
                if active_mask is not None:
                    vv = vv[:M][am]
                # Compare against scaled threshold and tie-break zeros to +1
                pred = _np.where((dv_acc - float(repN)*vv) >= 0.0, 1, -1)
            else:
                pred = _np.where(dv_acc >= 0.0, 1, -1)
            errs.append(float(_np.mean(pred != tcur)))
        path_a_summary = {
            "p50_ber": float(_np.median(errs)) if errs else None,
            "p50_energy_pj": None,
            "window_ns": float(orch.clk.p.window_ns),
        }
    elif cls_choice == 'phys2x':
        # Simulate 2x physical redundancy: each logical channel is read from two physical tiles simultaneously
        # Implementation: run once on tern, then again on a half-rotated channel assignment and sum dv
        import numpy as _np
        errs = []
        ch = orch.sys.channels
        base_perm = _np.arange(ch)
        if ch % 2 == 0:
            alt_perm = _np.roll(base_perm, ch//2)
        else:
            alt_perm = _np.array(orch.rng.permutation(ch))
        inv_base = _np.argsort(base_perm)
        inv_alt = _np.argsort(alt_perm)
        for _ in range(min(args.trials, 200)):
            tern = orch.rng.integers(-1, 2, size=ch)
            r1 = orch.step(force_ternary=tern[base_perm])
            dv1 = _np.array(r1.get("dv_mV", [0]*ch))[inv_base]
            r2 = orch.step(force_ternary=tern[alt_perm])
            dv2 = _np.array(r2.get("dv_mV", [0]*ch))[inv_alt]
            dv_sum = dv1 + dv2
            if vth_vec_pa is not None:
                pred = _np.sign(dv_sum - 2.0*vth_vec_pa)
            else:
                pred = _np.sign(dv_sum)
            errs.append(float(_np.mean(pred != tern)))
        path_a_summary = {
            "p50_ber": float(_np.median(errs)) if errs else None,
            "p50_energy_pj": None,
            "window_ns": float(orch.clk.p.window_ns),
        }
    elif cls_choice == 'lockin' and (lockin_ber is not None):
        path_a_summary = {"p50_ber": lockin_ber, "p50_energy_pj": None, "window_ns": float(orch.clk.p.window_ns)}
    elif cls_choice == 'chop' and (chop_ber is not None):
        path_a_summary = {"p50_ber": chop_ber, "p50_energy_pj": None, "window_ns": float(orch.clk.p.window_ns)}
    elif cls_choice == 'mitigated' and (mitigated_ber is not None):
        path_a_summary = {"p50_ber": mitigated_ber, "p50_energy_pj": None, "window_ns": float(orch.clk.p.window_ns)}
    elif cls_choice == 'soft' or getattr(args, 'soft_thresh', False):
        import numpy as _np
        errs = []
        for _ in range(min(args.trials, 200)):
            tern = orch.rng.integers(-1, 2, size=orch.sys.channels)
            r = orch.step(force_ternary=tern)
            dv = _np.array(r.get("dv_mV", [0]*orch.sys.channels))
            tcur = tern
            if active_mask is not None:
                M = min(len(active_mask), dv.shape[0])
                dv = dv[:M]; tcur = tcur[:M]; am = active_mask[:M]
                dv = dv[am]; tcur = tcur[am]
            if vth_vec_pa is not None:
                vv = vth_vec_pa
                if active_mask is not None:
                    vv = vv[:M][am]
                pred = _np.where((dv - vv) >= 0.0, 1, -1)
            else:
                pred = _np.where(dv >= 0.0, 1, -1)
            errs.append(float(_np.mean(pred != tcur)))
        path_a_summary = {
            "p50_ber": float(_np.median(errs)) if errs else None,
            "p50_energy_pj": None,
            "window_ns": float(orch.clk.p.window_ns),
        }
    elif cls_choice == 'avg' or (getattr(args, 'use_avg_frames_for_path_a', False) and int(args.avg_frames) > 1):
        import numpy as _np
        N = int(args.avg_frames)
        errs = []
        for _ in range(min(args.trials, 200)):
            tern = orch.rng.integers(-1, 2, size=orch.sys.channels)
            acc = _accumulate_dv_over_frames(orch, tern, N, str(getattr(args, 'avg_kernel', 'sum')), float(getattr(args, 'avg_ema_alpha', 0.6)))
            if vth_vec_pa is not None:
                pred = _np.sign(acc - vth_vec_pa)
            else:
                pred = _np.sign(acc)
            errs.append(float(_np.mean(pred != tern)))
        path_a_summary = {
            "p50_ber": float(_np.median(errs)) if errs else None,
            "p50_energy_pj": None,
            "window_ns": float(orch.clk.p.window_ns),
        }
    elif cls_choice == 'adaptive' or args.adaptive_input:
        import numpy as _np
        errs = []
        T = int(args.trials)
        maxN = max(1, int(args.adaptive_max_frames))
        margin = float(args.adaptive_margin_mV)
        for _ in range(min(T, 400)):
            tern = orch.rng.integers(-1, 2, size=orch.sys.channels)
            acc = _np.zeros(orch.sys.channels, dtype=float)
            for k in range(maxN):
                r = orch.step(force_ternary=tern)
                dv = _np.array(r.get("dv_mV", [0]*orch.sys.channels))
                if dv.shape[0] != orch.sys.channels:
                    dv = dv[:orch.sys.channels]
                acc = acc[:dv.shape[0]]
                acc += dv
                dv = _np.array(r.get("dv_mV", [0]*orch.sys.channels))
                if dv.shape[0] != orch.sys.channels:
                    dv = dv[:orch.sys.channels]
                acc = acc[:dv.shape[0]]
                acc += dv
                up_th = float(orch.comp.p.vth_mV) + 0.5*float(orch.comp.p.hysteresis_mV)
                if _np.all(_np.abs(acc) >= (up_th + margin)):
                    break
            if vth_vec_pa is not None:
                pred = _np.sign(acc - vth_vec_pa)
            else:
                pred = _np.sign(acc)
            errs.append(float(_np.mean(pred != tern)))
        path_a_summary = {
            "p50_ber": float(_np.median(errs)) if errs else None,
            "p50_energy_pj": None,
            "window_ns": float(orch.clk.p.window_ns),
        }
    else:
        path_a_summary = orch.run(trials=args.trials)
    # Add mean_ber to path_a using a lightweight re-run (bounded)
    try:
        _rows_a = run_trials(orch, min(args.trials, 200))
        path_a_summary["mean_ber"] = mean_ber(_rows_a)
    except Exception:
        pass

    # (Mask already built above; no-op here)

    summary = {
        "config": {
            "trials": args.trials,
            "seed": args.seed,
            "sensitivity": args.sensitivity,
            "vote3": (rep == 3 and args.vote3),
            "repeat": rep,
            "neighbor_ct": bool(args.neighbor_ct),
            "base_window_ns": float(args.base_window_ns),
            "applied_calibration": bool(args.apply_calibration),
            "adaptive_input": bool(args.adaptive_input),
            "adaptive_max_frames": int(args.adaptive_max_frames),
            "adaptive_margin_mV": float(args.adaptive_margin_mV),
            "avg_frames": int(args.avg_frames),
            "classifier": (cls_choice or "auto"),
            "mask_bad_channels_req": int(getattr(args, 'mask_bad_channels', 0)),
            "mask_bad_frac_req": float(getattr(args, 'mask_bad_frac', 0.0)),
            "mask_applied_count": int(masked_count),
        },
        "baseline": base_summary,
        "path_a": path_a_summary,
        "path_b": path_b_summary,
        "path_b_chain": path_b_chain,
        "path_b_sweeps": path_b_sweeps,
        "cold_input": cold_summary,
        "packs": {
            "emitter": emit.__dict__,
            "optics": optx.__dict__,
            "tia": tia.__dict__,
            "comparator": comp.__dict__,
            "clock": clk.__dict__,
        },
        "realism": realism_scores(),
        "components": components,
        "ber_per_tile": per_tile,
        "ber_per_tile_after": per_tile_after,
        "baseline_calibrated": (cal_summary or {}),
        "vote3_p50_ber": vote3_ber,
        "spatial_oversample_p50_ber": spatial_ber,
        "lockin_p50_ber": lockin_ber,
        "chop_p50_ber": chop_ber,
        "avg_frames_p50_ber": avg_frames_ber,
        "soft_thresh_p50_ber": soft_thresh_ber,
        "mitigated_p50_ber": mitigated_ber,
        "sanity": {
            "window_non_increasing": w_ok,
            "rin_non_decreasing": r_ok,
            "crosstalk_non_decreasing": c_ok,
        },
        "effects": effects,
        "window_sweep": {"x_window_ns": w_xs, "p50_ber": w_ys},
        "rin_sweep": {"x_rin_dbhz": r_xs, "p50_ber": r_ys},
        "crosstalk_sweep": {"x_crosstalk_db": c_xs, "p50_ber": c_ys},
        "calibration": {
            "vth_suggest_mV": vth_suggest,
            "ber_before": base_summary.get("p50_ber"),
            "ber_after": ber_after,
            "ber_delta": (None if (ber_after is None or base_summary.get("p50_ber") is None) else float(ber_after - base_summary.get("p50_ber")))
        }
    }

    # Optionally apply calibration to make calibrated KPIs the baseline
    if args.apply_calibration and cal_summary:
        summary["baseline_raw"] = summary["baseline"]
        summary["baseline"] = cal_summary

    # Sensitivity block (skip entirely in light-output mode)
    if not getattr(args, 'light_output', False):
        sens_tia_bw = 30.0
        sens_comp_noise = 0.3
        sens_windows = [3, 6, 10, 15, 20, 30]
        sens_rin = (-170.0, -130.0, 9)
        sens_ct = (-40.0, -15.0, 9)
        sens_emit = EmitterParams(channels=sys_p.channels, power_mw_per_ch=0.05, modulation_mode="pushpull", pushpull_alpha=0.9)
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
        # Diagonal crosstalk sweep
        dct_range = (-45.0, -20.0, 6)
        sd_xs, sd_ys, sd_ok = quick_diag_ct_sweep(
            sys_p,
            trials=args.trials,
            starts=dct_range[0],
            stops=dct_range[1],
            steps=dct_range[2],
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
            "diag_crosstalk_sweep": {"x_ct_diag_db": sd_xs, "p50_ber": sd_ys},
        }
        # Optional: Per-tile heatmap in sensitivity mode if tiling is square (blocks^2 == channels)
        try:
            from looking_glass.plotting import save_heatmap
            _one = sens_orch.step()
            if _one.get("per_tile", {}).get("plus") is not None:
                save_heatmap(_one["per_tile"]["plus"], xlabel="tile-x", ylabel="tile-y", out_path="out/per_tile_plus.png", title="Per-tile Plus Intensity")
                save_heatmap(_one["per_tile"]["minus"], xlabel="tile-x", ylabel="tile-y", out_path="out/per_tile_minus.png", title="Per-tile Minus Intensity")
        except (ImportError, RuntimeError, ValueError):
            pass
    else:
        summary["sensitivity"] = None

    # Drift calibration demo (skip in light mode): BER vs time with/without periodic vth re-centering
    try:
        if getattr(args, 'light_output', False) or getattr(args, 'no_drift', False) or getattr(args, 'fast', False):
            raise RuntimeError('skip drift in light output')
        import numpy as _np
        from looking_glass.sim.thermal import ThermalParams as _Therm
        drift_frames = 600
        chunk = 30
        # No calibration
        orch_drift = Orchestrator(
            sys_p,
            EmitterParams(channels=sys_p.channels, power_mw_per_ch=0.7),
            OpticsParams(),
            PDParams(),
            TIAParams(bw_mhz=tia_bw, tia_transimpedance_kohm=5.0),
            ComparatorParams(input_noise_mV_rms=comp_noise),
            ClockParams(window_ns=10.0, jitter_ps_rms=10.0),
            cam_p=None,
            thermal_p=_Therm(drift_scale=0.05, corner_hz=0.01),
        )
        ber_no = []
        xs_no = []
        tmp = []
        for i in range(drift_frames):
            tmp.append(orch_drift.step()["ber"])
            if (i+1) % chunk == 0:
                ber_no.append(float(_np.median(tmp))); xs_no.append(i+1); tmp = []
        # With periodic re-centering
        orch_fix = Orchestrator(
            sys_p,
            EmitterParams(channels=sys_p.channels, power_mw_per_ch=0.7),
            OpticsParams(),
            PDParams(),
            TIAParams(bw_mhz=tia_bw, tia_transimpedance_kohm=5.0),
            ComparatorParams(input_noise_mV_rms=comp_noise),
            ClockParams(window_ns=10.0, jitter_ps_rms=10.0),
            cam_p=None,
            thermal_p=_Therm(drift_scale=0.05, corner_hz=0.01),
        )
        ber_fix = []
        xs_fix = []
        tmp = []
        calib_interval = 5  # chunks
        for i in range(drift_frames):
            tmp.append(orch_fix.step()["ber"])
            if (i+1) % chunk == 0:
                k = (i+1)//chunk
                # periodic re-centering using last chunk's dv
                rows = [orch_fix.step() for _ in range(100)]
                dv = _np.array([r.get("dv_mV", [0]*sys_p.channels) for r in rows])
                truth = _np.array([r.get("truth", [0]*sys_p.channels) for r in rows])
                pos_mean = _np.mean(_np.where(truth>0, dv, _np.nan), axis=0)
                neg_mean = _np.mean(_np.where(truth<0, dv, _np.nan), axis=0)
                vth_vec = _np.nan_to_num(0.5*(pos_mean + neg_mean))
                orch_fix.comp.set_vth_per_channel(vth_vec)
                ber_fix.append(float(_np.median(tmp))); xs_fix.append(i+1); tmp = []
        summary["drift"] = {
            "no_cal": {"x_frame": xs_no, "p50_ber": ber_no},
            "with_cal": {"x_frame": xs_fix, "p50_ber": ber_fix},
        }
    except Exception:
        pass

    # Autotuner (optional)
    if args.autotune:
        from looking_glass.tuner import auto_tune
        if args.progress:
            print("PROGRESS: autotune start")
        # Build tuning constraints from packs if provided
        constraints = {}
        def _merge_constraints(prefix: str, pack: dict | None):
            if not pack: return
            t = pack.get('tuning') or {}
            allowed = t.get('allowed_params') or []
            for item in allowed:
                # item like {'comparator.hysteresis_mV': {min:.., max:..}} or {'tia.bw_mhz': {choices:[..]}}
                for k, v in item.items():
                    if isinstance(k, str) and isinstance(v, dict):
                        if '.' in k:
                            comp, param = k.split('.', 1)
                            constraints[(comp, param)] = v
        _merge_constraints('emitter', emit_override)
        _merge_constraints('optics', optx_override)
        _merge_constraints('sensor', pd_override)
        _merge_constraints('tia', tia_override)
        _merge_constraints('comparator', comp_override)
        _merge_constraints('clock', clk_override)
        # Optional locks: keep optics neighbor/diag CT fixed at initial values
        try:
            if getattr(args, 'lock_optics_ct', False) and getattr(optx, 'ct_model', 'global') == 'neighbor':
                if getattr(optx, 'ct_neighbor_db', None) is not None:
                    constraints[("optics", "ct_neighbor_db")] = {"min": float(optx.ct_neighbor_db), "max": float(optx.ct_neighbor_db)}
                if getattr(optx, 'ct_diag_db', None) is not None:
                    constraints[("optics", "ct_diag_db")] = {"min": float(optx.ct_diag_db), "max": float(optx.ct_diag_db)}
        except Exception:
            pass

        tune_res = auto_tune(
            sys_p,
            EmitterParams(**emit.__dict__),
            OpticsParams(**optx.__dict__),
            PDParams(**pd.__dict__),
            TIAParams(**tia.__dict__),
            ComparatorParams(**comp.__dict__),
            ClockParams(**clk.__dict__),
            trials=int(args.autotune_trials),
            budget=int(args.autotune_budget),
            seed=int(args.seed),
            use_calibration=True,
            constraints=constraints,
        )
        summary["autotune"] = tune_res
        if args.progress:
            print("PROGRESS: autotune done")
        # Optional: re-evaluate path_a with tuned params
        try:
            if getattr(args, 'apply_autotuned_params', False):
                best = (tune_res.get("params") or {})
                def _apply(dobj, key):
                    upd = (best.get(key) or {})
                    if not isinstance(upd, dict):
                        return dobj
                    # keep only attributes that exist on the dataclass
                    filt = {k: v for k, v in upd.items() if hasattr(dobj, k)}
                    return replace(dobj, **filt) if filt else dobj
                sys_t = _apply(sys_p, "system")
                emit_t = _apply(EmitterParams(**emit.__dict__), "emitter")
                optx_t = _apply(OpticsParams(**optx.__dict__), "optics")
                pd_t = _apply(PDParams(**pd.__dict__), "sensor")
                tia_t = _apply(TIAParams(**tia.__dict__), "tia")
                comp_t = _apply(ComparatorParams(**comp.__dict__), "comparator")
                clk_t = _apply(ClockParams(**clk.__dict__), "clock")
                orch_t = Orchestrator(sys_t, emit_t, optx_t, pd_t, tia_t, comp_t, clk_t)
                if args.adaptive_input:
                    import numpy as _np
                    errs = []
                    T = int(args.trials)
                    maxN = max(1, int(args.adaptive_max_frames))
                    margin = float(args.adaptive_margin_mV)
                    for _ in range(min(T, 400)):
                        tern = orch_t.rng.integers(-1, 2, size=orch_t.sys.channels)
                        acc = _np.zeros(orch_t.sys.channels, dtype=float)
                        for k in range(maxN):
                            r = orch_t.step(force_ternary=tern)
                            dv = _np.array(r.get("dv_mV", [0]*orch_t.sys.channels))
                            acc += dv
                            up_th = float(orch_t.comp.p.vth_mV) + 0.5*float(orch_t.comp.p.hysteresis_mV)
                            if _np.all(_np.abs(acc) >= (up_th + margin)):
                                break
                        pred = _np.sign(acc)
                        errs.append(float(_np.mean(pred != tern)))
                    path_a_auto = {
                        "p50_ber": float(_np.median(errs)) if errs else None,
                        "p50_energy_pj": None,
                        "window_ns": float(orch_t.clk.p.window_ns),
                    }
                else:
                    path_a_auto = orch_t.run(trials=args.trials)
                # Add mean_ber for tuned as well
                try:
                    _rows_at = run_trials(orch_t, min(args.trials, 200))
                    path_a_auto["mean_ber"] = mean_ber(_rows_at)
                except Exception:
                    pass
                summary["path_a_autotuned"] = path_a_auto
                try:
                    if getattr(args, 'use_autotuned_as_primary', False):
                        summary["path_a"] = path_a_auto
                except Exception:
                    pass
        except Exception:
            pass
    if not args.quiet:
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

