import os
import sys
import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from looking_glass.orchestrator import Orchestrator, SystemParams
from looking_glass.sim.emitter import EmitterParams
from looking_glass.sim.optics import OpticsParams
from looking_glass.sim.sensor import PDParams
from looking_glass.sim.tia import TIAParams
from looking_glass.sim.comparator import ComparatorParams
from looking_glass.sim.clock import ClockParams


def load_yaml(path, cls, channels=None):
    base = cls()
    if channels is not None and hasattr(base, "channels"):
        base.channels = channels
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    for k, v in data.items():
        if hasattr(base, k):
            setattr(base, k, v)
    if channels is not None and hasattr(base, "channels"):
        base.channels = channels
    return base


def compare_step_vs_manual(trials=200):
    channels = 8
    sys_p = SystemParams(channels=channels, window_ns=9.0, seed=321, reset_analog_state_each_frame=False)
    emit = load_yaml('configs/packs/overlays/emitter_pathb_premium.yaml', EmitterParams, channels)
    optx = load_yaml('configs/packs/overlays/optics_pathb_soa_mzi_clamp.yaml', OpticsParams)
    pd = PDParams()
    tia = load_yaml('configs/packs/overlays/tia_pathb_premium.yaml', TIAParams)
    comp = load_yaml('configs/packs/overlays/comparator_pathb_premium.yaml', ComparatorParams)
    clk = ClockParams(window_ns=9.0, jitter_ps_rms=45.0)
    orch = Orchestrator(sys_p, emit, optx, pd, tia, comp, clk)
    rng = np.random.default_rng(4321)
    errs_step = []
    errs_manual = []
    for _ in range(trials):
        tern0 = rng.integers(-1, 2, size=channels)
        res = orch.step(force_ternary=tern0)
        errs_step.append(np.mean(np.array(res['t_out']) != tern0))
        dt = float(orch.clk.sample_window())
        Pp, Pm = orch.emit.simulate(tern0, dt, orch.sys.temp_C)
        Pp, Pm, _, _ = orch.optx.simulate(Pp, Pm, dt)
        Ip = orch.pd.simulate(Pp, dt)
        Im = orch.pd.simulate(Pm, dt)
        Vp = orch.tia.simulate(Ip, dt)
        Vm = orch.tia.simulate(Im, dt)
        out = orch.comp.simulate(Vp, Vm, orch.sys.temp_C)
        errs_manual.append(np.mean(out != tern0))
    print('step median', float(np.median(errs_step)))
    print('manual median', float(np.median(errs_manual)))


if __name__ == '__main__':
    compare_step_vs_manual()
