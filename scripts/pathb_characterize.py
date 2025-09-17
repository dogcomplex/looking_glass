import argparse
import json
import os
import sys
import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from looking_glass.sim.optics import OpticsParams, Optics
from looking_glass.sim.emitter import EmitterParams
from looking_glass.sim.sensor import PDParams
from looking_glass.sim.tia import TIAParams
from looking_glass.sim.comparator import ComparatorParams
from looking_glass.sim.clock import ClockParams
from looking_glass.orchestrator import Orchestrator, SystemParams


def load_pack(path, cls, channels=None):
    base = cls()
    if channels is not None and hasattr(base, "channels"):
        base.channels = channels
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for k, v in data.items():
        if hasattr(base, k):
            setattr(base, k, v)
    if channels is not None and hasattr(base, "channels"):
        base.channels = channels
    return base


def build_optics(path):
    params = load_pack(path, OpticsParams)
    return Optics(params)


def transfer_curve(optics, total_mw=2.0, span_mw=4.0, steps=41, dt_ns=9.0):
    diffs = np.linspace(-span_mw, span_mw, steps)
    result = []
    for d in diffs:
        plus_in = np.array([0.5 * total_mw + 0.5 * d])
        minus_in = np.array([0.5 * total_mw - 0.5 * d])
        plus_in = np.clip(plus_in, 0.0, None)
        minus_in = np.clip(minus_in, 0.0, None)
        p_out, m_out, _, _ = optics.simulate(plus_in, minus_in, dt_ns)
        diff_out = float(p_out[0] - m_out[0])
        result.append({
            "diff_in_mw": float(d),
            "diff_out_mw": diff_out,
            "servo_bias_mw": float(optics._servo_bias[0] if optics._servo_bias is not None else 0.0)
        })
    return result


def osnr_growth(optics, passes=6, total_mw=2.0, diff_mw=0.0, dt_ns=9.0):
    plus = np.array([0.5 * total_mw + 0.5 * diff_mw])
    minus = np.array([0.5 * total_mw - 0.5 * diff_mw])
    stages = []
    for _ in range(passes):
        plus, minus, _, _ = optics.simulate(plus, minus, dt_ns)
        total = plus + minus
        diff = plus - minus
        stages.append({
            "total_mw": float(total[0]),
            "diff_mw": float(diff[0])
        })
    return stages


def ternary_histogram(emitter_path, optics_path, tia_path, comp_path, clock_path, channels=8, trials=400, window_ns=9.0, seed=321):
    sys_p = SystemParams(channels=channels, window_ns=window_ns, seed=seed, reset_analog_state_each_frame=False)
    emit = load_pack(emitter_path, EmitterParams, channels)
    optx = load_pack(optics_path, OpticsParams)
    pd = PDParams()
    tia = load_pack(tia_path, TIAParams)
    comp = load_pack(comp_path, ComparatorParams)
    clk = load_pack(clock_path, ClockParams)
    orch = Orchestrator(sys_p, emit, optx, pd, tia, comp, clk)
    rng = np.random.default_rng(seed + 99)
    counts = {(t, o): 0 for t in (-1, 0, 1) for o in (-1, 0, 1)}
    servo_trace = []
    for _ in range(trials):
        tern = rng.integers(-1, 2, size=channels)
        res = orch.step(force_ternary=tern)
        out = np.array(res.get("t_out", tern), dtype=int)
        for t, o in zip(tern, out):
            counts[(int(t), int(o))] += 1
        if hasattr(orch.optx, "_servo_bias") and orch.optx._servo_bias is not None:
            servo_trace.append(float(np.mean(orch.optx._servo_bias)))
    return {
        "counts": {f"{t}->{o}": c for (t, o), c in counts.items()},
        "servo_bias_trace": servo_trace
    }


def main():
    parser = argparse.ArgumentParser(description="Characterize Path B optics stack")
    parser.add_argument("--optics", required=True, help="Optics overlay YAML path")
    parser.add_argument("--emitter", required=True, help="Emitter pack")
    parser.add_argument("--tia", required=True, help="TIA pack")
    parser.add_argument("--comparator", required=True, help="Comparator pack")
    parser.add_argument("--clock", required=True, help="Clock pack")
    parser.add_argument("--channels", type=int, default=8)
    parser.add_argument("--window-ns", type=float, default=9.0)
    parser.add_argument("--trials", type=int, default=400)
    parser.add_argument("--passes", type=int, default=6)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    optics = build_optics(args.optics)
    transfer = transfer_curve(optics, dt_ns=args.window_ns)
    optics = build_optics(args.optics)
    growth = osnr_growth(optics, passes=args.passes, dt_ns=args.window_ns)
    hist = ternary_histogram(
        emitter_path=args.emitter,
        optics_path=args.optics,
        tia_path=args.tia,
        comp_path=args.comparator,
        clock_path=args.clock,
        channels=args.channels,
        trials=args.trials,
        window_ns=args.window_ns,
    )
    data = {
        "transfer_curve": transfer,
        "osnr_growth": growth,
        "ternary_histogram": hist
    }
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    else:
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
