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
    ap.add_argument("--mask-mode", type=str, choices=["error","dvspan"], default="error", help="Mask criterion: error (default) or dvspan (use |pos_mean-neg_mean|)")
    ap.add_argument("--spatial-oversample", type=int, default=1, help="Pseudo spatial oversampling vote (runs per input)")
    ap.add_argument("--lockin", action="store_true", help="Estimate lock-in subtraction by subtracting a dark frame dv")
    ap.add_argument("--chop", action="store_true", help="Chopper stabilization: use +x and -x frames, subtract dv before threshold")
    ap.add_argument("--avg-frames", type=int, default=1, help="Average dv over N frames per input before thresholding (noise ~ 1/sqrt(N))")
    ap.add_argument("--avg-kernel", type=str, choices=["sum", "ewma"], default="sum", help="Averaging kernel for dv over frames: sum or ewma")
    # Simple spatial deblurring (neighbor deconvolution)
    ap.add_argument("--deblur-neigh-alpha", type=float, default=0.0, help="Neighbor deblurring strength alpha; dv' = dv - alpha*(left+right)")
    ap.add_argument("--learn-deblur", action="store_true", help="Learn per-channel neighbor deblur weights (left/right) from calibration dv")
    ap.add_argument("--deblur-l2", type=float, default=0.1, help="Ridge penalty for learned deblur weights")
    ap.add_argument("--deblur-samples", type=int, default=240, help="Samples to gather for learned deblur weights")
    # Confidence gating (selective extra frames for low-margin channels)
    ap.add_argument("--gate-thresh-mV", type=float, default=0.0, help="If |dv| < thresh, take extra frames and add to dv before decision")
    ap.add_argument("--gate-extra-frames", type=int, default=0, help="Number of extra frames to integrate for gated channels")
    ap.add_argument("--avg-ema-alpha", type=float, default=0.6, help="EWMA alpha (0..1], only used when --avg-kernel=ewma")
    ap.add_argument("--use-avg-frames-for-path-a", action="store_true", help="If set and avg_frames>1, use averaged-dv classifier as primary path_a summary")
    ap.add_argument("--permute-repeats", action="store_true", help="Permute logical???physical channel mapping on each repeat and de-permute for voting")
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
    ap.add_argument("--path-b-servo-eta", type=float, default=0.05, help="Per-iteration comparator bias adjustment for analog Path B servo (mV per unit error)")
    ap.add_argument("--path-b-guard-deadzone-mV", type=float, default=0.0, help="Dead-zone (mV) for hybrid guard; if >0, enforces sign based on dv with zeros inside dead-zone")
    ap.add_argument("--path-b-guard-gain-mW", type=float, default=0.05, help="Guard injection gain (mW) added symmetrically to the optical rails when guard is active")
    ap.add_argument("--path-b-digital-guard", action="store_true", help="Apply digital sign guard after the analog cascade")
    ap.add_argument("--path-b-digital-deadzone-mV", type=float, default=0.1, help="Dead-zone (mV) for the digital guard accumulator; values within the band map to 0")
    ap.add_argument("--path-b-digital-guard-passes", type=int, default=3, help="Number of analog replays to average before applying the digital guard")
    ap.add_argument("--path-b-return-map", action="store_true", help="Record Path B return map (dv in/out, slopes, histograms)")
    ap.add_argument("--path-b-balanced", action="store_true", help="Use balanced photodiode/TIA path for Path B calculations")
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
    ap.add_argument("--vth-inline", type=str, default=None, help="Comma-separated per-channel vth (mV) to apply (overrides import)")
    ap.add_argument("--vth-scale", type=float, default=1.0, help="Scale factor applied to per-channel vth vector before use")
    ap.add_argument("--vth-bias-mV", type=float, default=0.0, help="Bias (mV) added to per-channel vth vector before use")
    ap.add_argument("--use-linear-calibration", action="store_true", help="Apply per-channel linear dv correction learned during calibration to classifiers")
    ap.add_argument("--force-cal-in-primary", action="store_true", help="Use calibrated dv_lin and vth in primary classifier decisions when available")
    ap.add_argument("--smooth-calibration", action="store_true", help="Spatially smooth per-channel vth/offset/scale with neighbor averaging")
    ap.add_argument("--calib-samples", type=int, default=0, help="Override number of calibration samples (0 = heuristic)")
    # Legacy calibration compatibility toggles
    ap.add_argument("--legacy-baseline-cal", action="store_true", help="Use legacy-style baseline calibration (no smoothing/deblur; comparator hyst=1.0, vth_sigma=0; no normalize in cal)")
    ap.add_argument("--legacy-cal-no-normalize", action="store_true", help="Disable dv normalization during baseline calibration only")
    ap.add_argument("--use-map-thresh", action="store_true", help="Use Gaussian MAP decision with comparator sigma on dv_lin vs vth")
    ap.add_argument("--fuse-decoder", action="store_true", help="Fuse calibrated score with decoder score for final decision")
    ap.add_argument("--fuse-alpha", type=float, default=0.8, help="Fusion weight alpha for calibrated score (0..1)")
    # Per-channel linear optimizer (adjusts lin_offset per channel)
    ap.add_argument("--optimize-linear", action="store_true", help="Greedy coordinate updates to per-channel dv linear offset to reduce BER on a small fixed set")
    ap.add_argument("--opt-lin-iters", type=int, default=6, help="Linear optimizer iterations")
    ap.add_argument("--opt-lin-step-mV", type=float, default=0.1, help="Per-iteration linear offset step (mV)")
    ap.add_argument("--opt-lin-use-mask", action="store_true", help="Restrict linear optimizer to unmasked channels")
    # Simple linear decoder (per-channel linear classifier on dv and neighbors)
    ap.add_argument("--decoder-linear", action="store_true", help="Train a per-channel linear decoder on dv features and use it for decisions")
    ap.add_argument("--decoder-l2", type=float, default=0.1, help="Ridge regularization for decoder training")
    ap.add_argument("--decoder-samples", type=int, default=320, help="Samples used to train decoder")
    ap.add_argument("--use-decoder-for-path-a", action="store_true", help="Use decoder as primary classifier for path_a summary")
    # MLP decoder
    ap.add_argument("--decoder-mlp", action="store_true", help="Train a tiny MLP decoder on dv features and use it for decisions")
    ap.add_argument("--decoder-mlp-hidden", type=int, default=8, help="Hidden units for MLP decoder")
    ap.add_argument("--decoder-mlp-epochs", type=int, default=10, help="Training epochs for MLP decoder")
    ap.add_argument("--decoder-mlp-lr", type=float, default=0.01, help="Learning rate for MLP decoder")
    # Simple ECC (single parity correction within blocks)
    ap.add_argument("--use-ecc", action="store_true", help="Apply single-parity correction within fixed-size channel blocks to decoder outputs")
    ap.add_argument("--ecc-spc-block", type=int, default=4, help="Block size for single-parity correction")
    # Software autotune (decoder/deblur/gating/mask)
    ap.add_argument("--soft-autotune", action="store_true", help="Autotune software params (decoder/deblur/gating/mask/avg/window) and select best")
    ap.add_argument("--soft-budget", type=int, default=60, help="Number of configurations to evaluate in software autotune")
    # Lightweight local autotuner for window/mask/avg
    ap.add_argument("--local-autotune", action="store_true", help="Run a local search over window/mask/avg and report best path_a")
    ap.add_argument("--la-windows", type=str, default="18,19,20,21", help="Comma-separated window ns for local autotune")
    ap.add_argument("--la-mask-fracs", type=str, default="0.0625,0.09375,0.125", help="Comma-separated mask fractions for local autotune")
    ap.add_argument("--la-avg-frames", type=str, default="2,3", help="Comma-separated avg-frames for local autotune")
    # Comparator override knobs
    ap.add_argument("--comp-hysteresis-mV", type=float, default=None, help="Override comparator hysteresis (mV)")
    ap.add_argument("--comp-input-noise-mV", type=float, default=None, help="Override comparator input noise RMS (mV)")
    ap.add_argument("--comp-vth-mV", type=float, default=None, help="Override comparator base vth (mV)")
    ap.add_argument("--comp-vth-sigma-mV", type=float, default=None, help="Override comparator vth sigma (mV)")
    # Per-channel vth optimizer
    ap.add_argument("--optimize-vth", action="store_true", help="Iteratively adjust per-channel vth to reduce classification errors on a small fixed set")
    ap.add_argument("--opt-vth-iters", type=int, default=6, help="Optimizer iterations")
    ap.add_argument("--opt-vth-step-mV", type=float, default=0.2, help="Per-iteration vth step size (mV)")
    ap.add_argument("--opt-vth-margin-mV", type=float, default=0.0, help="Optional margin when deciding errors for optimizer")
    ap.add_argument("--opt-vth-use-mask", action="store_true", help="Restrict vth optimization to unmasked channels (ignore masked)")
    ap.add_argument("--legacy-cal-estimator-soft", action="store_true", help="Compute baseline_calibrated via dv sign vs vth (no comparator deadband)")
    ap.add_argument("--baseline-cal-binary", action="store_true", help="Evaluate calibrated baseline with ??1 truths only (no zeros)")
    args = ap.parse_args()
    # Defaults to run full non-destructive suite
    run_path_b_sweep = (not getattr(args, 'no_path_b_sweep', False)) or getattr(args, 'path_b_sweep', False)
    args.path_b_sweep = bool(run_path_b_sweep)
    if not getattr(args, 'no_adaptive_input', False):
        args.adaptive_input = True

    # Base system from typ packs inline
    sys_p = SystemParams(channels=int(args.channels), window_ns=float(args.base_window_ns), temp_C=25.0, seed=args.seed,
                         normalize_dv=bool(getattr(args, 'normalize_dv', False)),
                         normalize_eps_v=float(getattr(args, 'normalize_eps_v', 1e-6)),
                         balanced_pd=bool(getattr(args, 'path_b_balanced', False)))
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
    # Map common vendor-pack fields ??? sim params
    try:
        if isinstance(optx_override, dict):
            if 'transmittance_percent' in optx_override:
                tp = float(optx_override['transmittance_percent'])
                optx.transmittance = max(0.0, min(1.0, tp/100.0))
            if 'scatter_angle_deg_FWHM' in optx_override:
                ang = float(optx_override['scatter_angle_deg_FWHM'])
                # Heuristic: wider scatter ??? higher neighbor leakage (less negative dB)
                neigh = -40.0 + (ang - 5.0) * (10.0 / 15.0)  # 5?????-40dB, 20?????-30dB
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
    # Apply comparator CLI overrides if provided
    try:
        if getattr(args, 'comp_hysteresis_mV', None) is not None:
            comp.hysteresis_mV = float(args.comp_hysteresis_mV)
        if getattr(args, 'comp_input_noise_mV', None) is not None:
            comp.input_noise_mV_rms = float(args.comp_input_noise_mV)
        if getattr(args, 'comp_vth_mV', None) is not None:
            comp.vth_mV = float(args.comp_vth_mV)
        if getattr(args, 'comp_vth_sigma_mV', None) is not None:
            comp.vth_sigma_mV = float(args.comp_vth_sigma_mV)
    except Exception:
        pass

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
    deblur_params = {"aL": None, "aR": None}

    # Helper: approximate Gaussian MAP probability using logistic approximation
    def _map_prob_from_dv(dv_lin_vec, vth_vec, sigma_mV):
        import numpy as _np
        s = float(max(1e-6, sigma_mV))
        z = (dv_lin_vec - (vth_vec if vth_vec is not None else 0.0)) / s
        k = 1.8137993642342178  # pi/sqrt(3)
        return 1.0 / (1.0 + _np.exp(-k * z))

    # Helper: compute decoder probability P(+1) given features
    def _decoder_prob_from_feats(feats, dec):
        import numpy as _np
        if dec is None:
            return None
        if bool(dec.get("mlp")):
            Z1 = feats @ dec["W1"] + dec["b1"]
            A1 = _np.tanh(Z1)
            Z2 = A1 @ dec["W2"] + dec["b2"]
            return 1.0 / (1.0 + _np.exp(-Z2.reshape(-1)))
        w = dec.get("w")
        if w is None:
            return None
        score = feats @ w
        return 1.0 / (1.0 + _np.exp(-score))

    # Helper: fuse two probabilities
    def _fuse_probs(p_cal, p_dec, alpha):
        import numpy as _np
        if p_cal is None:
            return p_dec
        if p_dec is None:
            return p_cal
        a = float(_np.clip(alpha, 0.0, 1.0))
        return a * p_cal + (1.0 - a) * p_dec

    # Helper: single-parity correction within blocks; assumes last bit in block is parity
    def _apply_spc(pred_pm1, prob_pos, block_size):
        import numpy as _np
        B = int(max(2, block_size))
        pred_bin = (_np.asarray(pred_pm1, dtype=int) > 0).astype(int)
        out = pred_bin.copy()
        probs = _np.asarray(prob_pos, dtype=float)
        M = pred_bin.shape[0]
        for i in range(0, M, B):
            j = min(M, i + B)
            if (j - i) < B:
                continue
            blk = pred_bin[i:j]
            # expected parity: XOR of first B-1 equals last bit
            exp_par = 0
            if B > 1:
                exp_par = int(_np.bitwise_xor.reduce(blk[:-1]))
            if exp_par != blk[-1]:
                conf = _np.abs(probs[i:j] - 0.5)
                k = int(_np.argmin(conf))
                out[i + k] = 1 - out[i + k]
        return _np.where(out > 0, 1, -1).astype(int)

    def _accumulate_dv_over_frames(_orch, _tern, _N: int, _kernel: str, _alpha: float):
        import numpy as _np
        acc = None
        for _j in range(max(1, int(_N))):
            r = _orch.step(force_ternary=_tern)
            dv = _np.array(r.get("dv_mV", [0]*_orch.sys.channels))
            # Deblur with learned taps if available
            if deblur_params.get("aL") is not None and dv.size > 1:
                l = _np.roll(dv, 1); rr = _np.roll(dv, -1)
                dv = dv - deblur_params["aL"]*l - deblur_params["aR"]*rr
            # Deblur with fixed neighbor taps if enabled
            if float(_alpha) > 0.0 and dv.size > 1:
                dv_l = _np.roll(dv, 1); dv_r = _np.roll(dv, -1)
                dv = dv - float(_alpha)*(dv_l + dv_r)
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
    # Hoist placeholder for per-channel threshold vector used in primary classifiers
    vth_vec_pa = None
    # Optional: import per-channel vth (mV) and apply to primary and baseline comparators
    try:
        imp_path = getattr(args, 'import_vth', None)
        inline = getattr(args, 'vth_inline', None)
        import numpy as _np
        vec = None
        if isinstance(inline, str) and inline:
            parts = [p.strip() for p in inline.split(',') if p.strip()]
            if parts:
                vec = _np.asarray([float(p) for p in parts], dtype=float)
        elif isinstance(imp_path, str) and imp_path:
            import json as _json, pathlib as _pathlib
            arr = _json.loads(_pathlib.Path(imp_path).read_text(encoding="utf-8"))
            vec = _np.asarray(arr, dtype=float)
        # Apply vector if provided
        if vec is not None:
            # Optional global scale/bias on per-channel vth
            try:
                s = float(getattr(args, 'vth_scale', 1.0)); b = float(getattr(args, 'vth_bias_mV', 0.0))
                vec = s*vec + b
            except Exception:
                pass
            orch.comp.set_vth_per_channel(vec)
            try:
                base_orch.comp.set_vth_per_channel(vec)
            except Exception:
                pass
    except Exception:
        pass
    # Apply per-channel vth from comparator pack if provided (key: vth_per_channel_mV)
    try:
        if isinstance(comp_override, dict) and isinstance(comp_override.get('vth_per_channel_mV'), list):
            import numpy as _np
            v = _np.asarray(comp_override.get('vth_per_channel_mV'), dtype=float)
            orch.comp.set_vth_per_channel(v)
            try:
                base_orch.comp.set_vth_per_channel(v)
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
        b_optx.channels = int(args.channels)
        b_optx.sat_abs_on = False
        b_optx.amp_on = False
        b_optx.soa_on = True
        b_optx.mzi_on = True
        b_pd = PDParams(**pd.__dict__)
        b_tia = TIAParams(**tia.__dict__)
        b_comp = ComparatorParams(**comp.__dict__)
        b_clk = ClockParams(**clk.__dict__)
        b_orch = Orchestrator(sys_p, b_emit, b_optx, b_pd, b_tia, b_comp, b_clk)
        if int(getattr(args, 'path_b_analog_depth', 0)) > 0 or int(getattr(args, 'path_b_depth', 0)) > 0:
            try:
                b_orch.sys.reset_analog_state_each_frame = False
            except AttributeError:
                pass
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
            vth_vec = _np.zeros(b_orch.sys.channels, dtype=float)
            eta = float(getattr(args, 'path_b_servo_eta', 0.05))
            guard_deadzone = float(getattr(args, 'path_b_guard_deadzone_mV', 0.0))
            guard_gain = float(getattr(args, 'path_b_guard_gain_mW', 0.05))
            use_digital_guard = bool(getattr(args, 'path_b_digital_guard', False))
            balanced_pd = bool(getattr(args, 'path_b_balanced', False))
            digital_deadzone = float(getattr(args, 'path_b_digital_deadzone_mV', 0.1))
            guard_passes = max(1, int(getattr(args, 'path_b_digital_guard_passes', 3)) if use_digital_guard else 1)
            for _ in range(T):
                tern0 = b_orch.rng.integers(-1, 2, size=b_orch.sys.channels)
                dv_samples = []
                out_samples = []
                for rep in range(guard_passes):
                    dt = float(b_orch.clk.sample_window())
                    if b_orch.sys.reset_analog_state_each_frame:
                        b_orch.tia.reset()
                        b_orch.comp.reset()
                    Pp, Pm = b_orch.emit.simulate(tern0, dt, b_orch.sys.temp_C)
                    for _k in range(analog_depth):
                        Pp, Pm, _, _ = b_orch.optx.simulate(Pp, Pm, dt)
                    if guard_gain > 0.0:
                        diff_opt = Pp - Pm
                        adjust = guard_gain * _np.sign(diff_opt)
                        if guard_deadzone > 0.0:
                            adjust[_np.abs(diff_opt) < guard_deadzone] = 0.0
                        Pp = _np.clip(Pp + 0.5 * adjust, 0.0, None)
                        Pm = _np.clip(Pm - 0.5 * adjust, 0.0, None)
                    Ip = b_orch.pd.simulate(Pp, dt)
                    Im = b_orch.pd.simulate(Pm, dt)
                    if balanced_pd:
                        diff_current = Ip - Im
                        Ip = diff_current
                        Im = -diff_current
                    Vp = b_orch.tia.simulate(Ip, dt)
                    Vm = b_orch.tia.simulate(Im, dt)
                    dv_final = (Vp - Vm) * 1e3
                    out = b_orch.comp.simulate(Vp, Vm, b_orch.sys.temp_C)
                    error = _np.asarray(out, dtype=float) - _np.asarray(tern0, dtype=float)
                    if eta > 0.0:
                        vth_vec = _np.clip(vth_vec + eta * error, -15.0, 15.0)
                        b_orch.comp.set_vth_per_channel(vth_vec)
                    dv_samples.append(dv_final)
                    out_samples.append(out)
                if use_digital_guard:
                    dv_mean = _np.mean(_np.stack(dv_samples), axis=0)
                    guard_out = _np.sign(dv_mean)
                    if digital_deadzone > 0.0:
                        guard_out[_np.abs(dv_mean) < digital_deadzone] = 0.0
                    out_arr = guard_out.astype(int)
                elif guard_gain > 0.0 or guard_deadzone > 0.0:
                    dv_last = dv_samples[-1]
                    guard_out = _np.sign(dv_last)
                    if guard_deadzone > 0.0:
                        guard_out[_np.abs(dv_last) < guard_deadzone] = 0.0
                    out_arr = guard_out.astype(int)
                else:
                    out_arr = _np.asarray(out_samples[-1], dtype=int)
                errs.append(float(_np.mean(out_arr != tern0)))
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
            # Here we approximate channel???tile as index // 1 (one channel per tile in current mapping)
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
            # Legacy calibration overrides
            if getattr(args, 'legacy_baseline_cal', False):
                try:
                    cal_comp.hysteresis_mV = 1.0
                    cal_comp.vth_sigma_mV = 0.0
                except Exception:
                    pass
            cal_clk = ClockParams(**clk.__dict__)
            # Build calibration orchestrator; optionally disable normalization only for calibration
            cal_sys = SystemParams(**sys_p.__dict__)
            if getattr(args, 'legacy_baseline_cal', False) or getattr(args, 'legacy_cal_no_normalize', False):
                try:
                    cal_sys.normalize_dv = False
                except Exception:
                    pass
            orch_cal = Orchestrator(cal_sys, cal_emit, cal_optx, cal_pd, cal_tia, cal_comp, cal_clk)
            # Gather dv per channel given known ternary patterns
            pos_sum = _np.zeros(sys_p.channels, dtype=float)
            pos_cnt = _np.zeros(sys_p.channels, dtype=float)
            neg_sum = _np.zeros(sys_p.channels, dtype=float)
            neg_cnt = _np.zeros(sys_p.channels, dtype=float)
            total_cal = int(min(args.trials*2, 400 if not getattr(args, 'fast', False) else 120))
            if int(getattr(args, 'calib_samples', 0)) > 0:
                total_cal = int(getattr(args, 'calib_samples'))
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
            # Linear per-channel calibration: scale/offset dv so classes map to ??1
            eps = 1e-6
            lin_scale = 2.0/_np.clip((pos_mean - neg_mean), eps, None)
            lin_offset = -0.5*(pos_mean + neg_mean)
            # Optional smoothing (skip if legacy baseline cal)
            try:
                if getattr(args, 'smooth_calibration', False) and not getattr(args, 'legacy_baseline_cal', False):
                    def _smooth(vec):
                        L = _np.roll(vec, 1); R = _np.roll(vec, -1)
                        return 0.25*L + 0.5*vec + 0.25*R
                    vth_vec = _smooth(vth_vec)
                    lin_scale = _smooth(lin_scale)
                    lin_offset = _smooth(lin_offset)
            except Exception:
                pass
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
            # Always compute canonical baseline via comparator pipeline
            cal_summary = orch_cal.run(trials=args.trials)
            # Optionally compute alternate estimators without overriding canonical baseline
            if getattr(args, 'legacy_cal_estimator_soft', False):
                errs_soft = []
                for _ in range(min(args.trials, 400)):
                    tern = orch_cal.rng.integers(-1, 2, size=orch_cal.sys.channels)
                    r = orch_cal.step(force_ternary=tern)
                    dv = _np.array(r.get("dv_mV", [0]*orch_cal.sys.channels), dtype=float)
                    pred = _np.where((dv - vth_vec) >= 0.0, 1, -1)
                    errs_soft.append(float(_np.mean(pred != tern)))
                cal_summary_alt_soft = {"p50_ber": float(_np.median(errs_soft)) if errs_soft else None, "window_ns": float(orch_cal.clk.p.window_ns)}
            else:
                cal_summary_alt_soft = None
            if getattr(args, 'baseline_cal_binary', False):
                errs_bin = []
                for _ in range(min(args.trials, 400)):
                    tern = orch_cal.rng.choice([-1, 1], size=orch_cal.sys.channels)
                    r = orch_cal.step(force_ternary=tern)
                    tout = _np.array(r.get("t_out", [0]*orch_cal.sys.channels), dtype=int)
                    errs_bin.append(float(_np.mean(tout != tern)))
                cal_summary_alt_bin = {"p50_ber": float(_np.median(errs_bin)) if errs_bin else None, "window_ns": float(orch_cal.clk.p.window_ns)}
            else:
                cal_summary_alt_bin = None
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
    # Initialize optional calibration outputs in case calibration block fails
    cal_summary_alt_soft = None
    cal_summary_alt_bin = None
    per_tile_after = None
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

    # Realism heuristic scoring (0.0???1.0)
    def realism_scores():
        scores = {}
        # Emitter: extinction, RIN in plausible range
        rin = float(emit.rin_dbhz if hasattr(emit, 'rin_dbhz') else -150.0)
        ext = float(emit.extinction_db if hasattr(emit, 'extinction_db') else 20.0)
        s_rin = min(1.0, max(0.0, (rin + 180.0) / 30.0))  # -180..-150 ??? 0..1, flatter above
        s_ext = min(1.0, max(0.0, (ext - 10.0) / 20.0))   # 10..30 dB ??? 0..1
        scores["emitter"] = {"score": round(0.6*s_rin + 0.4*s_ext, 3), "rin_dbhz": rin, "extinction_db": ext}
        # Optics: crosstalk and stray floor
        ct = float(optx.crosstalk_db if hasattr(optx, 'crosstalk_db') else -28.0)
        stray = float(optx.stray_floor_db if hasattr(optx, 'stray_floor_db') else -38.0)
        s_ct = min(1.0, max(0.0, (-ct - 18.0) / 20.0))    # -38..-18 ??? 1..0
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

    # Build bad-channel mask BEFORE classifier evaluation so it is applied
    active_mask = None
    masked_count = 0
    try:
        Nmask = int(max(int(getattr(args, 'mask_bad_channels', 0)), float(getattr(args, 'mask_bad_frac', 0.0)) * float(sys_p.channels)))
        if Nmask > 0:
            import numpy as _np
            trials_mask = int(max(50, min(getattr(args, 'calib_mask_trials', 200), 500)))
            ch = sys_p.channels
            err_counts = None
            pos_sum = _np.zeros(ch, dtype=float)
            pos_cnt = _np.zeros(ch, dtype=float)
            neg_sum = _np.zeros(ch, dtype=float)
            neg_cnt = _np.zeros(ch, dtype=float)
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
                dv_cur = _np.array(r.get("dv_mV", [0]*tout.shape[0]), dtype=float)
                pos = tern > 0; neg = tern < 0
                pos_sum[:dv_cur.shape[0]][pos[:dv_cur.shape[0]]] += dv_cur[pos[:dv_cur.shape[0]]]
                pos_cnt[:dv_cur.shape[0]][pos[:dv_cur.shape[0]]] += 1.0
                neg_sum[:dv_cur.shape[0]][neg[:dv_cur.shape[0]]] += dv_cur[neg[:dv_cur.shape[0]]]
                neg_cnt[:dv_cur.shape[0]][neg[:dv_cur.shape[0]]] += 1.0
            mode = (getattr(args, 'mask_mode', 'error') or 'error')
            if mode == 'dvspan':
                with _np.errstate(divide='ignore', invalid='ignore'):
                    pos_mean = _np.divide(pos_sum, _np.clip(pos_cnt, 1.0, None))
                    neg_mean = _np.divide(neg_sum, _np.clip(neg_cnt, 1.0, None))
                    span = _np.abs(pos_mean - neg_mean)
                idx = _np.argsort(span)[:min(Nmask, span.shape[0])]
            else:
                rates = err_counts / float(max(1, trials_mask))
                idx = _np.argsort(rates)[::-1][:min(Nmask, rates.shape[0])]
            active_mask = _np.ones_like(rates, dtype=bool)
            active_mask[idx] = False
            try:
                masked_count = int((_np.asarray(active_mask) == False).sum())
            except Exception:
                masked_count = int(Nmask)
    except Exception:
        active_mask = None

    def _mask_and_trim(pred_vec, truth_vec):
        import numpy as _np
        M = min(len(pred_vec), len(truth_vec))
        pred = _np.asarray(pred_vec[:M], dtype=int)
        truth = _np.asarray(truth_vec[:M], dtype=int)
        if active_mask is not None:
            mask = _np.asarray(active_mask[:M], dtype=bool)
            pred = pred[mask]
            truth = truth[mask]
        return pred, truth

    def _masked_error(pred_vec, truth_vec):
        import numpy as _np
        pred, truth = _mask_and_trim(pred_vec, truth_vec)
        if truth.size == 0:
            return 0.0
        return float(_np.mean(pred != truth))

    # Lock-in estimate: subtract a dark dv per trial and threshold on sign
    lockin_ber = None
    if args.lockin or (getattr(args, 'classifier', None) == 'lockin'):
        import numpy as _np
        errs = []
        for _ in range(min(args.trials, 200)):
            tern = base_orch.rng.integers(-1, 2, size=base_orch.sys.channels)
            r_sig = base_orch.step(force_ternary=tern)
            r_dark = base_orch.step(force_ternary=_np.zeros_like(tern))
            dv_sig = _np.array(r_sig.get("dv_mV", [0]*base_orch.sys.channels))
            dv_dark = _np.array(r_dark.get("dv_mV", [0]*base_orch.sys.channels))
            dv_diff = dv_sig - dv_dark
            if bool(getattr(args, 'force_cal_in_primary', False)) and (lin_scale is not None) and (lin_offset is not None):
                dv_lin = lin_scale*(dv_diff + lin_offset)
                if vth_vec_pa is not None:
                    pred = _np.sign(dv_lin - vth_vec_pa)
                else:
                    pred = _np.sign(dv_lin)
            else:
                # Optional confidence gating even without calibration
                g_th = float(getattr(args, 'gate_thresh_mV', 0.0)); g_ex = int(getattr(args, 'gate_extra_frames', 0))
                if g_ex > 0 and g_th > 0.0:
                    import numpy as _np
                    ref = (vth_vec_pa if vth_vec_pa is not None else 0.0)
                    low = _np.abs(dv_diff - ref) < g_th
                    if low.any():
                        r_sig2 = base_orch.step(force_ternary=tern)
                        r_dark2 = base_orch.step(force_ternary=_np.zeros_like(tern))
                        dv_sig2 = _np.array(r_sig2.get("dv_mV", [0]*base_orch.sys.channels))
                        dv_dark2 = _np.array(r_dark2.get("dv_mV", [0]*base_orch.sys.channels))
                        dv_diff2 = dv_sig2 - dv_dark2
                        dv_diff[low] = dv_diff[low] + dv_diff2[low]
                pred = _np.sign(dv_diff)
            errs.append(_masked_error(pred, tern))
        lockin_ber = float(_np.median(errs)) if errs else None

    # Chopper stabilization: use +x and -x frames, subtract, then threshold
    chop_ber = None
    if args.chop or (getattr(args, 'classifier', None) == 'chop'):
        import numpy as _np
        errs = []
        for _ in range(min(args.trials, 200)):
            tern = base_orch.rng.integers(-1, 2, size=base_orch.sys.channels)
            r_pos = base_orch.step(force_ternary=tern)
            r_neg = base_orch.step(force_ternary=-tern)
            dv_pos = _np.array(r_pos.get("dv_mV", [0]*base_orch.sys.channels))
            dv_neg = _np.array(r_neg.get("dv_mV", [0]*base_orch.sys.channels))
            dv_diff = dv_pos - dv_neg
            if bool(getattr(args, 'force_cal_in_primary', False)) and (lin_scale is not None) and (lin_offset is not None):
                dv_lin = lin_scale*(dv_diff + lin_offset)
                # confidence gate: one extra frame for small margins
                g_th = float(getattr(args, 'gate_thresh_mV', 0.0)); g_ex = int(getattr(args, 'gate_extra_frames', 0))
                if g_ex > 0 and g_th > 0.0:
                    low = _np.abs(dv_lin - (vth_vec_pa if vth_vec_pa is not None else 0.0)) < g_th
                    if low.any():
                        r_pos2 = base_orch.step(force_ternary=tern)
                        r_neg2 = base_orch.step(force_ternary=-tern)
                        dv_pos2 = _np.array(r_pos2.get("dv_mV", [0]*base_orch.sys.channels)); dv_neg2 = _np.array(r_neg2.get("dv_mV", [0]*base_orch.sys.channels))
                        dv_lin2 = lin_scale*((dv_pos2 - dv_neg2) + lin_offset)
                        dv_lin[low] = dv_lin[low] + dv_lin2[low]
                if vth_vec_pa is not None:
                    pred = _np.sign(dv_lin - vth_vec_pa)
                else:
                    pred = _np.sign(dv_lin)
            else:
                # Optional confidence gating even without calibration
                g_th = float(getattr(args, 'gate_thresh_mV', 0.0)); g_ex = int(getattr(args, 'gate_extra_frames', 0))
                if g_ex > 0 and g_th > 0.0:
                    import numpy as _np
                    ref = (vth_vec_pa if vth_vec_pa is not None else 0.0)
                    low = _np.abs(dv_diff - ref) < g_th
                    if low.any():
                        r_pos2 = base_orch.step(force_ternary=tern)
                        r_neg2 = base_orch.step(force_ternary=-tern)
                        dv_pos2 = _np.array(r_pos2.get("dv_mV", [0]*base_orch.sys.channels)); dv_neg2 = _np.array(r_neg2.get("dv_mV", [0]*base_orch.sys.channels))
                        dv_diff2 = dv_pos2 - dv_neg2
                        dv_diff[low] = dv_diff[low] + dv_diff2[low]
                pred = _np.sign(dv_diff)
            errs.append(_masked_error(pred, tern))
        chop_ber = float(_np.median(errs)) if errs else None

    # Frame averaging on dv: average N frames per input, then threshold
    avg_frames_ber = None
    if (int(args.avg_frames) > 1) or (getattr(args, 'classifier', None) == 'avg'):
        import numpy as _np
        N = int(args.avg_frames)
        errs = []
        for _ in range(min(args.trials, 200)):
            tern = base_orch.rng.integers(-1, 2, size=base_orch.sys.channels)
            acc = _accumulate_dv_over_frames(base_orch, tern, N, str(getattr(args, 'avg_kernel', 'sum')), float(getattr(args, 'avg_ema_alpha', 0.6)))
            # Confidence gating: add extra frames for low-margin channels
            g_th = float(getattr(args, 'gate_thresh_mV', 0.0)); g_ex = int(getattr(args, 'gate_extra_frames', 0))
            if g_ex > 0 and g_th > 0.0:
                low = _np.abs(acc) < g_th
                if low.any():
                    add = _accumulate_dv_over_frames(base_orch, tern, g_ex, str(getattr(args, 'avg_kernel', 'sum')), float(getattr(args, 'avg_ema_alpha', 0.6)))
                    acc[low] = acc[low] + add[low]
            pred = _np.sign(acc)
            errs.append(_masked_error(pred, tern))
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
            errs.append(_masked_error(pred, tern))
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
            errs.append(_masked_error(pred, tern))
        mitigated_ber = float(_np.median(errs)) if errs else None

    # Optional quick per-channel calibration to set vth for path_a/baseline even when --no-cal
    # Initialize masking and calibration vectors
    active_mask = None
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
            # Learn deblur taps per channel if requested (skip if legacy baseline cal)
            try:
                if getattr(args, 'learn_deblur', False) and not getattr(args, 'legacy_baseline_cal', False):
                    import numpy as _np
                    M = sys_p.channels
                    S = int(max(120, getattr(args, 'deblur_samples', 240)))
                    lam = float(getattr(args, 'deblur_l2', 0.1))
                    # Gather dv snapshots
                    D = _np.zeros((S, M), dtype=float)
                    for si in range(S):
                        rr = orch_cal.step()
                        D[si, :] = _np.array(rr.get("dv_mV", [0]*M), dtype=float)
                    # Build regression X (left,right), y=dv per channel solved independently with ridge
                    L = _np.roll(D, 1, axis=1); R = _np.roll(D, -1, axis=1)
                    # Solve (X^T X + lam I) w = X^T y where X=[L,R]
                    # Approximate shared taps across channels (global) for stability
                    X = _np.concatenate([L.reshape(-1,1), R.reshape(-1,1)], axis=1)
                    y = D.reshape(-1)
                    XT = X.T
                    A = XT @ X + lam*_np.eye(2)
                    b = XT @ y
                    w = _np.linalg.solve(A, b)
                    deblur_params["aL"], deblur_params["aR"] = float(w[0]), float(w[1])
            except Exception:
                pass
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

    # Optional per-channel vth optimizer (small fixed set, greedy updates)
    try:
        if getattr(args, 'optimize_vth', False):
            import numpy as _np
            K = int(max(1, getattr(args, 'opt_vth_iters', 6)))
            step = float(getattr(args, 'opt_vth_step_mV', 0.2))
            margin = float(getattr(args, 'opt_vth_margin_mV', 0.0))
            use_mask = bool(getattr(args, 'opt_vth_use_mask', False))
            # Initialize from current suggestion if available
            if vth_vec_pa is None:
                # derive quick vth vector from a short calibration set
                pos_sum = _np.zeros(orch.sys.channels, dtype=float)
                pos_cnt = _np.zeros(orch.sys.channels, dtype=float)
                neg_sum = _np.zeros(orch.sys.channels, dtype=float)
                neg_cnt = _np.zeros(orch.sys.channels, dtype=float)
                for _ in range(min(args.trials, 120)):
                    tern = orch.rng.integers(-1, 2, size=orch.sys.channels)
                    r = orch.step(force_ternary=tern)
                    dv = _np.array(r.get("dv_mV", [0]*orch.sys.channels), dtype=float)
                    pos = tern > 0; neg = tern < 0
                    pos_sum[pos] += dv[pos]; pos_cnt[pos] += 1
                    neg_sum[neg] += dv[neg]; neg_cnt[neg] += 1
                pos_mean = _np.divide(pos_sum, _np.clip(pos_cnt, 1.0, None))
                neg_mean = _np.divide(neg_sum, _np.clip(neg_cnt, 1.0, None))
                vth_vec_pa = 0.5*(pos_mean + neg_mean)
            vth = _np.array(vth_vec_pa, dtype=float)
            for _iter in range(K):
                # Evaluate errors and push vth opposite the error direction per channel
                grad = _np.zeros_like(vth)
                cnt = _np.zeros_like(vth)
                for _ in range(min(args.trials, 160)):
                    tern = orch.rng.integers(-1, 2, size=orch.sys.channels)
                    r = orch.step(force_ternary=tern)
                    dv = _np.array(r.get("dv_mV", [0]*orch.sys.channels), dtype=float)
                    # Marginized errors: treat near-threshold as errors to encourage separation
                    err_pos = (tern > 0) & ((dv - vth) < margin)
                    err_neg = (tern < 0) & ((dv - vth) > -margin)
                    grad[err_pos] -= 1.0
                    grad[err_neg] += 1.0
                    cnt += 1.0
                cnt = _np.clip(cnt, 1.0, None)
                upd = (step * grad / cnt)
                if use_mask and (active_mask is not None):
                    M = min(len(active_mask), upd.shape[0])
                    maskv = _np.array(active_mask[:M], dtype=bool)
                    upd[:M] = _np.where(maskv, upd[:M], 0.0)
                vth = vth + upd
            # Apply tuned vector
            orch.comp.set_vth_per_channel(vth)
            try:
                base_orch.comp.set_vth_per_channel(vth)
            except Exception:
                pass
            vth_vec_pa = vth
    except Exception:
        pass

    # Optional per-channel linear offset optimizer for dv (uses lin_scale baseline, tunes lin_offset per channel)
    try:
        if getattr(args, 'optimize_linear', False) and (lin_scale is not None):
            import numpy as _np
            K = int(max(1, getattr(args, 'opt_lin_iters', 6)))
            step = float(getattr(args, 'opt_lin_step_mV', 0.1))
            use_mask = bool(getattr(args, 'opt_lin_use_mask', False))
            # Initialize lin_offset if missing
            if lin_offset is None:
                lin_offset = _np.zeros(orch.sys.channels, dtype=float)
            lo = _np.array(lin_offset, dtype=float)
            for _iter in range(K):
                grad = _np.zeros_like(lo)
                cnt = _np.zeros_like(lo)
                for _ in range(min(args.trials, 160)):
                    tern = orch.rng.integers(-1, 2, size=orch.sys.channels)
                    r = orch.step(force_ternary=tern)
                    dv = _np.array(r.get("dv_mV", [0]*orch.sys.channels), dtype=float)
                    dv_lin = lin_scale*(dv + lo)
                    pred = _np.sign(dv_lin)
                    err = (pred != tern)
                    grad += _np.where(err, -_np.sign(dv_lin), 0.0)
                    cnt += 1.0
                cnt = _np.clip(cnt, 1.0, None)
                upd = (step * grad / cnt)
                if use_mask and (active_mask is not None):
                    M = min(len(active_mask), upd.shape[0])
                    maskv = _np.array(active_mask[:M], dtype=bool)
                    upd[:M] = _np.where(maskv, upd[:M], 0.0)
                lo = lo + upd
            # Apply tuned linear offset (keep scale)
            lin_offset = lo
    except Exception:
        pass

    # Optional simple linear decoder (per-channel) trained on dv features
    decoder = None
    try:
        if getattr(args, 'decoder_linear', False):
            import numpy as _np
            S = int(max(100, getattr(args, 'decoder_samples', 320)))
            lam = float(getattr(args, 'decoder_l2', 0.1))
            Xs = []; Ys = []
            for _ in range(S):
                tern = orch.rng.integers(-1, 2, size=orch.sys.channels)
                r = orch.step(force_ternary=tern)
                dv = _np.array(r.get("dv_mV", [0]*orch.sys.channels), dtype=float)
                # Features: [dv, left, right, |dv|, dv^2]
                l = _np.roll(dv, 1); rr = _np.roll(dv, -1)
                feats = _np.stack([dv, l, rr, _np.abs(dv), dv*dv], axis=1)
                Xs.append(feats)
                Ys.append(tern)
            X = _np.vstack(Xs)
            y = _np.concatenate(Ys)
            # Ridge regression for each channel independently (shared weights approximated by pooled solution)
            # Solve (X^T X + lam I)w = X^T y
            XT = X.T
            A = XT @ X + lam*_np.eye(X.shape[1])
            b = XT @ y
            w = _np.linalg.solve(A, b)
            decoder = {"w": w}
        if getattr(args, 'decoder_mlp', False):
            import numpy as _np
            S = int(max(200, getattr(args, 'decoder_samples', 400)))
            H = int(max(4, getattr(args, 'decoder_mlp_hidden', 8)))
            epochs = int(max(5, getattr(args, 'decoder_mlp_epochs', 10)))
            lr = float(max(1e-4, getattr(args, 'decoder_mlp_lr', 0.01)))
            # Build training set
            Xs = []; Ys = []
            for _ in range(S):
                tern = orch.rng.integers(-1, 2, size=orch.sys.channels)
                r = orch.step(force_ternary=tern)
                dv = _np.array(r.get("dv_mV", [0]*orch.sys.channels), dtype=float)
                l = _np.roll(dv, 1); rr = _np.roll(dv, -1)
                feats = _np.stack([dv, l, rr, _np.abs(dv), dv*dv], axis=1)
                Xs.append(feats)
                Ys.append(tern)
            X = _np.vstack(Xs)  # [S*ch, F]
            y = _np.where(_np.concatenate(Ys) > 0, 1.0, 0.0)  # map {-1,+1}???{0,1}
            F = X.shape[1]
            rng = _np.random.default_rng(int(args.seed))
            W1 = rng.normal(0, 0.1, size=(F, H)); b1 = _np.zeros(H)
            W2 = rng.normal(0, 0.1, size=(H, 1)); b2 = _np.zeros(1)
            def sigmoid(z): return 1.0/(1.0+_np.exp(-z))
            for _ in range(epochs):
                # Forward
                Z1 = X @ W1 + b1
                A1 = _np.tanh(Z1)
                Z2 = A1 @ W2 + b2
                P = sigmoid(Z2).reshape(-1)
                # Gradients (log-loss)
                dZ2 = (P - y).reshape(-1,1)
                dW2 = A1.T @ dZ2 / X.shape[0]
                db2 = dZ2.mean(axis=0)
                dA1 = dZ2 @ W2.T
                dZ1 = dA1 * (1.0 - A1*A1)
                dW1 = X.T @ dZ1 / X.shape[0]
                db1 = dZ1.mean(axis=0)
                # Update
                W1 -= lr * dW1; b1 -= lr * db1
                W2 -= lr * dW2; b2 -= lr * db2
            decoder = {"mlp": True, "W1": W1, "b1": b1, "W2": W2, "b2": b2}
    except Exception:
        decoder = None

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
            errs.append(_masked_error(pred, tern))
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
            if bool(getattr(args, 'force_cal_in_primary', False)) and (lin_scale is not None) and (lin_offset is not None):
                dv_lin = lin_scale*(acc + lin_offset)
                # confidence gate
                g_th = float(getattr(args, 'gate_thresh_mV', 0.0)); g_ex = int(getattr(args, 'gate_extra_frames', 0))
                if g_ex > 0 and g_th > 0.0:
                    low = _np.abs(dv_lin - (vth_vec_pa if vth_vec_pa is not None else 0.0)) < g_th
                    if low.any():
                        add = _accumulate_dv_over_frames(orch, tern, g_ex, str(getattr(args, 'avg_kernel', 'sum')), float(getattr(args, 'avg_ema_alpha', 0.6)))
                        dv_lin[low] = dv_lin[low] + (lin_scale[low] * add[low])
                if vth_vec_pa is not None:
                    pred = _np.sign(dv_lin - vth_vec_pa)
                else:
                    pred = _np.sign(dv_lin)
            else:
                if vth_vec_pa is not None:
                    pred = _np.sign(acc - vth_vec_pa)
                else:
                    pred = _np.sign(acc)
            errs.append(_masked_error(pred, tern))
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
            errs.append(_masked_error(pred, tern))
        path_a_summary = {
            "p50_ber": float(_np.median(errs)) if errs else None,
            "p50_energy_pj": None,
            "window_ns": float(orch.clk.p.window_ns),
        }
    elif getattr(args, 'use_decoder_for_path_a', False) and decoder is not None:
        import numpy as _np
        errs = []
        fuse = bool(getattr(args, 'fuse_decoder', False))
        alpha = float(getattr(args, 'fuse_alpha', 0.8))
        _sigma_arg = getattr(args, 'comp_input_noise_mV', None)
        sigma = float(orch.comp.p.input_noise_mV_rms if _sigma_arg is None else _sigma_arg)
        blk = int(getattr(args, 'ecc_spc_block', 4))
        use_ecc = bool(getattr(args, 'use_ecc', False))
        N = int(max(1, getattr(args, 'avg_frames', 1)))
        for _ in range(min(args.trials, 200)):
            tern = orch.rng.integers(-1, 2, size=orch.sys.channels)
            if N > 1:
                acc = _accumulate_dv_over_frames(orch, tern, N, str(getattr(args, 'avg_kernel', 'sum')), float(getattr(args, 'avg_ema_alpha', 0.6)))
                dv = _np.array(acc, dtype=float)
            else:
                r = orch.step(force_ternary=tern)
                dv = _np.array(r.get("dv_mV", [0]*orch.sys.channels), dtype=float)
            l = _np.roll(dv, 1); rr = _np.roll(dv, -1)
            feats = _np.stack([dv, l, rr, _np.abs(dv), dv*dv], axis=1)
            p_dec = _decoder_prob_from_feats(feats, decoder)
            # Optional calibrated probability using dv_lin and vth
            p_cal = None
            if bool(getattr(args, 'force_cal_in_primary', False)) and (lin_scale is not None) and (lin_offset is not None):
                dv_lin = lin_scale*(dv + (lin_offset if lin_offset is not None else 0.0))
                p_cal = _map_prob_from_dv(dv_lin, vth_vec_pa, sigma)
            p_fused = p_dec if not fuse else _fuse_probs(p_cal, p_dec, alpha)
            pred = _np.where(p_fused >= 0.5, 1, -1)
            if use_ecc:
                pred = _apply_spc(pred, p_fused, blk)
            if active_mask is not None:
                M = min(len(active_mask), pred.shape[0])
                am = _np.array(active_mask[:M], dtype=bool)
                pred = pred[:M][am]; tcur = tern[:M][am]
            else:
                tcur = tern
            errs.append(float(_np.mean(pred != tcur)))
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
        "baseline_calibrated_alt": {
            "soft": (cal_summary_alt_soft or {}),
            "binary": (cal_summary_alt_bin or {}),
        },
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
    _auto_tune_func = None
    if args.autotune:
        from looking_glass.tuner import auto_tune as _auto_tune_func
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
    # Local autotune (window/mask/avg)
    local_best = None
    try:
        if getattr(args, 'local_autotune', False):
            import numpy as _np
            la_w = [float(w) for w in str(getattr(args, 'la_windows', '18,19,20,21')).split(',') if w.strip()]
            la_m = [float(m) for m in str(getattr(args, 'la_mask_fracs', '0.0625,0.09375,0.125')).split(',') if m.strip()]
            la_a = [int(a) for a in str(getattr(args, 'la_avg_frames', '2,3')).split(',') if a.strip()]
            best = {"ber": 1.0, "window_ns": None, "mask_frac": None, "avg_frames": None}
            T = int(min(args.trials, 160))
            for w in la_w:
                orch.clk.p.window_ns = float(w)
                for mf in la_m:
                    for af in la_a:
                        # Build a short-run evaluation using current classifier
                        errs = []
                        for _ in range(T):
                            tern = orch.rng.integers(-1, 2, size=orch.sys.channels)
                            r = orch.step(force_ternary=tern)
                            dv = _np.array(r.get("dv_mV", [0]*orch.sys.channels))
                            # Apply avg frames if requested
                            if af > 1:
                                acc = dv.copy().astype(float)
                                for _j in range(af-1):
                                    r2 = orch.step(force_ternary=tern)
                                    acc += _np.array(r2.get("dv_mV", [0]*orch.sys.channels))
                                dv_eff = acc
                            else:
                                dv_eff = dv
                            # Apply mask fraction (select best channels only)
                            M = orch.sys.channels
                            keep = int(max(0, M - int(round(mf*M))))
                            if keep > 0 and keep < M:
                                # Score by |dv|; keep largest
                                idx = _np.argsort(_np.abs(dv_eff))[::-1][:keep]
                                dv_sel = dv_eff[idx]
                                t_sel = tern[idx]
                            else:
                                dv_sel = dv_eff
                                t_sel = tern
                            pred = _np.sign(dv_sel)
                            errs.append(float(_np.mean(pred != t_sel)))
                        med = float(_np.median(errs)) if errs else None
                        if (med is not None) and (med < best["ber"]):
                            best = {"ber": med, "window_ns": float(w), "mask_frac": float(mf), "avg_frames": int(af)}
            local_best = best
            summary["local_autotune"] = best
            # Optionally override primary path_a with local best estimate
            try:
                if getattr(args, 'use_autotuned_as_primary', False) and best.get("ber") is not None:
                    summary["path_a"] = {"p50_ber": best["ber"], "window_ns": best["window_ns"], "note": "local_autotune"}
            except Exception:
                pass
    except Exception:
        pass

        tune_res = _auto_tune_func(
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
                        errs.append(_masked_error(pred, tern))
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








